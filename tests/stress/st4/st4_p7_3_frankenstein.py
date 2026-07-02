"""ST4 Phase 7.3 — Frankenstein PDF: mixed accounts and junk pages."""
import os
import sys
import io
import requests
from fpdf import FPDF


def build_frankenstein_pdf():
    pdf = FPDF()

    # 2 marketing pages
    for i in range(2):
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"Marketing Page {i+1}", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, "Special offers, disclaimers, and promotional content. Not financial data.")

    # 5 checking account pages
    for i in range(5):
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Checking Account - Page {i+1}", ln=True)
        pdf.set_font("Arial", "", 10)
        headers = ["Date", "Description", "Debit", "Credit", "Balance"]
        for h in headers:
            pdf.cell(35, 8, h, border=1)
        pdf.ln()
        for j in range(10):
            pdf.cell(35, 8, f"01/{j+1:02d}/2026", border=1)
            pdf.cell(35, 8, f"Txn {i*10+j+1}", border=1)
            pdf.cell(35, 8, "10.00", border=1)
            pdf.cell(35, 8, "", border=1)
            pdf.cell(35, 8, f"{1000 - (i*10+j+1)*10:.2f}", border=1)
            pdf.ln()

    # 1 T&C page
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Terms and Conditions", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 8, "These terms govern your use of Fake Bank services. No transaction data on this page.")

    # 4 savings account pages
    for i in range(4):
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Savings Account - Page {i+1}", ln=True)
        pdf.set_font("Arial", "", 10)
        headers = ["Date", "Description", "Debit", "Credit", "Balance"]
        for h in headers:
            pdf.cell(35, 8, h, border=1)
        pdf.ln()
        for j in range(8):
            pdf.cell(35, 8, f"01/{j+1:02d}/2026", border=1)
            pdf.cell(35, 8, f"Savings Txn {i*8+j+1}", border=1)
            pdf.cell(35, 8, "", border=1)
            pdf.cell(35, 8, "25.00", border=1)
            pdf.cell(35, 8, f"{500 + (i*8+j+1)*25:.2f}", border=1)
            pdf.ln()

    return io.BytesIO(bytes(pdf.output()))


def login():
    r = requests.post(
        "http://127.0.0.1:8010/api/auth/login-json",
        json={"username": "p7user", "password": "password"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def upload_pdf(pdf_bytes, filename):
    token = login()
    files = {"file": (filename, pdf_bytes.getvalue(), "application/pdf")}
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}
    r = requests.post("http://127.0.0.1:8010/api/upload?account_id=1", files=files, headers=headers, timeout=180)
    return r.status_code, r.text[:500]


def main():
    pdf = build_frankenstein_pdf()
    status, text = upload_pdf(pdf, "p7_3_frankenstein.pdf")
    print(f"  Frankenstein upload: HTTP {status}")
    if status == 500:
        print("\nPHASE 7.3 RESULT: FAIL")
        sys.exit(1)
    print("\nPHASE 7.3 RESULT: PASS (mixed-content PDF parsed without crash)")


if __name__ == "__main__":
    main()
