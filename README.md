# Email Deliverability Checker

A lightweight web app built with Python (Flask) and vanilla JavaScript to check email deliverability without sending actual emails.

Paste up to 100 email addresses to find out if they are **Likely deliverable**, **Likely to bounce**, or **Unknown**.

---

## How It Works

1. **Format Check**: Validates standard `user@domain.tld` syntax and length constraints via regex.
2. **DNS & MX Lookup**: Queries domain MX records using `dnspython` (with fallback to `A` address records). Nonexistent domains (`NXDOMAIN`) or domains with no mail records are flagged as likely to bounce.
3. **Safe SMTP Handshake**: Connects to the mail server on port 25, runs `EHLO`, sets `MAIL FROM: <>`, and checks `RCPT TO: <target>`. It records the server code and terminates immediately with `QUIT`. **It never issues `DATA` or sends email.**
4. **Classification**:
   - **Likely deliverable**: Server accepted the recipient (`250 OK`).
   - **Likely to bounce**: Invalid syntax, dead domain, or server rejected recipient (`550`).
   - **Unknown**: Mail server hides mailbox status, greylisting, connection timed out, or outbound port 25 is blocked.

> **Note on Free Cloud Hosting (Render):** Render, Heroku, and AWS free tier block outbound port 25. On these hosts, the app still verifies syntax and resolves DNS MX records, but safely marks domains with active mail servers as **Unknown** instead of giving false bounce errors.

---

## How to Run Locally

### 1. Clone & Set Up
```bash
git clone https://github.com/akhildragon-07/Shield_X
cd email-deliverability-checker

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start the App
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## Running Tests

Run the test suite using `pytest`:

```bash
pytest -v tests/test_app.py
```

All 22 unit and integration tests use mocked DNS and SMTP calls and run completely offline.

---

## Deployment (Render)

1. Push your code to GitHub.
2. In [Render](https://dashboard.render.com/), create a new **Web Service** linked to your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Environment variable: Set `ENABLE_SMTP_CHECK` to `false` (since Render blocks port 25).
