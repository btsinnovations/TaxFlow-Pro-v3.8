from fpdf import FPDF
from pathlib import Path

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=10)

# Ally-style header
pdf.set_font("Helvetica", "B", 14)
pdf.cell(0, 8, "Ally Bank", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", size=9)
pdf.cell(0, 5, "Online Savings Account", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 5, "Member FDIC", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

# Account Summary
pdf.set_font("Helvetica", "B", 11)
pdf.cell(0, 6, "Account Summary", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", size=9)
pdf.cell(0, 5, "Account Number: ****9012", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 5, "Statement Period: 06/01/2026 - 06/30/2026", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 5, "Beginning Balance: $25,000.00", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 5, "Ending Balance: $25,847.50", new_x="LMARGIN", new_y="NEXT")
pdf.ln(6)

# Single-column amount layout (negative for debits)
pdf.set_font("Helvetica", "B", 10)
pdf.cell(0, 6, "Transactions", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)

pdf.set_font("Helvetica", "B", 8)
pdf.cell(22, 6, "Date", border="B")
pdf.cell(90, 6, "Description", border="B")
pdf.cell(35, 6, "Amount", border="B", align="R")
pdf.cell(35, 6, "Balance", border="B", align="R")
pdf.ln(6)

pdf.set_font("Helvetica", size=8)
rows = [
    ("06/01/2026", "Beginning Balance", "", "$25,000.00"),
    ("06/02/2026", "ACH TRANSFER FROM EXTERNAL", "$5,000.00", "$30,000.00"),
    ("06/05/2026", "WIRE TRANSFER OUT - SWIFT", "-$2,500.00", "$27,500.00"),
    ("06/08/2026", "INTEREST EARNED", "$12.50", "$27,512.50"),
    ("06/10/2026", "ZELLE PAYMENT TO JOHN DOE", "-$250.00", "$27,262.50"),
    ("06/12/2026", "DIVIDEND PAYMENT", "$25.00", "$27,287.50"),
    ("06/15/2026", "ATM WITHDRAWAL FEE", "-$3.00", "$27,284.50"),
    ("06/18/2026", "OVERDRAFT TRANSFER FROM SAV", "-$500.00", "$26,784.50"),
    ("06/20/2026", "CASH BACK REWARD", "$5.00", "$26,789.50"),
    ("06/22/2026", "MONTHLY SERVICE FEE", "-$0.00", "$26,789.50"),
    ("06/25/2026", "ACH DEPOSIT - PAYROLL", "$3,200.00", "$29,989.50"),
    ("06/28/2026", "EXTERNAL TRANSFER OUT", "-$4,142.00", "$25,847.50"),
    ("06/30/2026", "Ending Balance", "", "$25,847.50"),
]

for date, desc, amt, bal in rows:
    pdf.cell(22, 5, date)
    pdf.cell(90, 5, desc)
    pdf.cell(35, 5, amt, align="R")
    pdf.cell(35, 5, bal, align="R")
    pdf.ln(5)

pdf.ln(4)
pdf.set_font("Helvetica", "I", 7)
pdf.cell(0, 4, "Ally Bank, P.O. Box 13625, Philadelphia, PA 19101", new_x="LMARGIN", new_y="NEXT")

out = Path("sample_fiserv.pdf")
pdf.output(str(out))
print(f"Created Fiserv DNA test PDF: {out.resolve()}")
