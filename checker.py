"""
checker.py - Core email deliverability verification engine.

Provides modular, explainable checks across 3 steps:
  1. Syntax & Format Validation
  2. DNS & MX Record Resolution (with RFC 5321 A-record fallback)
  3. Safe SMTP Recipient Verification (EHLO/HELO -> MAIL FROM -> RCPT TO -> QUIT)
     CRITICAL: NEVER sends SMTP DATA or actual email messages.
"""

import os
import re
import socket
import smtplib
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver
import dns.exception

# Status category constants
STATUS_DELIVERABLE = "Likely deliverable"
STATUS_BOUNCE = "Likely to bounce"
STATUS_UNKNOWN = "Unknown"

# Limits & Defaults
DEFAULT_DNS_TIMEOUT = 3.5
DEFAULT_SMTP_TIMEOUT = 3.5
MAX_EMAILS_PER_BATCH = 100

# RFC 5322 compliant simplified regex for standard email syntax
EMAIL_REGEX = re.compile(
    r"^(?P<local>[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+)@"
    r"(?P<domain>[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+)$"
)


def is_smtp_enabled() -> bool:
    """Check environment variable whether outbound SMTP checks are enabled."""
    val = os.getenv("ENABLE_SMTP_CHECK", "true").strip().lower()
    return val not in ("false", "0", "no", "disabled")


def validate_format(email: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Step A: Validate email format.
    Returns: (is_valid, reason, local_part, domain)
    """
    if not email or not isinstance(email, str):
        return False, "Email address is empty.", None, None

    cleaned = email.strip()
    if len(cleaned) > 254:
        return False, "Email address exceeds maximum length of 254 characters.", None, None

    match = EMAIL_REGEX.match(cleaned)
    if not match:
        return False, "Invalid email format. Must follow standard user@domain.tld syntax.", None, None

    local_part = match.group("local")
    domain = match.group("domain").lower()

    if len(local_part) > 64:
        return False, "Local part of email exceeds 64 characters.", None, None

    # Check for consecutive dots in local part or domain
    if ".." in local_part or ".." in domain:
        return False, "Email address contains invalid consecutive periods.", None, None

    # Ensure top-level domain has at least 2 characters and is not purely numeric
    tld = domain.split(".")[-1]
    if len(tld) < 2 or tld.isdigit():
        return False, "Invalid top-level domain (TLD).", None, None

    return True, "Email format is valid.", local_part, domain


def check_dns(domain: str, timeout: float = DEFAULT_DNS_TIMEOUT) -> Tuple[bool, Optional[str], List[str], str]:
    """
    Step B: Query DNS for MX records (or fallback A/AAAA records per RFC 5321).
    Returns: (success, primary_mx_host, all_hosts, explanation)
    """
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout

    try:
        # 1. Query MX records
        answers = resolver.resolve(domain, "MX")
        # Sort by MX preference (lowest priority number = most preferred)
        mx_records = sorted(answers, key=lambda rdata: rdata.preference)
        hosts = [str(rdata.exchange).rstrip(".") for rdata in mx_records if str(rdata.exchange).strip()]
        
        if hosts:
            # Check for "null MX" record (RFC 7505: priority 0, host ".")
            if len(hosts) == 1 and hosts[0] in ("", "."):
                return False, None, [], f"Domain '{domain}' publishes a Null MX record, indicating it does not accept email."
            return True, hosts[0], hosts, f"Found {len(hosts)} valid MX mail server(s) for '{domain}'."

    except dns.resolver.NXDOMAIN:
        return False, None, [], f"Domain '{domain}' does not exist (NXDOMAIN)."
    except dns.resolver.NoAnswer:
        # RFC 5321 Fallback: if no MX record, check for A or AAAA records
        pass
    except dns.resolver.NoNameservers:
        return False, None, [], f"No responding nameservers found for domain '{domain}'."
    except dns.exception.Timeout:
        return False, None, [], f"DNS lookup timed out while querying MX records for '{domain}'."
    except Exception as exc:
        return False, None, [], f"DNS resolution error for '{domain}': {str(exc)}"

    # Check fallback A / AAAA records
    try:
        a_records = resolver.resolve(domain, "A")
        fallback_hosts = [str(rdata.address) for rdata in a_records]
        if fallback_hosts:
            return True, domain, fallback_hosts, f"No explicit MX record found for '{domain}', but valid fallback A address record exists (RFC 5321)."
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        pass
    except Exception:
        pass

    return False, None, [], f"Domain '{domain}' has no MX or address records configured to receive email."


def check_smtp_recipient(
    email: str,
    mx_host: str,
    timeout: float = DEFAULT_SMTP_TIMEOUT
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Step C: Optional SMTP recipient verification.
    Connects to mail server, performs EHLO/HELO, MAIL FROM, and RCPT TO.
    NEVER sends DATA or actual email message.
    Always terminates with QUIT.
    
    Returns: (status, explanation, details)
    """
    details: Dict[str, Any] = {
        "mx_host": mx_host,
        "smtp_checked": True,
        "smtp_response_code": None,
        "smtp_response_message": None
    }

    try:
        # Establish connection with socket timeout
        # Using smtplib.SMTP with custom timeout
        server = smtplib.SMTP(timeout=timeout)
        server.set_debuglevel(0)

        # Attempt connection to port 25
        code, resp = server.connect(mx_host, 25)
        resp_str = resp.decode("utf-8", errors="replace") if isinstance(resp, bytes) else str(resp)

        # Initiate handshake
        try:
            helo_code, helo_resp = server.ehlo("validator.local")
        except Exception:
            helo_code, helo_resp = server.helo("validator.local")

        # Set envelope sender (null sender or validation address)
        # RFC 5321 recommends null reverse-path <> for verification probes
        mail_code, mail_resp = server.mail("<>")
        if mail_code >= 400:
            # Some servers reject null sender, try simple address
            mail_code, mail_resp = server.mail("<check@validator.local>")

        if mail_code >= 400:
            server.quit()
            details["smtp_response_code"] = mail_code
            details["smtp_response_message"] = str(mail_resp)
            return (
                STATUS_UNKNOWN,
                f"Mail server rejected envelope sender initiation (Code {mail_code}). Mailbox status could not be verified.",
                details
            )

        # Recipient probe: RCPT TO
        # CRITICAL: We do NOT send DATA.
        rcpt_code, rcpt_resp = server.rcpt(f"<{email}>")
        rcpt_resp_str = rcpt_resp.decode("utf-8", errors="replace") if isinstance(rcpt_resp, bytes) else str(rcpt_resp)

        details["smtp_response_code"] = rcpt_code
        details["smtp_response_message"] = rcpt_resp_str

        # Always close properly
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass

        # Evaluate response code
        if rcpt_code in (250, 251):
            return (
                STATUS_DELIVERABLE,
                f"Mail server accepted recipient verification probe (Status {rcpt_code}). Note: Mailbox existence cannot be guaranteed due to possible internal routing or catch-all configurations.",
                details
            )
        elif rcpt_code in (550, 551, 552, 553, 554):
            return (
                STATUS_BOUNCE,
                f"Mail server rejected recipient address (Status {rcpt_code}: {rcpt_resp_str.strip()}). The address is likely invalid or nonexistent.",
                details
            )
        elif 400 <= rcpt_code < 500:
            return (
                STATUS_UNKNOWN,
                f"Mail server returned temporary deferral or greylisting response (Status {rcpt_code}: {rcpt_resp_str.strip()}). Mailbox existence remains unconfirmed.",
                details
            )
        else:
            return (
                STATUS_UNKNOWN,
                f"Mail server returned ambiguous response (Status {rcpt_code}: {rcpt_resp_str.strip()}).",
                details
            )

    except (socket.timeout, TimeoutError):
        details["smtp_checked"] = False
        details["error"] = "Connection timed out"
        return (
            STATUS_UNKNOWN,
            f"SMTP connection to '{mx_host}' timed out on port 25. Many hosting environments (and free tiers like Render) block outbound SMTP port 25.",
            details
        )
    except ConnectionRefusedError:
        details["smtp_checked"] = False
        details["error"] = "Connection refused"
        return (
            STATUS_UNKNOWN,
            f"Connection refused by mail server '{mx_host}' on port 25. The server may be blocking probes or port 25 is restricted.",
            details
        )
    except OSError as os_err:
        details["smtp_checked"] = False
        details["error"] = str(os_err)
        return (
            STATUS_UNKNOWN,
            f"Network error communicating with '{mx_host}' on port 25: {str(os_err)}. Outbound port 25 is likely blocked by network security rules.",
            details
        )
    except Exception as exc:
        details["smtp_checked"] = False
        details["error"] = str(exc)
        return (
            STATUS_UNKNOWN,
            f"Unable to complete SMTP recipient check with '{mx_host}': {str(exc)}.",
            details
        )


def verify_single_email(email: str, allow_smtp: Optional[bool] = None) -> Dict[str, Any]:
    """
    Run full deliverability verification pipeline for a single email address:
      Step A: Format validation
      Step B: DNS & MX records lookup
      Step C: Optional SMTP verification (if enabled)
      Step D: Final conservative classification
    """
    email_clean = email.strip()
    result: Dict[str, Any] = {
        "email": email_clean,
        "status": STATUS_UNKNOWN,
        "format_valid": False,
        "domain": None,
        "mx_host": None,
        "mx_records": [],
        "reason": "",
        "smtp_checked": False
    }

    # Step A: Format Validation
    format_ok, format_reason, local_part, domain = validate_format(email_clean)
    result["format_valid"] = format_ok

    if not format_ok:
        result["status"] = STATUS_BOUNCE
        result["reason"] = format_reason
        return result

    result["domain"] = domain

    # Step B: DNS & Mail Server Checks
    dns_ok, primary_mx, all_hosts, dns_reason = check_dns(domain)
    result["mx_host"] = primary_mx
    result["mx_records"] = all_hosts

    if not dns_ok:
        # Check if it was a timeout / temporary error vs hard NXDOMAIN
        if "NXDOMAIN" in dns_reason or "no MX or address records" in dns_reason or "Null MX" in dns_reason:
            result["status"] = STATUS_BOUNCE
            result["reason"] = dns_reason
        else:
            result["status"] = STATUS_UNKNOWN
            result["reason"] = dns_reason
        return result

    # Step C: Optional SMTP Recipient Verification
    perform_smtp = allow_smtp if allow_smtp is not None else is_smtp_enabled()

    if not perform_smtp:
        # SMTP checks explicitly disabled in config
        result["status"] = STATUS_UNKNOWN
        result["reason"] = (
            f"Domain '{domain}' has valid mail exchanger ({primary_mx}). "
            f"SMTP recipient probe is disabled by server configuration."
        )
        return result

    # Perform safe SMTP probe
    smtp_status, smtp_reason, details = check_smtp_recipient(email_clean, primary_mx)
    result["status"] = smtp_status
    result["reason"] = smtp_reason
    result["smtp_checked"] = details.get("smtp_checked", False)
    if details.get("smtp_response_code"):
        result["smtp_code"] = details["smtp_response_code"]

    return result


def verify_batch(
    emails: List[str],
    max_workers: int = 8,
    allow_smtp: Optional[bool] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Deduplicates and evaluates a batch of email addresses concurrently.
    Enforces maximum batch limit of 100 unique addresses.
    
    Returns: (results_list, summary_counts)
    """
    # Deduplicate while preserving order
    seen = set()
    unique_emails = []
    for item in emails:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_emails.append(cleaned)

    if len(unique_emails) > MAX_EMAILS_PER_BATCH:
        raise ValueError(
            f"Batch size exceeds maximum limit of {MAX_EMAILS_PER_BATCH} unique email addresses. "
            f"Received {len(unique_emails)}."
        )

    results: List[Dict[str, Any]] = []
    summary = {
        "total": len(unique_emails),
        "deliverable": 0,
        "bounce": 0,
        "unknown": 0
    }

    if not unique_emails:
        return results, summary

    # Concurrent processing with bounded pool
    # Maintain input order
    results_map: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(unique_emails))) as executor:
        future_to_email = {
            executor.submit(verify_single_email, email, allow_smtp): email
            for email in unique_emails
        }
        for future in as_completed(future_to_email):
            email = future_to_email[future]
            try:
                res = future.result()
            except Exception as e:
                res = {
                    "email": email,
                    "status": STATUS_UNKNOWN,
                    "format_valid": False,
                    "domain": None,
                    "mx_host": None,
                    "mx_records": [],
                    "reason": f"Unexpected verification failure: {str(e)}",
                    "smtp_checked": False
                }
            results_map[email] = res

    # Reconstruct original order
    for email in unique_emails:
        res = results_map[email]
        results.append(res)
        status = res.get("status")
        if status == STATUS_DELIVERABLE:
            summary["deliverable"] += 1
        elif status == STATUS_BOUNCE:
            summary["bounce"] += 1
        else:
            summary["unknown"] += 1

    return results, summary
