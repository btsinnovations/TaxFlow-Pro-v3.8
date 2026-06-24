from fpdf import FPDF
from pathlib import Path

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=10)

# Header
pdf.set_font("Helvetica", "B", 14)
pdf.cell(0, 8, "Navy Federal Credit Union", ln=True)
pdf.set_font("Helvetica", size=9)
pdf.cell(0, 5, "P.O. Box 3000, Merrifield, VA 22119-3000", ln=True)
pdf.ln(4)

# Account Summary
pdf.set_font("Helvetica", "B", 11)
pdf.cell(0, 6, "Account Summary", ln=True)
pdf.set_font("Helvetica", size=9)
pdf.cell(0, 5, "Account Number: ****1234", ln=True)
pdf.cell(0, 5, "Statement Period: 05/01/2026 - 05/31/2026", ln=True)
pdf.cell(0, 5, "Beginning Balance: $5,250.00", ln=True)
pdf.cell(0, 5, "Ending Balance: $5,845.50", ln=True)
pdf.cell(0, 5, "Account Type: Share Draft", ln=True)
pdf.ln(6)

# Transaction table
pdf.set_font("Helvetica", "B", 10)
pdf.cell(0, 6, "Transaction History", ln=True)
pdf.ln(2)

pdf.set_font("Helvetica", "B", 8)
pdf.cell(22, 6, "Date", border="B")
pdf.cell(70, 6, "Description", border="B")
pdf.cell(28, 6, "Withdrawals", border="B", align="R")
pdf.cell(28, 6, "Deposits", border="B", align="R")
pdf.cell(28, 6, "Balance", border="B", align="R")
pdf.ln(6)

pdf.set_font("Helvetica", size=8)
rows = [
    ("05/01/2026", "Beginning Balance", "", "", "$5,250.00"),
    ("05/02/2026", "DFAS BAH HOUSING ALLOWANCE", "", "$1,850.00", "$7,100.00"),
    ("05/03/2026", "SHELL OIL STATION", "$45.67", "", "$7,054.33"),
    ("05/05/2026", "PAYROLL - DIRECT DEPOSIT", "", "$3,200.00", "$10,254.33"),
    ("05/07/2026", "STARBUCKS COFFEE", "$6.42", "", "$10,247.91"),
    ("05/10/2026", "TREAS 310 XXVA BENEFITS", "", "$2,150.00", "$12,397.91"),
    ("05/12/2026", "COURTESY PAY FEE", "$35.00", "", "$12,362.91"),
    ("05/15/2026", "DIVIDEND PAYMENT", "", "$12.50", "$12,375.41"),
    ("05/18/2026", "WALMART SUPERCENTER", "$127.83", "", "$12,247.58"),
    ("05/20/2026", "ZELLE FROM JOHN DOE", "", "$250.00", "$12,497.58"),
    ("05/22/2026", "GEICO AUTO INSURANCE", "$145.00", "", "$12,352.58"),
    ("05/25/2026", "NETFLIX.COM", "$15.99", "", "$12,336.59"),
    ("05/28/2026", "COURTESY PAY FEE", "$35.00", "", "$12,301.59"),
    ("05/31/2026", "Ending Balance", "", "", "$5,845.50"),
]

for date, desc, w, d, bal in rows:
    pdf.cell(22, 5, date)
    pdf.cell(70, 5, desc)
    pdf.cell(28, 5, w, align="R")
    pdf.cell(28, 5, d, align="R")
    pdf.cell(28, 5, bal, align="R")
    pdf.ln(5)

pdf.ln(4)
pdf.set_font("Helvetica", "I", 7)
pdf.cell(0, 4, "Share Draft Account transactions are listed above. Dividends are paid monthly.", ln=True)

out = Path("sample_statement.pdf")
pdf.output(str(out))
print(f"Created: {out.resolve()}")
