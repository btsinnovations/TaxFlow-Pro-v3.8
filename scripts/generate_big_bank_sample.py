from fpdf import FPDF
from pathlib import Path

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=10)

# Chase-style header
pdf.set_font("Helvetica", "B", 14)
pdf.cell(0, 8, "JPMorgan Chase Bank, N.A.", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", size=9)
pdf.cell(0, 5, "Chase Total Checking", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

# Account Summary
pdf.set_font("Helvetica", "B", 11)
pdf.cell(0, 6, "Account Summary", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", size=9)
pdf.cell(0, 5, "Account Number: ****5678", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 5, "Statement Period: 06/01/2026 - 06/30/2026", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 5, "Beginning Balance: $12,450.00", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 5, "Ending Balance: $11,892.33", new_x="LMARGIN", new_y="NEXT")
pdf.ln(6)

# Transaction table with Withdrawals/Deposits columns
pdf.set_font("Helvetica", "B", 10)
pdf.cell(0, 6, "Transaction Details", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)

pdf.set_font("Helvetica", "B", 8)
pdf.cell(22, 6, "Date", border="B")
pdf.cell(60, 6, "Description", border="B")
pdf.cell(28, 6, "Withdrawals", border="B", align="R")
pdf.cell(28, 6, "Deposits", border="B", align="R")
pdf.cell(28, 6, "Balance", border="B", align="R")
pdf.ln(6)

pdf.set_font("Helvetica", size=8)
rows = [
    ("06/01/2026", "Beginning Balance", "", "", "$12,450.00"),
    ("06/02/2026", "PAYROLL DIRECT DEPOSIT", "", "$4,200.00", "$16,650.00"),
    ("06/03/2026", "SHELL OIL 5744212039", "$52.45", "", "$16,597.55"),
    ("06/04/2026", "AMAZON.COM AMZN.COM/BILL", "$127.99", "", "$16,469.56"),
    ("06/05/2026", "STARBUCKS #2849 SEATTLE", "$8.67", "", "$16,460.89"),
    ("06/07/2026", "CITY ELECTRIC BILL PAY", "$145.00", "", "$16,315.89"),
    ("06/08/2026", "UBER TRIP HELP.UBER.COM", "$24.50", "", "$16,291.39"),
    ("06/10/2026", "VENMO PAYMENT", "$150.00", "", "$16,141.39"),
    ("06/12/2026", "MORTGAGE PAYMENT CHASE", "$2,100.00", "", "$14,041.39"),
    ("06/15/2026", "INTEREST PAID", "", "$0.85", "$14,042.24"),
    ("06/18/2026", "HOME DEPOT #1234", "$345.67", "", "$13,696.57"),
    ("06/20/2026", "NETFLIX.COM 800-123-4567", "$15.99", "", "$13,680.58"),
    ("06/22/2026", "GEICO AUTO INS PREM", "$185.00", "", "$13,495.58"),
    ("06/25/2026", "ATM WITHDRAWAL #9876", "$200.00", "", "$13,295.58"),
    ("06/28/2026", "OVERDRAFT PROTECTION FEE", "$34.00", "", "$13,261.58"),
    ("06/30/2026", "Ending Balance", "", "", "$11,892.33"),
]

for date, desc, w, d, bal in rows:
    pdf.cell(22, 5, date)
    pdf.cell(60, 5, desc)
    pdf.cell(28, 5, w, align="R")
    pdf.cell(28, 5, d, align="R")
    pdf.cell(28, 5, bal, align="R")
    pdf.ln(5)

pdf.ln(4)
pdf.set_font("Helvetica", "I", 7)
pdf.cell(0, 4, "Questions? Visit chase.com or call 1-800-935-9935.", new_x="LMARGIN", new_y="NEXT")

out = Path("sample_big_bank.pdf")
pdf.output(str(out))
print(f"Created Big Bank test PDF: {out.resolve()}")
