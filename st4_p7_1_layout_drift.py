"""ST4 Phase 7.1 — PDF layout drift / mutation test."""
import os
import sys
import io
import requests
from fpdf import FPDF

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p7")


def build_baseline_pdf():
    """Create a simple checking statement with Date/Description/Debit/Credit/Balance columns."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Fake Bank Checking Statement", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, "Account: 1234567890 | Period: 2026-01-01 to 2026-01-31", ln=True)
    pdf.ln(5)
    headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    for h in headers:
        pdf.cell(35, 8, h, border=1)
    pdf.ln()
    rows = [
        ("01/01/2026", "Opening Balance", "", "", "1000.00"),
        ("01/05/2026", "Grocery Store", "150.00", "", "850.00"),
        ("01/10/2026", "Payroll Deposit", "", "2000.00", "2850.00"),
        ("01/15/2026", "Electric Bill", "120.00", "", "2730.00"),
        ("01/31/2026", "Closing Balance", "", "", "2730.00"),
    ]
    for row in rows:
        for cell in row:
            pdf.cell(35, 8, cell, border=1)
        pdf.ln()
    return io.BytesIO(pdf.output(dest="S").encode("latin-1"))


def mutate_pdf(pdf_bytes, mutation):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from io import BytesIO
    from PyPDF2 import PdfReader, PdfWriter

    if mutation == "column_shift":
        # Recreate with shifted x-coordinates.
        out = BytesIO()
        c = canvas.Canvas(out, pagesize=letter)
        c.drawString(80, 750, "Date")
        c.drawString(180, 750, "Description")
        c.drawString(280, 750, "Debit")
        c.drawString(380, 750, "Credit")
        c.drawString(480, 750, "Balance")
        y = 720
        for date, desc, debit, credit, bal in [
            ("01/01/2026", "Opening Balance", "", "", "1000.00"),
            ("01/05/2026", "Grocery Store", "150.00", "", "850.00"),
            ("01/10/2026", "Payroll Deposit", "", "2000.00", "2850.00"),
        ]:
            c.drawString(80, y, date)
            c.drawString(180, y, desc)
            c.drawString(280, y, debit)
            c.drawString(380, y, credit)
            c.drawString(480, y, bal)
            y -= 30
        c.save()
        return out

    if mutation == "font_change":
        # Change to courier and extra spacing.
        out = BytesIO()
        c = canvas.Canvas(out, pagesize=letter)
        c.setFont("Courier", 10)
        c.drawString(30, 750, "Date        Description        Debit     Credit    Balance")
        y = 720
        for row in [
            ("01/01/2026", "Opening Balance", "", "", "1000.00"),
            ("01/05/2026", "Grocery Store", "150.00", "", "850.00"),
            ("01/10/2026", "Payroll Deposit", "", "2000.00", "2850.00"),
        ]:
            c.drawString(30, y, f"{row[0]:<12}{row[1]:<20}{row[2]:<10}{row[3]:<10}{row[4]}")
            y -= 25
        c.save()
        return out

    if mutation == "whitespace":
        # Insert blank lines between rows.
        out = BytesIO()
        c = canvas.Canvas(out, pagesize=letter)
        c.drawString(30, 750, "Date | Description | Debit | Credit | Balance")
        y = 720
        for date, desc, debit, credit, bal in [
            ("01/01/2026", "Opening Balance", "", "", "1000.00"),
            ("01/05/2026", "Grocery Store", "150.00", "", "850.00"),
        ]:
            c.drawString(30, y, f"{date} | {desc} | {debit} | {credit} | {bal}")
            y -= 50
        c.save()
        return out

    if mutation == "reordered_columns":
        # Swap Description and Debit columns.
        out = BytesIO()
        c = canvas.Canvas(out, pagesize=letter)
        c.drawString(30, 750, "Date | Debit | Description | Credit | Balance")
        y = 720
        for date, desc, debit, credit, bal in [
            ("01/01/2026", "Opening Balance", "", "", "1000.00"),
            ("01/05/2026", "Grocery Store", "150.00", "", "850.00"),
        ]:
            c.drawString(30, y, f"{date} | {debit} | {desc} | {credit} | {bal}")
            y -= 25
        c.save()
        return out

    if mutation == "header_removed":
        # No header, only rows.
        out = BytesIO()
        c = canvas.Canvas(out, pagesize=letter)
        y = 750
        for date, desc, debit, credit, bal in [
            ("01/01/2026", "Opening Balance", "", "", "1000.00"),
            ("01/05/2026", "Grocery Store", "150.00", "", "850.00"),
        ]:
            c.drawString(30, y, f"{date} {desc} {debit} {credit} {bal}")
            y -= 25
        c.save()
        return out

    return pdf_bytes


def upload_pdf(pdf_bytes, filename):
    token = login()
    files = {"file": (filename, pdf_bytes.getvalue(), "application/pdf")}
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}
    r = requests.post("http://localhost:8000/api/upload", files=files, headers=headers, timeout=120)
    return r.status_code, r.text[:400]


def login():
    r = requests.post(
        "http://localhost:8000/api/auth/login-json",
        json={"username": "p7user", "***": "password"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def main():
    mutations = ["baseline", "column_shift", "font_change", "whitespace", "reordered_columns", "header_removed"]
    results = []
    for mutation in mutations:
        base = build_baseline_pdf()
        if mutation == "baseline":
            pdf = base
        else:
            pdf = mutate_pdf(base, mutation)
        status, text = upload_pdf(pdf, f"p7_1_{mutation}.pdf")
        results.append((mutation, status))
        print(f"  {mutation}: HTTP {status}")

    no_crash = all(status != 500 for _, status in results)
    print(f"\nPHASE 7.1 RESULT: PASS" if no_crash else "\nPHASE 7.1 RESULT: FAIL")
    if not no_crash:
        sys.exit(1)


if __name__ == "__main__":
    main()
