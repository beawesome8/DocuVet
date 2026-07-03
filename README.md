# DocuVet — Multimodal Document Intake Reviewer

Accepts scanned forms, PDFs, and images; extracts structured fields via OCR
and vision-model fallback; validates against business rules; routes
low-confidence results to human review.

## Status: Phase 1 of 6 complete

| Phase | Scope | Status |
|---|---|---|
| 1 | Document intake, hashing, normalization, preprocessing | Done |
| 2 | OCR (Tesseract + EasyOCR), confidence scoring, vision fallback | Not started |
| 3 | Structured field extraction (Pydantic + instructor) | Not started |
| 4 | Business rule validation, confidence-based routing | Not started |
| 5 | Human review UI (Streamlit), correction logging | Not started |
| 6 | Portfolio polish, demo, metrics | Not started |

## Architecture

Documents enter as PDF/PNG/JPEG/TIFF, get hashed for audit integrity, and
are normalized into per-page images (PDFs rendered at 200 DPI). Each page
gets baseline preprocessing (autocontrast, resolution check) before
downstream OCR.

## Known limitation (by design, not oversight)

Phase 1's quality gate checks pixel resolution only. It does not detect
blur, noise, or skew — a technically high-resolution image can still be
unreadable to OCR. This is intentional: confidence-based quality detection
belongs in Phase 2, where OCR output itself can be scored. Phase 1 proves
this gap directly — a synthetic test image with injected blur and noise
passes Phase 1 with zero warnings (see `data/uploads/test_invoice_messy.png`).

## Tech stack

Python 3.12, PyMuPDF, Pillow, Pydantic, PostgreSQL, Celery + Redis,
Tesseract + EasyOCR, Anthropic Claude (vision fallback), Streamlit.

## Setup

\`\`\`bash
py -3.12 -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
\`\`\`

## Usage (Phase 1)

\`\`\`bash
python src/generate_test_file.py       # generates clean + degraded test fixtures
python src/preprocess.py <filepath>    # runs intake on a document, prints JSON record
\`\`\`

## Author

Aman Benjamin Emmanuel — github.com/beawesome8
