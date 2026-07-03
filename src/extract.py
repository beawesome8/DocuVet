"""
Structured field extraction module.

Takes a processed page image (Phase 1) and its OCR diagnostic record (Phase 2),
then extracts structured invoice fields into a validated Pydantic schema.

Routing logic:
- If Phase 2 did NOT flag the page for vision fallback: extract from OCR text.
  Cheap, fast, and OCR was already validated as trustworthy.
- If Phase 2 DID flag the page: skip OCR text entirely and send the raw page
  image to Claude's vision API. Garbled OCR text is never trusted as
  extraction input once it's been flagged as unreliable.

Scope note: only an invoice schema is implemented. The build spec calls for
schema selection by document type (invoice, form, contract...). Real
classification needs either a labeled dataset or a dedicated classification
prompt — out of scope for a single-fixture portfolio demo. This is a
documented simplification, not an oversight.
"""

import base64
import json
import os
import sys
from typing import Optional

import instructor
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from PIL import Image as PILImage

from preprocess import process_document
from ocr import process_page_ocr

load_dotenv()

MODEL = "claude-sonnet-5"

client = instructor.from_anthropic(Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]))


class LineItem(BaseModel):
    description: str
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None


class InvoiceExtraction(BaseModel):
    vendor_name: str
    invoice_number: str
    invoice_date: str
    due_date: Optional[str] = None
    line_items: list[LineItem]
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: float
    extraction_method: str = Field(
        default="unset", description="'ocr_text' or 'vision_fallback'"
    )
    extraction_notes: Optional[str] = Field(
        default=None,
        description="Any ambiguity, conflicting values, or fields the model "
        "could not confidently determine. Empty if extraction was clean.",
    )


def extract_from_text(ocr_text: str) -> InvoiceExtraction:
    """Extract invoice fields from OCR-derived text. Used when OCR passed Phase 2's checks."""
    result = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        response_model=InvoiceExtraction,
        messages=[{
            "role": "user",
            "content": (
                "Extract invoice fields from this OCR text. The text may contain "
                "OCR errors (misread characters, merged words) - use surrounding "
                "context to correct obvious character-level errors only. Do not "
                "compute or infer any numeric value that is not explicitly present "
                "in the text (for example, do not divide a line total by quantity "
                "to produce a unit price). If a field is not explicitly stated, "
                "leave it null and note it in extraction_notes.\n\n"
                f"OCR TEXT:\n{ocr_text}"
            ),
        }],
    )
    result.extraction_method = "ocr_text"
    return result


def extract_from_image(image_path: str) -> InvoiceExtraction:
    """Extract invoice fields directly from the page image. Used when Phase 2 flagged the page."""
    result = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        response_model=InvoiceExtraction,
        messages=[{
            "role": "user",
            "content": [
                instructor.Image.from_path(image_path),
                (
                    "Extract invoice fields directly from this document image. "
                    "OCR failed on this page (low confidence or inter-engine "
                    "disagreement), so read the image itself rather than relying "
                    "on any OCR text. Do not compute or infer any numeric value "
                    "that is not explicitly present in the image (for example, do "
                    "not divide a line total by quantity to produce a unit price). "
                    "If a field is not explicitly shown, leave it null and note it "
                    "in extraction_notes rather than guessing."
                ),
            ],
        }],
    )
    result.extraction_method = "vision_fallback"
    return result


def extract_invoice(image_path: str) -> dict:
    """Run the full routing decision: OCR-based or vision-based extraction."""
    img = PILImage.open(image_path).convert("RGB")
    ocr_record = process_page_ocr(img)

    if ocr_record.needs_vision_fallback:
        extraction = extract_from_image(image_path)
    else:
        extraction = extract_from_text(ocr_record.tesseract_result.text)

    return {
        "extraction": extraction.model_dump(),
        "ocr_diagnostic": {
            "needs_vision_fallback": ocr_record.needs_vision_fallback,
            "reason": ocr_record.reason,
            "agreement_ratio": ocr_record.agreement_ratio,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/extract.py <path_to_processed_page_image>")
        sys.exit(1)

    result = extract_invoice(sys.argv[1])
    print(json.dumps(result, indent=2))
