#!/usr/bin/env python3
"""Generate Big Bank (Chase/BofA) test fixture with correct closing balance."""

from fpdf import FPDF
import os

class BigBankPDF(FPDF):
    def header(self):
        pass

def generate_big_bank(output_dir: str = "tests/fixtures") -> str:
    os.makedirs(output_dir, exist_ok=True)
    pdf = BigBankPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Courier", "", 10)

    pdf.cell(0, 8, "JPMorgan Chase Bank, N.A.", ln=True, align="C")
    pdf.cell(0, 6, "Chase Total Checking", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Courier", "", 9)
    pdf.cell(0, 5, "Account Summary", ln=True)
    pdf.cell(0, 5, "Account Number: ****5678", ln=True)
    pdf.cell(0, 5, "Statement Period: 06/01/2026 - 06/30/2026", ln=True)
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
        ("06/01/2026", "Beginning Balance", "", "", "12450.00"),
        ("06/02/2026", "AMAZON.COM", "127.83", "", "12322.17"),
        ("06/03/2026", "SALARY DEPOSIT", "", "3200.00", "15522.17"),
        ("06/05/2026", "SHELL OIL", "45.67", "", "15476.50"),
        ("06/07/2026", "STARBUCKS", "6.42", "", "15470.08"),
        ("06/08/2026", "IRS TAX REFUND", "", "850.00", "16320.08"),
        ("06/10/2026", "BEST BUY", "249.99", "", "16070.09"),
        ("06/12/2026", "COURTESY PAY FEE", "35.00", "", "16035.09"),
        ("06/15/2026", "ZELLE PAYMENT", "250.00", "", "15785.09"),
        ("06/17/2026", "WHOLE FOODS", "89.47", "", "15695.62"),
        ("06/18/2026", "INTEREST EARNED", "", "2.50", "15698.12"),
        ("06/20/2026", "GEICO INSURANCE", "145.00", "", "15553.12"),
        ("06/22/2026", "NETFLIX", "15.99", "", "15537.13"),
        ("06/25/2026", "TARGET", "75.55", "", "15461.58"),
        ("06/28/2026", "COURTESY PAY FEE", "35.00", "", "15426.58"),
        ("06/30/2026", "Ending Balance", "", "", "15426.58"),
    ]

    for date, desc, withdrawal, deposit, balance in transactions:
        pdf.cell(25, 5, date, border=0)
        pdf.cell(70, 5, desc[:34], border=0)
        pdf.cell(35, 5, f"${withdrawal}" if withdrawal else "", border=0, align="R")
        pdf.cell(35, 5, f"${deposit}" if deposit else "", border=0, align="R")
        pdf.cell(25, 5, f"${balance}", border=0, align="R")
        pdf.ln(5)

    out = os.path.join(output_dir, "sample_big_bank.pdf")
    pdf.output(out)
    print(f"[OK] Generated {out}")
    return out

if __name__ == "__main__":
    generate_big_bank()
