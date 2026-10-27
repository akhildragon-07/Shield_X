# Email Deliverability Checker

A modern, privacy-first, non-intrusive web application built with Python Flask and Vanilla JavaScript to inspect email deliverability risk and classify addresses without sending actual emails.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Key Features](#key-features)
3. [Technology Stack](#technology-stack)
4. [How the Checking Logic Works](#how-the-checking-logic-works)
5. [Deliverability Classifications](#deliverability-classifications)
6. [Accuracy Limitations & Industry Realities](#accuracy-limitations--industry-realities)
7. [Why Mailbox Verification Returns "Unknown"](#why-mailbox-verification-returns-unknown)
8. [Free Hosting & Port 25 Blocking](#free-hosting--port-25-blocking)
9. [Local Installation Guide](#local-installation-guide)
10. [Running the Application and Tests](#running-the-application-and-tests)
11. [GitHub Publishing Instructions](#github-publishing-instructions)
12. [Render Deployment Guide](#render-deployment-guide)
13. [Environment Variables](#environment-variables)
14. [Privacy & Responsible Use Policy](#privacy--responsible-use-policy)

---

## 1. Project Overview

The **Email Deliverability Checker** is a full-stack software development project designed to analyze bulk email lists (up to 100 unique addresses per batch) and evaluate whether emails are likely to reach an inbox or bounce.

### Critical Safety Guarantee
> **NEVER SENDS ACTUAL EMAILS:** The application strictly forbids issuing the SMTP `DATA` command, avoids mailing campaigns, and does not integrate with bulk-sending services. Verification probes only test the envelope handshake (`EHLO` &rarr; `MAIL FROM` &rarr; `RCPT TO` &rarr; `QUIT`) and safely terminate.

---

## 2. Key Features

- **Modern & Responsive UI**: Clean, accessible white/indigo layout with real-time counters, responsive data tables, and mobile support.
- **Batch Processing**: Evaluates up to 100 deduplicated addresses concurrently using a bounded thread pool.
- **Multi-Stage Verification Pipeline**:
  - RFC 5322 syntax and format inspection
  - Authoritative DNS MX record queries and RFC 5321 fallback resolution
  - Conservative SMTP recipient probes
- **Live Filtering & Instant Search**: Filter table results by status (Deliverable, Bounce, Unknown) or search by email string.
- **CSV Data Export**: One-click download of timestamped evaluation reports (`.csv`) via client or backend API.
- **Educational Explanations**: Every evaluated address includes a transparent reason code explaining why the classification was made.
- **Zero-Storage Privacy**: No database, no logging of user-submitted email addresses, completely stateless in-memory execution.

---

## 3. Technology Stack

- **Backend**: Python 3.11+ / 3.12, [Flask](https://flask.palletsprojects.com/)
- **DNS Resolution**: [dnspython](https://www.dnspython.org/)
- **Network / Mail Protocol**: Python standard library `smtplib`, `socket`, `concurrent.futures`
- **Frontend**: Semantic HTML5, Custom Modern CSS3 (Flexbox & Grid), Vanilla JavaScript (ES6+, zero third-party JS dependencies)
- **Production Server**: [Gunicorn](https://gunicorn.org/)
- **Testing**: [pytest](https://docs.pytest.org/) with unittest mocking
- **Cloud Deployment**: [Render](https://render.com/) via `render.yaml` Blueprint

---

## 4. How the Checking Logic Works

Every email undergoes a four-step inspection funnel:

```
[User Input (Max 100)] 
       │
       ▼
 [Deduplication]
       │
       ▼
 [Step A: Format Validation] ──(Invalid)──► [Likely to bounce]
       │ (Valid)
       ▼
 [Step B: DNS & MX Lookup] ────(NXDOMAIN/No MX)──► [Likely to bounce]
       │ (MX Found)
       ▼
 [Step C: SMTP Recipient Probe] 
       ├─► (Port 25 blocked / Timeout) ──► [Unknown]
       ├─► (Server 250 OK) ──────────────► [Likely deliverable]
       ├─► (Server 550 Rejected) ────────► [Likely to bounce]
       └─► (Greylisting / 4xx) ──────────► [Unknown]
```

### Step A: Format Validation
Inspects RFC compliance: verifies `@` symbol, local-part ($\le 64$ characters), overall length ($\le 254$ characters), valid domain characters, and top-level domain format. Malformed strings are classified as **Likely to bounce**.

### Step B: DNS and Mail-Server Checks
Uses `dnspython` to query authoritative nameservers for MX records:
- **MX Records Present**: Resolves the priority-ranked list of mail exchanger hosts.
- **Null MX (RFC 7505)**: If the domain advertises `0 .`, the domain explicitly rejects mail &rarr; **Likely to bounce**.
- **No MX Record**: Follows RFC 5321 fallback rules by querying `A` or `AAAA` records. If none exist &rarr; **Likely to bounce**.
- **Non-existent Domain (NXDOMAIN)**: Domain is unregistered &rarr; **Likely to bounce**.
- **DNS Timeout / Temporary Error**: Classified as **Unknown**.

### Step C: Optional SMTP Recipient Verification
When enabled and network permissions allow:
1. Connects to the primary MX host on TCP port 25 with a short socket timeout (3.5 seconds).
2. Performs greeting (`EHLO validator.local`).
3. Sets envelope sender (`MAIL FROM:<>` or `<check@validator.local>`).
4. Issues `RCPT TO:<email>`.
5. Records the response code and immediately terminates with `QUIT`.
6. **NEVER executes `DATA`**.

### Step D: Result Classification
- **Likely deliverable**: Mail server accepted the recipient probe (Status 250/251).
- **Likely to bounce**: Syntax invalid, NXDOMAIN, no mail exchanger, or server returned permanent rejection (Status 550-554).
- **Unknown**: Connection blocked, timeout, greylisting (4xx), catch-all configuration, or SMTP verification disabled.

---

## 5. Deliverability Classifications

| Status Badge | Color | Technical Meaning | Practical Advice |
| :--- | :--- | :--- | :--- |
| **Likely deliverable** | 🟢 Green | Mail server acknowledged recipient address during handshake. | Highly likely to accept mail, though subject to spam filters. |
| **Likely to bounce** | 🔴 Red | Syntax error, dead domain, or mail server explicitly refused mailbox. | Remove from mailing list immediately to prevent reputation damage. |
| **Unknown** | 🟡 Amber | Domain has mail servers, but mailbox existence could not be confirmed. | Send double opt-in confirmation or verify through alternate channels. |

---

## 6. Accuracy Limitations & Industry Realities

No email verification tool can achieve 100% accuracy without actually delivering a message. Key reasons include:
1. **Catch-All (Accept-All) Servers**: Many corporate domains accept all recipient addresses at the perimeter gate, only to drop or bounce nonexistent mailboxes internally later.
2. **False Positives/Negatives**: Anti-spam firewalls (Proofpoint, Mimecast, Barracuda) frequently respond with generic `250 OK` to prevent address harvesting (Directory Harvest Attacks).
3. **Inbox Quota & Filtering**: An address may exist on the server but still bounce due to a full mailbox quota or stringent sender reputation policies (SPF/DKIM/DMARC).

---

## 7. Why Mailbox Verification Returns "Unknown"

When an address is marked **Unknown**, it is not an error in the tool; it is an honest, conservative technical classification:
- **Concealed Mailbox Status**: Providers like Yahoo, Microsoft (Outlook/Hotmail), and Apple iCloud deliberately withhold mailbox existence info from unknown IP addresses.
- **Greylisting**: The server temporarily refuses the probe with code `451` or `421`, asking legitimate mailers to retry later.
- **Port 25 Blocking**: Cloud hosts and ISPs block outbound port 25 to prevent spam abuse.

---

## 8. Free Hosting & Port 25 Blocking

Major cloud providers (including **Render**, **Heroku**, **AWS EC2**, and **DigitalOcean**) block outbound connections on TCP port 25 on their public and free tiers.

### What the Application Can and Cannot Verify on Cloud Hosting:
- **What Works Perfectly on Render**:
  - Full syntax and format validation
  - Full DNS MX record resolution
  - NXDOMAIN detection (identifying dead or bogus domains)
  - RFC 5321 fallback address resolution
  - Batching, reporting, and CSV export
- **What Degrades Gracefully**:
  - Recipient-level mailbox existence (`RCPT TO`). Because port 25 is blocked by Render's firewall, domains with valid MX records are classified transparently as **Unknown** (with an explanation note), preventing false positive bounces.

---

## 9. Local Installation Guide

### Prerequisites
- Python 3.11 or newer
- Git

### Windows Installation
```powershell
# 1. Clone repository
git clone https://github.com/<your-username>/email-deliverability-checker.git
cd email-deliverability-checker

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### macOS / Linux Installation
```bash
# 1. Clone repository
git clone https://github.com/<your-username>/email-deliverability-checker.git
cd email-deliverability-checker

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 10. Running the Application and Tests

### Run the Web Server Locally
```bash
python app.py
```
Open your browser and navigate to:
```
http://localhost:5000
```

### Run Automated Tests
```bash
pytest -v tests/test_app.py
```
All 22 unit and integration tests will execute, validating formatting, DNS parsing, SMTP probing, limits, and CSV generation with 100% mocked dependencies.

---

## 11. GitHub Publishing Instructions

Follow these exact steps to publish this project to GitHub:

```bash
# 1. Initialize git repository if not already done
git init

# 2. Add all project files
git add .

# 3. Create initial commit
git commit -m "Initial commit: Email Deliverability Checker web application"

# 4. Create repository on GitHub named: email-deliverability-checker
# (Ensure it is Public)

# 5. Link remote and push
git branch -M main
git remote add origin https://github.com/<your-username>/email-deliverability-checker.git
git push -u origin main
```

---

## 12. Render Deployment Guide

### Option 1: Blueprint Deployment via `render.yaml` (Recommended)
1. Push your repository to GitHub.
2. Sign in to [Render](https://dashboard.render.com/).
3. Click **New +** and select **Blueprint**.
4. Connect your `email-deliverability-checker` repository.
5. Render reads `render.yaml` automatically and configures the service.
6. Click **Apply**.

### Option 2: Manual Web Service Setup
1. On Render Dashboard, click **New +** &rarr; **Web Service**.
2. Select your repository.
3. Configure settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Environment Variables**:
     - `ENABLE_SMTP_CHECK`: `false` (recommended on Render free tier due to port 25 block)
4. Click **Deploy Web Service**.

---

## 13. Environment Variables

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `PORT` | `5000` | Port on which the HTTP server listens. Automatically supplied by Render. |
| `ENABLE_SMTP_CHECK` | `true` (local) / `false` (Render) | When `false`, skips port 25 connection attempts and reports valid MX as Unknown. |
| `SECRET_KEY` | Auto-generated | Flask session and cryptographic secret. |
| `FLASK_DEBUG` | `false` | Enables Flask debug mode (use only during local development). |

---

## 14. Privacy & Responsible Use Policy

- **No Data Retention**: User email lists are never saved to a database, persistent store, or browser storage.
- **Privacy Logs**: System logs record only the count of processed emails (e.g. `Processing batch of 5 items`), never the user-submitted email addresses.
- **Non-Harassment**: The tool is designed solely for list hygiene and academic demonstration. Indefinite retries and automated brute-force probing are strictly disabled.
- **No Spam Transmission**: The application cannot send emails; it operates exclusively as an envelope diagnostic utility.
