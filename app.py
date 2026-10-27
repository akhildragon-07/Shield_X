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
    MAX_EMAILS
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-12345")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


@app.route("/")
def index():
    return render_template(
        "index.html",
        smtp_enabled=is_smtp_enabled(),
        max_emails=MAX_EMAILS
    )


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "email-deliverability-checker",
        "smtp_verification_enabled": is_smtp_enabled()
    }), 200


@app.route("/api/check", methods=["POST"])
def check_emails():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "Please provide a valid JSON payload with email addresses."
        }), 400

    raw_input = data.get("emails")
    if not raw_input:
        return jsonify({
            "success": False,
            "error": "No email addresses provided. Enter at least one email."
        }), 400

    if isinstance(raw_input, str):
        lines = [line.strip() for line in raw_input.replace(",", "\n").replace(";", "\n").splitlines()]
    elif isinstance(raw_input, list):
        lines = [str(item).strip() for item in raw_input]
    else:
        return jsonify({
            "success": False,
            "error": "Invalid format for emails field. Expected text or a list."
        }), 400

    emails = [e for e in lines if e]
    if not emails:
        return jsonify({
            "success": False,
            "error": "No non-empty email addresses found."
        }), 400

    try:
        logger.info(f"Checking batch of {len(emails)} items")
        results, summary = verify_batch(emails)
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
    except Exception as e:
        logger.error(f"Error checking emails: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Something went wrong while checking the emails."
        }), 500


@app.route("/api/export-csv", methods=["POST"])
def export_csv():
    data = request.get_json(silent=True)
    if not data or "results" not in data or not isinstance(data["results"], list):
        return jsonify({
            "success": False,
            "error": "Expected results array in request body."
        }), 400

    results = data["results"]
    if not results:
        return jsonify({
            "success": False,
            "error": "Results list is empty."
        }), 400

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

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
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
