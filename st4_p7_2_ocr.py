"""ST4 Phase 7.2 — OCR degradation / scanned PDF test."""
import os
import sys
import io
import requests
from fpdf import FPDF
from PIL import Image, ImageFilter
from pdf2image import convert_from_path


def build_clean_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Fake Bank Checking Statement", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, "Account: 1234567890 | Period: 2026-01-01 to 2026-01-31", ln=True)
    pdf.ln(5)
    headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    for h in headers:
        pdf.cell(35, 8, h, border=1)
    pdf.ln()
    rows = [
        ("01/01/2026", "Opening Balance", "", "", "1000.00"),
        ("01/05/2026", "Grocery Store", "150.00", "", "850.00"),
        ("01/10/2026", "Payroll Deposit", "", "2000.00", "2850.00"),
        ("01/15/2026", "Electric Bill", "120.00", "", "2730.00"),
    ]
    for row in rows:
        for cell in row:
            pdf.cell(35, 8, cell, border=1)
        pdf.ln()
    raw = pdf.output(dest="S")
    return io.BytesIO(raw.encode("latin-1"))


def degrade_pdf(pdf_bytes):
    """Render PDF to 150 DPI image, add noise + blur, then re-embed into a new PDF."""
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes.getvalue())
        tmp_path = tmp.name
    try:
        images = convert_from_path(tmp_path, dpi=150)
        degraded = []
        for img in images:
            from PIL import ImageDraw
            import random
            # Gaussian blur
            img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
            # Add noise
            pixels = img.load()
            for y in range(0, img.height, 2):
                for x in range(0, img.width, 2):
                    r, g, b = pixels[x, y][:3]
                    noise = random.randint(-15, 15)
                    pixels[x, y] = (max(0, min(255, r+noise)), max(0, min(255, g+noise)), max(0, min(255, b+noise)))
            degraded.append(img)

        # Write images back to PDF using fpdf
        out = io.BytesIO()
        pdf = FPDF()
        for img in degraded:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as png:
                img.save(png.name, "PNG")
                pdf.add_page()
                pdf.image(png.name, 10, 10, 190)
        raw = pdf.output(dest="S")
        return io.BytesIO(raw.encode("latin-1"))
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


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
    return r.status_code, r.text[:400]


def main():
    clean = build_clean_pdf()
    degraded = degrade_pdf(clean)

    print("Uploading clean PDF...")
    clean_status, clean_text = upload_pdf(clean, "p7_2_clean.pdf")
    print(f"  clean: HTTP {clean_status}")

    print("Uploading degraded/scanned PDF...")
    ocr_status, ocr_text = upload_pdf(degraded, "p7_2_degraded.pdf")
    print(f"  degraded: HTTP {ocr_status}")

    if ocr_status == 500:
        print("\nPHASE 7.2 RESULT: FAIL (degraded PDF caused 500)")
        sys.exit(1)

    print("\nPHASE 7.2 RESULT: PASS (degraded PDF handled without crash)")


if __name__ == "__main__":
    main()
