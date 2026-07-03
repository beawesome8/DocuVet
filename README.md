# DocuVet — Multimodal Document Intake Reviewer

Accepts scanned forms, PDFs, and images; extracts structured fields via OCR
and vision-model fallback; validates against business rules; routes
low-confidence results to human review.

## Status: Phase 5 of 6 complete

| Phase | Scope | Status |
|---|---|---|
| 1 | Document intake, hashing, normalization, preprocessing | Done |
| 2 | OCR (Tesseract + EasyOCR), confidence scoring, vision fallback | Done |
| 3 | Structured field extraction (Pydantic + instructor) | Done |
| 4 | Business rule validation, confidence-based routing | Done |
| 5 | FastAPI backend + React review UI | Done |
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

**Implemented:** Python 3.12, FastAPI, PyMuPDF, Pillow, Pydantic,
Tesseract + EasyOCR, Anthropic Claude (vision fallback, via `instructor`),
React (Vite), Axios.

**Not yet built (named next steps, not shipped):** PostgreSQL — currently
an in-memory Python dict, lost on server restart. Celery + Redis — currently
synchronous request handling; a document upload blocks on OCR + LLM calls
for 10-20 seconds rather than being queued as a background job.

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

## Phase 2: OCR and confidence-based routing

Runs Tesseract and EasyOCR independently on each page. Neither engine's
confidence score is trusted alone — a single OCR engine can report high
confidence while producing wrong text. Instead, the two engines' outputs
are compared for agreement (via sequence similarity); low agreement is
treated as a stronger failure signal than either engine's self-reported
confidence.

Validated against Phase 1's clean/messy test pair:
- Clean invoice: 99.8% inter-engine agreement, no fallback needed.
- Messy invoice (rotated, blurred, noised): 44.6% agreement, correctly
  flagged for vision-model fallback, despite Tesseract's own confidence
  score (63%) technically clearing the single-engine threshold alone.

Note: word counts differ between engines on identical text (Tesseract
tokenizes per-word, EasyOCR groups multi-word regions). This is expected
and not used as a quality signal — only text similarity is.

## Usage (Phase 2)

\`\`\`bash
python src/ocr.py <path_to_processed_page_image>
\`\`\`

## Phase 3: Structured extraction with confidence-based routing

Routes each page based on Phase 2's diagnostic: OCR-clean pages are
extracted from OCR text (cheap); pages flagged for vision fallback skip
OCR text entirely and are extracted directly from the image via Claude's
vision API.

Validated result: on the messy test fixture, both OCR engines produced
garbled text (e.g. "BUR 1810.00" instead of "EUR 1310.00"), while
Tesseract's own confidence score (63%) would have passed a single-engine
threshold check alone. Vision fallback, triggered by the Phase 2 agreement
signal, recovered every field correctly. This is the core validation of
the project's confidence-routing architecture, not just OCR duplication.

Scope note: only an invoice schema is implemented. Document-type
classification and multi-schema routing are a named next step (see spec),
not built here — real classification needs a labeled dataset or dedicated
classification prompt, out of scope for a single-fixture demo.

Known inconsistency: the OCR-text extraction path will compute unit price
via division when only line totals are present (flagged honestly in
`extraction_notes`); the vision path leaves it null in the same scenario.
Same model, different prompt phrasing produced different behavior — not
yet reconciled.

## Usage (Phase 3)

\`\`\`bash
python src/extract.py <path_to_processed_page_image>
\`\`\`

## Phase 4: Business rule validation and routing

Three layers: type validation (dates parse), business rules (line items
sum to subtotal, subtotal + tax = total), and routing (auto-approve vs.
human review).

No per-field numeric confidence score exists from the extraction model,
so routing does not fabricate one. It uses two real signals instead:
whether the page needed OCR vision fallback (Phase 2), and whether the
model's own `extraction_notes` is non-empty (self-reported uncertainty).

Known limitation: `extraction_notes` is treated as binary (present/absent),
not classified by severity. Measured on 2 test documents: the notes-based
rule contributed 0 correct catches and 1 false positive (a clean invoice
with a harmless note about an optional null field was routed to review
solely because of that note). The OCR-fallback flag alone was sufficient
in both test cases. This is not enough data to remove the rule - n=2 is
an anecdote, not a statistic - so it stays active, but Phase 5's dashboard
tracks false-positive review rate directly so this becomes a measured
decision instead of a guessed one.

## Usage (Phase 4)

\`\`\`bash
python src/extract.py <image_path> > data/scratch/extraction.json
python src/validate.py data/scratch/extraction.json
\`\`\`

## Phase 5: FastAPI backend and React review UI

FastAPI wraps the existing pipeline (preprocess, ocr, extract, validate)
as HTTP endpoints; no pipeline logic was rewritten, only exposed. React
(Vite) provides a two-view UI: a queue list showing all processed documents
with their routing decision, and a detail view showing each page's image
alongside extracted fields and the reason for the routing decision.

Validated end-to-end through the actual browser UI (not just curl/CLI):
uploading the clean test fixture correctly produced `extraction_method:
ocr_text` and `auto_approved`-eligible field values, while still routing
to `needs_review` due to the extraction_notes false-positive pattern
documented in Phase 4 - this is now reproduced live in the UI, not just
measured in a script, on the same 2-document sample size.

Off-scope test: uploading an unrelated document (a resume) into the
invoice-only pipeline did not produce hallucinated invoice data - the
model correctly reported "this document is not an invoice" in
`extraction_notes` rather than inventing a vendor or totals. Informal
robustness signal, not a formal test case.

Known limitations, stated plainly:
- No persistence: all state is an in-memory dict, lost on server restart.
- No async queue: document processing is synchronous inside the HTTP
  request, so uploads take 10-20 seconds rather than returning immediately.
- No click-to-highlight source regions on the image (spec's stated
  interaction) - extraction doesn't return bounding boxes, so this would
  require a second, dedicated OCR pass just for coordinates. Full image
  and full field list are shown side by side instead.

## Usage (Phase 5)

\`\`\`bash
# terminal 1: backend
python -m uvicorn src.api:app --reload --port 8000

# terminal 2: frontend
cd frontend
npm run dev
# open http://localhost:5173
\`\`\`
