from fpdf import FPDF


class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 116, 139)
        self.cell(0, 8, "Software Development Course Project - Email Deliverability Checker", border=0, align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def build_pdf(filename="Email_Deliverability_Checker_Submission.pdf"):
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 10, "Email Deliverability Checker", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, "Software Development Course Project - Assignment Submission", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_font("Helvetica", "", 9)

    meta = [
        ("Project Title:", "Email Deliverability Checker"),
        ("Course / Assignment:", "Software Development Course Project"),
        ("Live Application URL:", "[Pending Deployment - e.g., https://email-deliverability-checker.onrender.com]"),
        ("GitHub Repository URL:", "[Pending Publication - e.g., https://github.com/<username>/email-deliverability-checker]"),
        ("Tech Stack:", "Python 3.12, Flask, dnspython, Gunicorn, Vanilla JS, CSS3, HTML5")
    ]

    for label, val in meta:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(48, 7, label, border=1, fill=True)
        pdf.set_font("Helvetica", "" if "[" not in val else "I", 9)
        if "[" in val:
            pdf.set_text_color(194, 65, 12)
        else:
            pdf.set_text_color(51, 65, 85)
        pdf.cell(142, 7, f" {val}", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 8, "1. Project Summary", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(15, 23, 42)
    summary_text = (
        "I built this Email Deliverability Checker to help users check whether an email list is safe to send "
        "to without actually sending test emails or using paid third-party APIs. Users can paste up to 100 emails at a time. "
        "The application cleans duplicate entries, checks email syntax, resolves domain MX records through DNS, and "
        "attempts a safe SMTP handshake.\n\n"
        "To avoid misleading users, results are categorized into three realistic statuses: 'Likely deliverable', "
        "'Likely to bounce', and 'Unknown'. All processing happens in memory without storing emails in any database."
    )
    pdf.multi_cell(0, 5, summary_text)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 8, "2. Main Features", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(15, 23, 42)
    features = [
        "- Multi-step checking: Regex syntax validation, dnspython for MX/A lookups, and socket SMTP probes.",
        "- No actual emails sent: Probes only up to recipient check and quits immediately (never issues DATA).",
        "- Clean responsive UI: Vanilla JavaScript, modern CSS, dynamic status badges, summary count cards, and search filtering.",
        "- Deduplication and limits: Automatically deduplicates lists and enforces a 100-email safety limit.",
        "- CSV download: One-click export of verified results into a clean CSV report."
    ]
    for feat in features:
        pdf.cell(0, 5, feat, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 8, "3. Deliverability Statuses", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(79, 70, 229)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(40, 7, "Status", border=1, fill=True)
    pdf.cell(75, 7, "Technical Check", border=1, fill=True)
    pdf.cell(75, 7, "Meaning", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    categories = [
        ("Likely deliverable", "Valid syntax, working MX records, and SMTP 250 OK accepted.", "Likely active mailbox (though spam filters still apply)."),
        ("Likely to bounce", "Malformed syntax, NXDOMAIN, or SMTP 550 rejection.", "Address is broken or rejected. High risk of bounce."),
        ("Unknown", "Valid MX exists, but server hides status, greylists, or port 25 blocked.", "Mailbox status cannot be confirmed without sending.")
    ]

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(15, 23, 42)
    for cat, crit, interp in categories:
        pdf.cell(40, 6, cat, border=1)
        pdf.cell(75, 6, crit, border=1)
        pdf.cell(75, 6, interp, border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 8, "4. Limitations & Cloud Hosting Realities", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(15, 23, 42)
    limitations = (
        "- Catch-All Servers: Many enterprise systems accept all addresses at the gate and drop invalid ones later.\n"
        "- Status Concealment: Providers like Outlook and Yahoo conceal mailbox status to block address scraping.\n"
        "- Cloud Port 25 Blocking: Free cloud tiers like Render block outbound port 25. The app safely degrades to "
        "checking DNS MX records and marking addresses as 'Unknown' with an explanation."
    )
    pdf.multi_cell(0, 5, limitations)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 8, "5. Automated Testing", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 5, "Automated test suite using pytest: 22 tests passing with 100% mocked DNS and SMTP.", new_x="LMARGIN", new_y="NEXT")

    pdf.output(filename)
    print(f"Generated PDF at: {filename}")


if __name__ == "__main__":
    build_pdf()
