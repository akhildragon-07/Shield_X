# Email Deliverability Checker

A web app built with Python (Flask) and vanilla JavaScript to check whether a list of email addresses is likely deliverable, likely to bounce, or unknown. 

I built this for my Software Development project. The goal is to let users paste up to 100 email addresses, clean duplicates, check their formatting, resolve their mail servers using DNS MX records, and optionally test the mail server handshake without ever sending an actual email message.

---

## Features

- **No spam / No emails sent**: The checker only talks to mail servers up to the recipient check (`RCPT TO`) and quits immediately. It never issues `DATA` and never sends anything.
- **Bulk check**: Accepts up to 100 emails at once (one per line, or separated by commas/semicolons).
- **Automatic deduplication**: Strips whitespace and removes repeated addresses before checking.
- **Multi-step validation**:
  - Regex syntax validation
  - DNS MX record lookup (with fallback to domain A records)
  - Safe SMTP connection check
- **Three clear categories**:
  - **Likely deliverable** (green)
  - **Likely to bounce** (red)
  - **Unknown** (amber)
- **Detailed diagnostic reasons**: Explains exactly why an address was classified into its status.
- **Search and filters**: Filter by status pill (All, Deliverable, Bounce, Unknown) or search by email string.
- **CSV export**: Download your checked list as a clean `.csv` file.
- **Privacy friendly**: Everything runs in memory. Nothing is stored in a database or written to disk logs.

---

## Tech Stack

- **Backend**: Python 3.12, Flask
- **DNS Lookups**: `dnspython`
- **Network / Mail checks**: Python standard library (`smtplib`, `socket`, `concurrent.futures`)
- **Frontend**: HTML5, CSS3 (responsive grid & flexbox), Vanilla JavaScript (no external JS libraries)
- **Production Server**: Gunicorn
- **Testing**: pytest
- **Deployment**: Render

---

## How It Works

Each submitted address goes through four stages:

1. **Format Validation**: Checks if the address follows standard `user@domain.tld` structure, doesn't exceed length limits (max 64 chars for local part, max 254 chars total), and has a valid domain. If syntax is broken, it immediately flags it as **Likely to bounce**.
2. **DNS & MX Lookup**: Uses `dnspython` to query the domain's MX records.
   - If the domain doesn't exist (`NXDOMAIN`), it marks it as **Likely to bounce**.
   - If there are no MX records, it checks for fallback address records (`A` records) according to RFC 5321. If neither exists, it marks it as **Likely to bounce**.
   - If DNS times out or has temporary errors, it marks it as **Unknown**.
3. **SMTP Handshake Check (Optional)**: If enabled, it connects to the primary MX host on port 25, says `EHLO`, sets `MAIL FROM: <>`, and checks `RCPT TO: <target>`.
   - If the server returns `250` or `251`, it's marked **Likely deliverable**.
   - If the server returns a hard rejection like `550 User unknown`, it's marked **Likely to bounce**.
   - If the server returns temporary deferrals (like `451` for greylisting), times out, or the connection is blocked, it's marked **Unknown**.
   - It always sends `QUIT` and closes the connection. **It never sends `DATA`.**
4. **Classification**: The results are compiled with a human-readable reason and returned to the UI.

---

## What the 3 Statuses Mean

- **Likely deliverable**: The format is good, MX records exist, and the mail server acknowledged that it accepts the recipient. Note: This isn't a 100% guarantee that the email will hit the inbox, because spam filters and inbox storage quotas still apply.
- **Likely to bounce**: The address is malformed, the domain doesn't exist, has no mail servers, or the mail server explicitly rejected the address. You should avoid sending to these.
- **Unknown**: The domain exists and has mail servers, but we cannot confirm whether the specific mailbox exists. This happens when mail servers hide recipient status, greylist connections, or when outbound port 25 is blocked by hosting.

---

## Accuracy Limitations & Why Mailbox Checks Can Be "Unknown"

It's technically impossible for any verification tool to guarantee 100% deliverability without actually sending an email. Here is why:

- **Catch-All (Accept-All) servers**: Many corporate mail servers are configured to accept every address at the perimeter (`250 OK`), and then discard or silently bounce invalid ones internally.
- **Anti-spam concealment**: Major providers (like Yahoo, Microsoft Outlook, and iCloud) deliberately don't disclose whether a mailbox exists to unknown IPs to stop spammers from scraping valid emails.
- **Greylisting**: Some servers temporarily reject the first connection attempt with a 4xx error code, asking the sender to retry in a few minutes.
- **Port 25 block on cloud hosts**: Cloud platforms like Render, AWS, and Heroku block outbound traffic on port 25 to prevent abuse.

---

## Note on Free Hosting & Port 25 (Render)

Free cloud platforms (including Render) block outbound SMTP port 25 connections by default. 

When running on Render:
- Syntax checks work completely.
- DNS MX lookups work completely (identifying dead domains, valid domains, mail servers).
- Because port 25 is firewalled by the host, the SMTP check safely degrades: valid domains are classified as **Unknown** with an explanation that the host blocks port 25, rather than giving fake bounce errors.

---

## Local Setup

### Requirements
- Python 3.11+
- Git

### On Windows
```powershell
# Clone the repository
git clone https://github.com/<your-username>/email-deliverability-checker.git
cd email-deliverability-checker

# Set up virtual environment
python -m venv venv
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Run the app
python app.py
```

### On macOS / Linux
```bash
# Clone the repository
git clone https://github.com/<your-username>/email-deliverability-checker.git
cd email-deliverability-checker

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run the app
python app.py
```

Once running, open your browser and go to:
`http://localhost:5000`

---

## Running the Tests

To run the automated test suite with pytest:

```bash
pytest -v tests/test_app.py
```

All 22 unit and integration tests run with mocked DNS and SMTP calls so they don't depend on external network connections.

---

## How to Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit of email deliverability checker"
git branch -M main
git remote add origin https://github.com/<your-username>/email-deliverability-checker.git
git push -u origin main
```

---

## Deploying to Render

1. Push your code to a public GitHub repo.
2. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
3. Select your repository.
4. Set the following settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Environment Variable**: `ENABLE_SMTP_CHECK` = `false` (recommended for Render since port 25 is blocked)
5. Click **Deploy**.

Alternatively, you can use the included `render.yaml` Blueprint file.

---

## Environment Variables

| Variable | Default | What it does |
|---|---|---|
| `PORT` | `5000` | Port for the web server to bind to. |
| `ENABLE_SMTP_CHECK` | `true` | Set to `false` on cloud hosts like Render to skip port 25 connection attempts. |
| `SECRET_KEY` | `dev-secret-key-12345` | Flask secret key for sessions. |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode for local testing. |

---

## Privacy Note

This tool is built strictly for list cleaning and testing. It does not store submitted email addresses in any database, does not keep persistent logs of user inputs, and never sends actual email content.
