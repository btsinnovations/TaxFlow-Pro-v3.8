#!/usr/bin/env python3
"""Generate Symitar CU (Navy Federal) test fixture with correct closing balance."""

from fpdf import FPDF
import os

class SymitarPDF(FPDF):
    def header(self):
        pass

def generate_symitar(output_dir: str = "tests/fixtures") -> str:
    os.makedirs(output_dir, exist_ok=True)
    pdf = SymitarPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Courier", "", 10)

    pdf.cell(0, 8, "Navy Federal Credit Union", ln=True, align="C")
    pdf.cell(0, 6, "P.O. Box 3000, Merrifield, VA 22119-3000", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Courier", "", 9)
    pdf.cell(0, 5, "Account Summary", ln=True)
    pdf.cell(0, 5, "Account Number: ****1234", ln=True)
    pdf.cell(0, 5, "Statement Period: 05/01/2026 - 05/31/2026", ln=True)
    pdf.ln(4)

    pdf.set_font("Courier", "B", 9)
    pdf.cell(25, 6, "Date", border=0)
    pdf.cell(70, 6, "Description", border=0)
    pdf.cell(35, 6, "Withdrawal", border=0, align="R")
    pdf.cell(35, 6, "Deposit", border=0, align="R")
    pdf.cell(25, 6, "Balance", border=0, align="R")
    pdf.ln(6)
    pdf.set_font("Courier", "", 9)

    transactions = [
        ("05/01/2026", "Beginning Balance", "", "", "5250.00"),
        ("05/02/2026", "DFAS BAH HOUSING ALLOWANCE", "", "1850.00", "7100.00"),
        ("05/03/2026", "SHELL OIL STATION", "45.67", "", "7054.33"),
        ("05/05/2026", "PAYROLL - DIRECT DEPOSIT", "", "3200.00", "10254.33"),
        ("05/07/2026", "STARBUCKS COFFEE", "6.42", "", "10247.91"),
        ("05/10/2026", "TREAS 310 XXVA BENEFITS", "", "2150.00", "12397.91"),
        ("05/12/2026", "COURTESY PAY FEE", "35.00", "", "12362.91"),
        ("05/15/2026", "DIVIDEND PAYMENT", "", "12.50", "12375.41"),
        ("05/18/2026", "WALMART SUPERCENTER", "127.83", "", "12247.58"),
        ("05/20/2026", "ZELLE FROM JOHN DOE", "", "250.00", "12497.58"),
        ("05/22/2026", "GEICO AUTO INSURANCE", "145.00", "", "12352.58"),
        ("05/25/2026", "NETFLIX.COM", "15.99", "", "12336.59"),
        ("05/28/2026", "COURTESY PAY FEE", "35.00", "", "12301.59"),
        ("05/31/2026", "Ending Balance", "", "", "12301.59"),
    ]

    for date, desc, withdrawal, deposit, balance in transactions:
        pdf.cell(25, 5, date, border=0)
        pdf.cell(70, 5, desc[:34], border=0)
        pdf.cell(35, 5, f"${withdrawal}" if withdrawal else "", border=0, align="R")
        pdf.cell(35, 5, f"${deposit}" if deposit else "", border=0, align="R")
        pdf.cell(25, 5, f"${balance}", border=0, align="R")
        pdf.ln(5)

    out = os.path.join(output_dir, "sample_statement.pdf")
    pdf.output(out)
    print(f"[OK] Generated {out}")
    return out

if __name__ == "__main__":
    generate_symitar()
