"""
test_app.py - Comprehensive test suite for Email Deliverability Checker.

Covers:
  - Valid and invalid email formats
  - Empty input handling
  - Multiple and duplicate email deduplication
  - Over 100 email batch rejection
  - DNS MX resolution and NXDOMAIN/NoAnswer/Timeout behaviors
  - SMTP recipient probe mocking (250 deliverable, 550 bounce, 451 unknown)
  - SMTP timeout and blocked port behavior
  - Verification that SMTP DATA command is NEVER issued
  - CSV export endpoint and structure
  - Status labels consistency check
  - Web UI and health routes
"""

import io
import csv
import json
import pytest
from unittest.mock import patch, MagicMock
import dns.resolver
import dns.exception

from app import app
from checker import (
    validate_format,
    check_dns,
    check_smtp_recipient,
    verify_single_email,
    verify_batch,
    STATUS_DELIVERABLE,
    STATUS_BOUNCE,
    STATUS_UNKNOWN,
    MAX_EMAILS_PER_BATCH
)


@pytest.fixture
def client():
    """Flask test client fixture."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# =====================================================================
# Unit Tests: Step A - Format Validation
# =====================================================================

def test_format_validation_valid():
    """Test standard valid email formats."""
    valid_emails = [
        "user@example.com",
        "first.last@domain.co.uk",
        "alice+tag@company.io",
        "support123@sub.domain.org"
    ]
    for email in valid_emails:
        ok, reason, local, domain = validate_format(email)
        assert ok is True, f"Failed for valid email {email}: {reason}"
        assert local is not None
        assert domain is not None


def test_format_validation_invalid():
    """Test invalid email formats that must be rejected."""
    invalid_emails = [
        "",
        "plainaddress",
        "@missing-local.com",
        "missing-at.domain.com",
        "user@.missing-host.com",
        "user@domain..com",
        "user..name@domain.com",
        "user@domain.c",  # TLD too short (<2 chars)
        "a" * 65 + "@domain.com",  # Local part > 64 chars
        "user@" + "a" * 250 + ".com"  # Total length > 254 chars
    ]
    for email in invalid_emails:
        ok, reason, local, domain = validate_format(email)
        assert ok is False, f"Email '{email}' should be invalid but passed validation."
        assert "Invalid" in reason or "empty" in reason or "exceeds" in reason or "invalid" in reason


# =====================================================================
# Unit Tests: Step B - DNS & MX Resolution (Mocked)
# =====================================================================

@patch("dns.resolver.Resolver.resolve")
def test_dns_mx_found(mock_resolve):
    """Test successful MX record lookup."""
    mock_mx = MagicMock()
    mock_mx.preference = 10
    mock_mx.exchange = "mail.example.com."
    mock_resolve.return_value = [mock_mx]

    ok, primary, hosts, reason = check_dns("example.com")
    assert ok is True
    assert primary == "mail.example.com"
    assert "mail.example.com" in hosts
    assert "Found 1 valid MX" in reason


@patch("dns.resolver.Resolver.resolve")
def test_dns_nxdomain(mock_resolve):
    """Test nonexistent domain returns bounce status."""
    mock_resolve.side_effect = dns.resolver.NXDOMAIN()

    ok, primary, hosts, reason = check_dns("nonexistent-test-domain.org")
    assert ok is False
    assert primary is None
    assert "does not exist (NXDOMAIN)" in reason


@patch("dns.resolver.Resolver.resolve")
def test_dns_no_mx_with_fallback_a_record(mock_resolve):
    """Test RFC 5321 fallback to A record when MX is absent."""
    def side_effect(qname, rdtype):
        if rdtype == "MX":
            raise dns.resolver.NoAnswer()
        elif rdtype == "A":
            mock_a = MagicMock()
            mock_a.address = "192.0.2.1"
            return [mock_a]
        raise dns.resolver.NXDOMAIN()

    mock_resolve.side_effect = side_effect

    ok, primary, hosts, reason = check_dns("fallback.example.com")
    assert ok is True
    assert primary == "fallback.example.com"
    assert "192.0.2.1" in hosts
    assert "fallback A address record exists" in reason


@patch("dns.resolver.Resolver.resolve")
def test_dns_no_mx_no_a_record(mock_resolve):
    """Test domain with neither MX nor A record returns bounce."""
    mock_resolve.side_effect = dns.resolver.NoAnswer()

    ok, primary, hosts, reason = check_dns("no-mail.example.com")
    assert ok is False
    assert "has no MX or address records" in reason


@patch("dns.resolver.Resolver.resolve")
def test_dns_timeout(mock_resolve):
    """Test DNS lookup timeout returns Unknown status."""
    mock_resolve.side_effect = dns.exception.Timeout()

    ok, primary, hosts, reason = check_dns("timeout.example.com")
    assert ok is False
    assert "timed out" in reason


# =====================================================================
# Unit Tests: Step C - Safe SMTP Recipient Verification (Mocked)
# =====================================================================

@patch("smtplib.SMTP")
def test_smtp_deliverable_accepted(mock_smtp_cls):
    """Test SMTP 250 OK yields STATUS_DELIVERABLE."""
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server
    mock_server.connect.return_value = (220, b"mail.example.com ESMTP")
    mock_server.ehlo.return_value = (250, b"OK")
    mock_server.mail.return_value = (250, b"OK")
    mock_server.rcpt.return_value = (250, b"Recipient OK")

    status, reason, details = check_smtp_recipient("valid@example.com", "mail.example.com")
    assert status == STATUS_DELIVERABLE
    assert "accepted recipient verification probe" in reason
    assert details["smtp_response_code"] == 250
    # Crucial security verification: DATA must NEVER be called
    mock_server.data.assert_not_called()
    mock_server.quit.assert_called_once()


@patch("smtplib.SMTP")
def test_smtp_bounce_rejected(mock_smtp_cls):
    """Test SMTP 550 User unknown yields STATUS_BOUNCE."""
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server
    mock_server.connect.return_value = (220, b"mail.example.com ESMTP")
    mock_server.ehlo.return_value = (250, b"OK")
    mock_server.mail.return_value = (250, b"OK")
    mock_server.rcpt.return_value = (550, b"5.1.1 User unknown")

    status, reason, details = check_smtp_recipient("unknown@example.com", "mail.example.com")
    assert status == STATUS_BOUNCE
    assert "rejected recipient address" in reason
    assert details["smtp_response_code"] == 550
    mock_server.data.assert_not_called()


@patch("smtplib.SMTP")
def test_smtp_greylisting_deferral(mock_smtp_cls):
    """Test SMTP 451 temporary deferral yields STATUS_UNKNOWN."""
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server
    mock_server.connect.return_value = (220, b"mail.example.com ESMTP")
    mock_server.ehlo.return_value = (250, b"OK")
    mock_server.mail.return_value = (250, b"OK")
    mock_server.rcpt.return_value = (451, b"4.7.1 Greylisted, try again later")

    status, reason, details = check_smtp_recipient("greylist@example.com", "mail.example.com")
    assert status == STATUS_UNKNOWN
    assert "temporary deferral or greylisting" in reason
    mock_server.data.assert_not_called()


@patch("smtplib.SMTP")
def test_smtp_connection_timeout(mock_smtp_cls):
    """Test SMTP timeout yields STATUS_UNKNOWN."""
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server
    mock_server.connect.side_effect = TimeoutError("Connection timed out")

    status, reason, details = check_smtp_recipient("user@example.com", "mail.example.com")
    assert status == STATUS_UNKNOWN
    assert "timed out on port 25" in reason
    assert details["smtp_checked"] is False


@patch("smtplib.SMTP")
def test_smtp_connection_blocked_os_error(mock_smtp_cls):
    """Test port 25 blocked by OS / hosting provider yields STATUS_UNKNOWN."""
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server
    mock_server.connect.side_effect = OSError("Network is unreachable")

    status, reason, details = check_smtp_recipient("user@example.com", "mail.example.com")
    assert status == STATUS_UNKNOWN
    assert "blocked by network security rules" in reason


def test_smtp_disabled_in_config():
    """Test behavior when SMTP checking is disabled via configuration."""
    with patch("checker.check_dns") as mock_dns:
        mock_dns.return_value = (True, "mail.example.com", ["mail.example.com"], "Found MX")
        result = verify_single_email("user@example.com", allow_smtp=False)
        assert result["status"] == STATUS_UNKNOWN
        assert "SMTP recipient probe is disabled" in result["reason"]
        assert result["smtp_checked"] is False


# =====================================================================
# Unit Tests: Batch Deduplication & Limits
# =====================================================================

def test_batch_deduplication():
    """Test that repeated addresses are deduplicated."""
    emails = ["alice@example.com", "bob@example.com", "alice@example.com", "  alice@example.com  "]
    with patch("checker.verify_single_email") as mock_verify:
        mock_verify.return_value = {
            "email": "dummy",
            "status": STATUS_DELIVERABLE,
            "format_valid": True,
            "domain": "example.com",
            "mx_host": "mail.example.com",
            "mx_records": ["mail.example.com"],
            "reason": "OK",
            "smtp_checked": True
        }
        results, summary = verify_batch(emails)
        assert summary["total"] == 2
        assert len(results) == 2


def test_batch_excessive_limit_rejected():
    """Test that submitting more than 100 unique addresses raises ValueError."""
    many_emails = [f"user{i}@example.com" for i in range(101)]
    with pytest.raises(ValueError) as excinfo:
        verify_batch(many_emails)
    assert f"exceeds maximum limit of {MAX_EMAILS_PER_BATCH}" in str(excinfo.value)


# =====================================================================
# Integration / Flask Endpoint Tests
# =====================================================================

def test_web_ui_renders(client):
    """Test index route renders HTML successfully."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Email Deliverability Checker" in html
    assert "Check Emails" in html
    assert "Download CSV" in html


def test_health_endpoint(client):
    """Test /health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "smtp_verification_enabled" in data


def test_api_check_empty_input(client):
    """Test API rejects empty input."""
    response = client.post("/api/check", json={"emails": ""})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "No email addresses provided" in data["error"]


def test_api_check_excessive_batch(client):
    """Test API rejects more than 100 emails."""
    excessive_list = [f"test{i}@example.com" for i in range(105)]
    response = client.post("/api/check", json={"emails": excessive_list})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "exceeds maximum limit" in data["error"]


@patch("app.verify_batch")
def test_api_check_success(mock_verify_batch, client):
    """Test API returns valid structured response."""
    mock_verify_batch.return_value = (
        [
            {
                "email": "user@example.com",
                "status": STATUS_DELIVERABLE,
                "format_valid": True,
                "domain": "example.com",
                "mx_host": "mail.example.com",
                "mx_records": ["mail.example.com"],
                "reason": "Accepted",
                "smtp_checked": True
            }
        ],
        {"total": 1, "deliverable": 1, "bounce": 0, "unknown": 0}
    )

    response = client.post("/api/check", json={"emails": "user@example.com"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["summary"]["deliverable"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] == STATUS_DELIVERABLE


def test_status_labels_exact():
    """Verify that all classification outcomes strictly match the 3 required names."""
    allowed_statuses = {STATUS_DELIVERABLE, STATUS_BOUNCE, STATUS_UNKNOWN}
    assert allowed_statuses == {"Likely deliverable", "Likely to bounce", "Unknown"}


def test_csv_export_endpoint(client):
    """Test CSV export generates correct columns and data."""
    sample_results = [
        {
            "email": "user1@example.com",
            "status": STATUS_DELIVERABLE,
            "domain": "example.com",
            "mx_host": "mx1.example.com",
            "format_valid": True,
            "smtp_checked": True,
            "reason": "Accepted probe"
        },
        {
            "email": "invalid@",
            "status": STATUS_BOUNCE,
            "domain": None,
            "mx_host": None,
            "format_valid": False,
            "smtp_checked": False,
            "reason": "Invalid syntax"
        }
    ]

    response = client.post("/api/export-csv", json={"results": sample_results})
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment; filename=email_deliverability_report.csv" in response.headers.get("Content-Disposition", "")

    csv_text = response.get_data(as_text=True)
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # Check header row
    assert rows[0] == [
        "Email Address",
        "Deliverability Status",
        "Domain",
        "Primary MX Host",
        "Format Valid",
        "SMTP Checked",
        "Detailed Reason"
    ]
    # Check rows content
    assert rows[1][0] == "user1@example.com"
    assert rows[1][1] == STATUS_DELIVERABLE
    assert rows[2][0] == "invalid@"
    assert rows[2][1] == STATUS_BOUNCE
