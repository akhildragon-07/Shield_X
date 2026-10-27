import os
import re
import socket
import smtplib
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver
import dns.exception

STATUS_DELIVERABLE = "Likely deliverable"
STATUS_BOUNCE = "Likely to bounce"
STATUS_UNKNOWN = "Unknown"

MAX_EMAILS = 100
MAX_EMAILS_PER_BATCH = MAX_EMAILS
EMAIL_REGEX = re.compile(
    r"^(?P<local>[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+)@"
    r"(?P<domain>[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+)$"
)


def is_smtp_enabled():
    val = os.getenv("ENABLE_SMTP_CHECK", "true").lower()
    return val not in ("false", "0", "no", "disabled")


def validate_format(email):
    if not email or not isinstance(email, str):
        return False, "Email address is empty.", None, None

    cleaned = email.strip()
    if len(cleaned) > 254:
        return False, "Email is too long (over 254 characters).", None, None

    match = EMAIL_REGEX.match(cleaned)
    if not match:
        return False, "Invalid email format.", None, None

    local_part = match.group("local")
    domain = match.group("domain").lower()

    if len(local_part) > 64:
        return False, "Local part is longer than 64 characters.", None, None

    if ".." in local_part or ".." in domain:
        return False, "Email cannot contain consecutive dots.", None, None

    tld = domain.split(".")[-1]
    if len(tld) < 2 or tld.isdigit():
        return False, "Invalid top-level domain.", None, None

    return True, "Email format looks good.", local_part, domain


def check_dns(domain, timeout=3.5):
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout

    try:
        answers = resolver.resolve(domain, "MX")
        mx_records = sorted(answers, key=lambda r: r.preference)
        hosts = [str(r.exchange).rstrip(".") for r in mx_records if str(r.exchange).strip()]
        
        if hosts:
            if len(hosts) == 1 and hosts[0] in ("", "."):
                return False, None, [], f"Domain '{domain}' has a Null MX record and rejects mail."
            return True, hosts[0], hosts, f"Found {len(hosts)} MX record(s) for '{domain}'."

    except dns.resolver.NXDOMAIN:
        return False, None, [], f"Domain '{domain}' does not exist (NXDOMAIN)."
    except dns.resolver.NoAnswer:
        pass
    except dns.resolver.NoNameservers:
        return False, None, [], f"Nameservers not responding for '{domain}'."
    except dns.exception.Timeout:
        return False, None, [], f"DNS lookup timed out for '{domain}'."
    except Exception as e:
        return False, None, [], f"DNS lookup error for '{domain}': {str(e)}"

    # fallback to A record if no MX exists
    try:
        a_records = resolver.resolve(domain, "A")
        fallback_hosts = [str(r.address) for r in a_records]
        if fallback_hosts:
            return True, domain, fallback_hosts, f"No MX found for '{domain}', but valid A record exists."
    except Exception:
        pass

    return False, None, [], f"Domain '{domain}' has no MX or A records configured to receive mail."


def check_smtp_recipient(email, mx_host, timeout=3.5):
    details = {
        "mx_host": mx_host,
        "smtp_checked": True,
        "smtp_response_code": None,
        "smtp_response_message": None
    }

    try:
        server = smtplib.SMTP(timeout=timeout)
        server.set_debuglevel(0)
        code, resp = server.connect(mx_host, 25)

        try:
            server.ehlo("validator.local")
        except Exception:
            server.helo("validator.local")

        mail_code, mail_resp = server.mail("<>")
        if mail_code >= 400:
            mail_code, mail_resp = server.mail("<check@validator.local>")

        if mail_code >= 400:
            server.quit()
            details["smtp_response_code"] = mail_code
            details["smtp_response_message"] = str(mail_resp)
            return STATUS_UNKNOWN, f"Server rejected sender handshake (code {mail_code}).", details

        # Check recipient without sending DATA
        rcpt_code, rcpt_resp = server.rcpt(f"<{email}>")
        rcpt_msg = rcpt_resp.decode("utf-8", errors="replace") if isinstance(rcpt_resp, bytes) else str(rcpt_resp)

        details["smtp_response_code"] = rcpt_code
        details["smtp_response_message"] = rcpt_msg

        try:
            server.quit()
        except Exception:
            pass

        if rcpt_code in (250, 251):
            return STATUS_DELIVERABLE, f"Mail server accepted recipient check (status {rcpt_code}). Final delivery depends on mailbox spam filters.", details
        elif rcpt_code in (550, 551, 552, 553, 554):
            return STATUS_BOUNCE, f"Mail server rejected recipient ({rcpt_code}: {rcpt_msg.strip()}).", details
        elif 400 <= rcpt_code < 500:
            return STATUS_UNKNOWN, f"Server returned temporary failure or greylisting ({rcpt_code}).", details
        else:
            return STATUS_UNKNOWN, f"Server returned inconclusive response: {rcpt_code} {rcpt_msg.strip()}.", details

    except (socket.timeout, TimeoutError):
        details["smtp_checked"] = False
        return STATUS_UNKNOWN, f"Connection to {mx_host} timed out on port 25 (port 25 is blocked by most cloud hosts).", details
    except ConnectionRefusedError:
        details["smtp_checked"] = False
        return STATUS_UNKNOWN, f"Connection refused by {mx_host} on port 25.", details
    except OSError as err:
        details["smtp_checked"] = False
        return STATUS_UNKNOWN, f"Could not connect to {mx_host} on port 25 (network blocked): {str(err)}", details
    except Exception as e:
        details["smtp_checked"] = False
        return STATUS_UNKNOWN, f"SMTP check error: {str(e)}", details


def verify_single_email(email, allow_smtp=None):
    clean = email.strip()
    result = {
        "email": clean,
        "status": STATUS_UNKNOWN,
        "format_valid": False,
        "domain": None,
        "mx_host": None,
        "mx_records": [],
        "reason": "",
        "smtp_checked": False
    }

    # syntax check
    ok, reason, local, domain = validate_format(clean)
    result["format_valid"] = ok
    if not ok:
        result["status"] = STATUS_BOUNCE
        result["reason"] = reason
        return result

    result["domain"] = domain

    # dns check
    dns_ok, primary_mx, hosts, dns_reason = check_dns(domain)
    result["mx_host"] = primary_mx
    result["mx_records"] = hosts

    if not dns_ok:
        if "NXDOMAIN" in dns_reason or "no MX or A records" in dns_reason or "Null MX" in dns_reason:
            result["status"] = STATUS_BOUNCE
        else:
            result["status"] = STATUS_UNKNOWN
        result["reason"] = dns_reason
        return result

    # smtp check if enabled
    run_smtp = allow_smtp if allow_smtp is not None else is_smtp_enabled()
    if not run_smtp:
        result["status"] = STATUS_UNKNOWN
        result["reason"] = f"Domain '{domain}' has valid MX records ({primary_mx}), but SMTP port 25 checking is disabled."
        return result

    status, reason, details = check_smtp_recipient(clean, primary_mx)
    result["status"] = status
    result["reason"] = reason
    result["smtp_checked"] = details.get("smtp_checked", False)
    if details.get("smtp_response_code"):
        result["smtp_code"] = details["smtp_response_code"]

    return result


def verify_batch(emails, max_workers=6, allow_smtp=None):
    seen = set()
    unique = []
    for item in emails:
        clean = item.strip()
        if clean and clean not in seen:
            seen.add(clean)
            unique.append(clean)

    if len(unique) > MAX_EMAILS:
        raise ValueError(f"Too many emails. Maximum is {MAX_EMAILS} unique addresses per batch (received {len(unique)}).")

    summary = {
        "total": len(unique),
        "deliverable": 0,
        "bounce": 0,
        "unknown": 0
    }
    if not unique:
        return [], summary

    results_map = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(unique))) as executor:
        futures = {executor.submit(verify_single_email, em, allow_smtp): em for em in unique}
        for f in as_completed(futures):
            em = futures[f]
            try:
                results_map[em] = f.result()
            except Exception as e:
                results_map[em] = {
                    "email": em,
                    "status": STATUS_UNKNOWN,
                    "format_valid": False,
                    "domain": None,
                    "mx_host": None,
                    "mx_records": [],
                    "reason": f"Verification error: {str(e)}",
                    "smtp_checked": False
                }

    ordered_results = []
    for em in unique:
        r = results_map[em]
        ordered_results.append(r)
        if r["status"] == STATUS_DELIVERABLE:
            summary["deliverable"] += 1
        elif r["status"] == STATUS_BOUNCE:
            summary["bounce"] += 1
        else:
            summary["unknown"] += 1

    return ordered_results, summary
