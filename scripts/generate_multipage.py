#!/usr/bin/env python3
from fpdf import FPDF
import os

def gen():
    os.makedirs("tests/fixtures", exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.set_font("Courier", "", 9)
    pdf.add_page()

    for t in ["JPMorgan Chase Bank, N.A.", "Chase Total Checking", "",
              "Account Summary", "Account Number: ****1234",
              "Statement Period: 01/01/2026 - 01/31/2026"]:
        pdf.cell(0, 5, t, ln=True, align="C" if t else "L")
    pdf.ln(2)

    pdf.set_font("Courier", "B", 9)
    for h, w in [("Date",25), ("Description",70), ("Withdrawal",35),
                 ("Deposit",35), ("Balance",25)]:
        pdf.cell(w, 5, h, align="R" if h not in ("Date","Description") else "L")
    pdf.ln(5)
    pdf.set_font("Courier", "", 9)

    bal = 10000.0
    rows = [("01/01/2026", "Beginning Balance", "", "", f"{bal:.2f}")]
    for i in range(1, 71):
        day = (i % 31) or 31
        d = f"01/{day:02d}/2026"
        if i % 3 == 0:
            bal += 100.0
            rows.append((d, f"DEPOSIT {i}", "", "100.00", f"{bal:.2f}"))
        else:
            w = 10.0 + i
            bal -= w
            rows.append((d, f"WITHDRAWAL {i}", f"{w:.2f}", "", f"{bal:.2f}"))
    rows.append(("01/31/2026", "Ending Balance", "", "", f"{bal:.2f}"))

    for r in rows:
        date, desc, w, dep, b = r
        pdf.cell(25, 5, date)
        pdf.cell(70, 5, desc[:34])
        pdf.cell(35, 5, f"${w}" if w else "", align="R")
        pdf.cell(35, 5, f"${dep}" if dep else "", align="R")
        pdf.cell(25, 5, f"${b}" if b else "", align="R")
        pdf.ln(5)

    out = "tests/fixtures/sample_multipage.pdf"
    pdf.output(out)
    print(f"[OK] {out} — {pdf.page_no()} pages, {len(rows)} rows")

if __name__ == "__main__":
    gen()
