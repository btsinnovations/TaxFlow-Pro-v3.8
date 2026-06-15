#!/usr/bin/env python3
"""
Generate test PDF fixtures for defunct institutions (graveyard templates).
Requires: fpdf2  (pip install fpdf2)
"""

import os
from fpdf import FPDF
from pathlib import Path


class GraveyardPDF(FPDF):
    def header(self):
        pass


def _base_pdf() -> FPDF:
    pdf = GraveyardPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


def generate_first_republic(output_dir: str = "fixtures") -> str:
    """First Republic Bank — private wealth style statement."""
    os.makedirs(output_dir, exist_ok=True)
    pdf = _base_pdf()
    pdf.add_page()
    pdf.set_font("Courier", "", 10)

    # Header
    pdf.cell(0, 8, "FIRST REPUBLIC BANK", ln=True, align="C")
    pdf.cell(0, 6, "Account Statement — March 2023", ln=True, align="C")
    pdf.ln(4)

    # Meta
    pdf.set_font("Courier", "", 9)
    pdf.cell(0, 5, "Account: ****1234   Opening Balance: $45,000.00", ln=True)
    pdf.cell(0, 5, "Period: 03/01/2023 — 03/31/2023   Closing Balance: $42,150.00", ln=True)
    pdf.ln(4)

    # Column headers
    pdf.set_font("Courier", "B", 9)
    pdf.cell(25, 6, "Date", border=0)
    pdf.cell(70, 6, "Description", border=0)
    pdf.cell(35, 6, "Withdrawal", border=0, align="R")
    pdf.cell(35, 6, "Deposit", border=0, align="R")
    pdf.cell(25, 6, "Balance", border=0, align="R")
    pdf.ln(6)
    pdf.set_font("Courier", "", 9)

    transactions = [
        ("03/01/2023", "Opening Balance", "", "", "45000.00"),
        ("03/02/2023", "Wire Out — SVB TREAS 310", "2500.00", "", "42500.00"),
        ("03/05/2023", "ACH Deposit — PAYROLL", "", "3200.00", "45700.00"),
        ("03/10/2023", "Check 1001", "150.00", "", "45550.00"),
        ("03/12/2023", "FRB ONLINE TRANSFER", "1000.00", "", "44550.00"),
        ("03/15/2023", "DIVIDEND — APY EARNED", "", "45.00", "44595.00"),
        ("03/18/2023", "ATM WITHDRAWAL", "200.00", "", "44395.00"),
        ("03/20/2023", "ZELLE PAYMENT — CONTINUED", "", "", "44395.00"),
        ("03/20/2023", "ON NEXT LINE", "1200.00", "", "43195.00"),
        ("03/25/2023", "MONTHLY SERVICE FEE", "45.00", "", "43150.00"),
        ("03/31/2023", "Closing Balance", "", "", "42150.00"),
    ]

    for date, desc, withdrawal, deposit, balance in transactions:
        pdf.cell(25, 5, date, border=0)
        pdf.cell(70, 5, desc[:34], border=0)
        pdf.cell(35, 5, withdrawal, border=0, align="R")
        pdf.cell(35, 5, deposit, border=0, align="R")
        pdf.cell(25, 5, balance, border=0, align="R")
        pdf.ln(5)

    out = os.path.join(output_dir, "sample_first_republic.pdf")
    pdf.output(out)
    print(f"[OK] Generated {out}")
    return out


def generate_svb(output_dir: str = "fixtures") -> str:
    """Silicon Valley Bank — startup banking style statement."""
    os.makedirs(output_dir, exist_ok=True)
    pdf = _base_pdf()
    pdf.add_page()
    pdf.set_font("Courier", "", 10)

    pdf.cell(0, 8, "SILICON VALLEY BANK", ln=True, align="C")
    pdf.cell(0, 6, "Business Account Statement — February 2023", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Courier", "", 9)
    pdf.cell(0, 5, "Account: ****5678   Opening Balance: $1,250,000.00", ln=True)
    pdf.cell(0, 5, "Period: 02/01/2023 — 02/28/2023   Closing Balance: $850,000.00", ln=True)
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
        ("02/01/2023", "Opening Balance", "", "", "1250000.00"),
        ("02/03/2023", "WIRE OUT — SERIES A DIST", "250000.00", "", "1000000.00"),
        ("02/05/2023", "ACH IN — STRIPE PAYOUTS", "", "45000.00", "1045000.00"),
        ("02/08/2023", "PAYROLL — GUSTO", "85000.00", "", "960000.00"),
        ("02/10/2023", "AWS *AMAZON WEB SERVICES", "12000.00", "", "948000.00"),
        ("02/12/2023", "INTEREST EARNED", "", "250.00", "948250.00"),
        ("02/15/2023", "CASH APP *SQ", "5000.00", "", "943250.00"),
        ("02/18/2023", "WIRE IN — VENTURE CAPITAL", "", "500000.00", "1443250.00"),
        ("02/20/2023", "SVB ONLINE BILL PAY", "", "", "1443250.00"),
        ("02/20/2023", "CONTINUED — VENDOR PAYMENT", "150000.00", "", "1293250.00"),
        ("02/25/2023", "MONTHLY ACCOUNT ANALYSIS", "443250.00", "", "850000.00"),
        ("02/28/2023", "Closing Balance", "", "", "850000.00"),
    ]

    for date, desc, withdrawal, deposit, balance in transactions:
        pdf.cell(25, 5, date, border=0)
        pdf.cell(70, 5, desc[:34], border=0)
        pdf.cell(35, 5, withdrawal, border=0, align="R")
        pdf.cell(35, 5, deposit, border=0, align="R")
        pdf.cell(25, 5, balance, border=0, align="R")
        pdf.ln(5)

    out = os.path.join(output_dir, "sample_svb.pdf")
    pdf.output(out)
    print(f"[OK] Generated {out}")
    return out


if __name__ == "__main__":
    generate_first_republic()
    generate_svb()
    print("[DONE] Graveyard fixtures ready for parser verification.")
