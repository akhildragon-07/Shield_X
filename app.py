"""
app.py - Web application entrypoint for Email Deliverability Checker.

Built with Flask, designed for production deployment on Render with Gunicorn.
Follows privacy-first design: no storage, no persistent logs of submitted emails,
zero transmission of actual email content.
"""

import os
import io
import csv
import logging
from flask import Flask, render_template, request, jsonify, Response
from checker import (
    verify_batch,
    is_smtp_enabled,
    STATUS_DELIVERABLE,
    STATUS_BOUNCE,
    STATUS_UNKNOWN,
    MAX_EMAILS_PER_BATCH
)

# Configure basic logging (never log user email addresses)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("EmailDeliverabilityChecker")

app = Flask(__name__)
# Secret key for sessions/CSRF if needed
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "deliverability-checker-insecure-dev-key")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # Max 2MB request payload


@app.route("/")
def index():
    """Render the main single-page interface."""
    return render_template(
        "index.html",
        smtp_enabled=is_smtp_enabled(),
        max_emails=MAX_EMAILS_PER_BATCH
    )


@app.route("/health")
def health():
    """Healthcheck endpoint for hosting platforms like Render."""
    return jsonify({
        "status": "healthy",
        "service": "email-deliverability-checker",
        "smtp_verification_enabled": is_smtp_enabled()
    }), 200


@app.route("/api/check", methods=["POST"])
def check_emails():
    """
    API endpoint to check a list of emails.
    Accepts JSON body:
      {
        "emails": "user1@example.com\\nuser2@test.org"
      }
      OR
      {
        "emails": ["user1@example.com", "user2@test.org"]
      }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request body. Expected JSON payload with 'emails' field."
        }), 400

    raw_input = data.get("emails")
    if not raw_input:
        return jsonify({
            "success": False,
            "error": "No email addresses provided. Please enter at least one email address."
        }), 400

    if isinstance(raw_input, str):
        # Split by newlines, commas, or semicolons
        lines = [line.strip() for line in raw_input.replace(",", "\n").replace(";", "\n").splitlines()]
    elif isinstance(raw_input, list):
        lines = [str(item).strip() for item in raw_input]
    else:
        return jsonify({
            "success": False,
            "error": "Invalid format for 'emails'. Must be a string or list of strings."
        }), 400

    emails = [e for e in lines if e]
    if not emails:
        return jsonify({
            "success": False,
            "error": "The submission did not contain any valid non-empty email lines."
        }), 400

    try:
        # Privacy note: We only log the count of emails evaluated, not the email addresses.
        logger.info(f"Processing deliverability verification batch of {len(emails)} raw items.")
        results, summary = verify_batch(emails)
        logger.info(f"Completed batch check. Total unique: {summary['total']}, "
                    f"Deliverable: {summary['deliverable']}, Bounce: {summary['bounce']}, Unknown: {summary['unknown']}")

        return jsonify({
            "success": True,
            "summary": summary,
            "results": results
        }), 200

    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": str(ve)
        }), 400
    except Exception as exc:
        logger.error(f"Unexpected error during verification: {str(exc)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An internal server error occurred while analyzing the email addresses."
        }), 500


@app.route("/api/export-csv", methods=["POST"])
def export_csv():
    """
    Generate and stream a CSV file containing deliverability results.
    Accepts JSON body:
      {
        "results": [
          {"email": "...", "status": "...", "domain": "...", "mx_host": "...", "reason": "..."}
        ]
      }
    """
    data = request.get_json(silent=True)
    if not data or "results" not in data or not isinstance(data["results"], list):
        return jsonify({
            "success": False,
            "error": "Invalid payload. Expected JSON with 'results' array."
        }), 400

    results = data["results"]
    if not results:
        return jsonify({
            "success": False,
            "error": "Results list is empty. Nothing to export."
        }), 400

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Write CSV Header
    writer.writerow([
        "Email Address",
        "Deliverability Status",
        "Domain",
        "Primary MX Host",
        "Format Valid",
        "SMTP Checked",
        "Detailed Reason"
    ])

    for item in results:
        writer.writerow([
            item.get("email", ""),
            item.get("status", STATUS_UNKNOWN),
            item.get("domain", "") or "N/A",
            item.get("mx_host", "") or "N/A",
            "Yes" if item.get("format_valid") else "No",
            "Yes" if item.get("smtp_checked") else "No",
            item.get("reason", "")
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=email_deliverability_report.csv",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1")
    print(f"Starting Email Deliverability Checker on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
