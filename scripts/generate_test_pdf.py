from pathlib import Path
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    output = Path("/home/e14/Desktop/Financial ETL/data/input/test_td_statement.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=letter)
    w, h = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, h-50, "TD BANK, N.A.")
    c.setFont("Helvetica", 12)
    c.drawString(50, h-70, "Personal Checking Statement")
    c.drawString(50, h-85, "Account: ****1234")
    c.drawString(50, h-100, "Statement Period: 05/01/2026 - 05/31/2026")
    y = h-140
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Date")
    c.drawString(150, y, "Description")
    c.drawString(400, y, "Amount")
    transactions = [
        ("05/01/2026", "PAYROLL DEPOSIT", "2,500.00"),
        ("05/02/2026", "AMAZON.COM AMZN.COM/BILL", "-45.67"),
        ("05/03/2026", "STARBUCKS #2847", "-8.50"),
        ("05/05/2026", "SHELL OIL 57442169", "-42.00"),
        ("05/10/2026", "NETFLIX.COM NETFLIX.COM", "-15.99"),
        ("05/15/2026", "PAYROLL DEPOSIT", "2,500.00"),
        ("05/20/2026", "HOME DEPOT #712", "-127.43"),
        ("05/25/2026", "UBER *TRIP HELP.UBER.COM", "-23.50"),
    ]
    c.setFont("Helvetica", 10)
    for date, desc, amount in transactions:
        y -= 20
        c.drawString(50, y, date)
        c.drawString(150, y, desc)
        c.drawString(400, y, amount)
    c.save()
    print(f"Created: {output}")
except ImportError:
    print("reportlab not installed")
