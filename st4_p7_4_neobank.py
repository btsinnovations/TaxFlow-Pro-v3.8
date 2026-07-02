"""ST4 Phase 7.4 — Unknown neobank / generic fallback test."""
import os
import sys
import io
import requests
from fpdf import FPDF


def build_neobank_pdf():
    """Create a statement from 'NeoBank X' with no known institution markers."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "NeoBank X — Account Summary", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, "Customer: Anonymous | Account: X-999-0001", ln=True)
    pdf.cell(0, 8, "Period: 2026-01-01 to 2026-01-31", ln=True)
    pdf.ln(5)
    headers = ["When", "What", "Out", "In", "Running Total"]
    for h in headers:
        pdf.cell(35, 8, h, border=1)
    pdf.ln()
    rows = [
        ("2026-01-01", "Start", "", "", "1000.00"),
        ("2026-01-05", "Coffee", "5.00", "", "995.00"),
        ("2026-01-10", "Salary", "", "2500.00", "3495.00"),
        ("2026-01-20", "Rent", "1200.00", "", "2295.00"),
        ("2026-01-31", "End", "", "", "2295.00"),
    ]
    for row in rows:
        for cell in row:
            pdf.cell(35, 8, cell, border=1)
        pdf.ln()
    raw = pdf.output(dest="S")
    return io.BytesIO(raw.encode("latin-1"))


def login():
    r = requests.post(
        "http://127.0.0.1:8000/api/auth/login-json",
        json={"username": "p7user", "***": "password"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def upload_pdf(pdf_bytes, filename):
    token = login()
    files = {"file": (filename, pdf_bytes.getvalue(), "application/pdf")}
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}
    r = requests.post("http://127.0.0.1:8000/api/upload", files=files, headers=headers, timeout=120)
    return r.status_code, r.text[:500]


def main():
    pdf = build_neobank_pdf()
    status, text = upload_pdf(pdf, "p7_4_neobank.pdf")
    print(f"  Neobank upload: HTTP {status}")
    if status == 500:
        print("\nPHASE 7.4 RESULT: FAIL (unknown institution caused 500)")
        sys.exit(1)
    print("\nPHASE 7.4 RESULT: PASS (unknown institution handled without crash)")


if __name__ == "__main__":
    main()
