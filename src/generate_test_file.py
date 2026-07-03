"""
Generates synthetic test documents for pipeline testing.

Produces two files from the same fake invoice content:
1. A clean PDF - for sanity-checking the intake pipeline (Phase 1).
2. A rotated, noisy PNG version - for stress-testing OCR confidence
   handling later in Phase 2, per the spec's requirement for a
   "messy document" demo case.

This is a development utility, not part of the production pipeline.
"""

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import os

OUTPUT_DIR = "data/uploads"


def create_clean_invoice_pdf(output_path: str) -> None:
    """Build a simple one-page invoice as a PDF using PyMuPDF's drawing API."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 in points

    lines = [
        (50, 60, "INVOICE", 18),
        (50, 100, "Vendor: Nordic Supply GmbH", 11),
        (50, 118, "Invoice Number: INV-2026-0417", 11),
        (50, 136, "Invoice Date: 2026-06-15", 11),
        (50, 154, "Due Date: 2026-07-15", 11),
        (50, 190, "Line Items:", 12),
        (50, 210, "1. Office Chairs (x4)         EUR 480.00", 10),
        (50, 228, "2. Standing Desk (x2)         EUR 620.00", 10),
        (50, 246, "3. Monitor Arm (x6)           EUR 210.00", 10),
        (50, 280, "Subtotal:                     EUR 1310.00", 11),
        (50, 298, "Tax (19%):                    EUR 248.90", 11),
        (50, 316, "Total:                        EUR 1558.90", 12),
    ]
    for x, y, text, size in lines:
        page.insert_text((x, y), text, fontsize=size)

    doc.save(output_path)
    doc.close()


def create_messy_version(clean_pdf_path: str, output_path: str) -> None:
    """
    Render the clean PDF's first page to an image, then degrade it:
    slight rotation, added noise, and mild blur - simulating a phone-camera
    scan rather than a clean digital export.
    """
    pdf = fitz.open(clean_pdf_path)
    page = pdf[0]
    zoom = 200 / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    pdf.close()

    # Rotate slightly, as if the document was photographed off-angle.
    rotated = img.rotate(-3.5, expand=True, fillcolor=(255, 255, 255))

    # Add light gaussian blur, simulating a soft-focus phone camera.
    blurred = rotated.filter(ImageFilter.GaussianBlur(radius=0.8))

    # Add speckle noise.
    pixels = blurred.load()
    width, height = blurred.size
    for _ in range(int(width * height * 0.02)):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        noise_val = random.randint(0, 255)
        pixels[x, y] = (noise_val, noise_val, noise_val)

    blurred.save(output_path)


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    clean_path = os.path.join(OUTPUT_DIR, "test_invoice_clean.pdf")
    messy_path = os.path.join(OUTPUT_DIR, "test_invoice_messy.png")

    create_clean_invoice_pdf(clean_path)
    print(f"Created: {clean_path}")

    create_messy_version(clean_path, messy_path)
    print(f"Created: {messy_path}")
