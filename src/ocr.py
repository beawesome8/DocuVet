"""
OCR extraction module — dual-engine approach with confidence-based routing.

Runs Tesseract and EasyOCR independently on the same page image. Tesseract
gives per-word confidence natively. EasyOCR gives per-detection confidence.
We compare both engines' output: if confidence is high and the text roughly
agrees, we trust it. If either engine reports low confidence, or the two
engines diverge significantly, the page is flagged for vision-model fallback
rather than passed downstream silently.

This module deliberately does not attempt to "fix" bad OCR text. Its only
job is extraction plus an honest confidence signal.
"""

import difflib
from dataclasses import dataclass, field

import pytesseract
from PIL import Image
import easyocr

# Point pytesseract directly at the Windows install path rather than
# relying on PATH, since the Windows installer does not add it automatically.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# EasyOCR loads its model into memory once, at import time. Recreating the
# reader per-call would reload the model every time, which is slow and
# wasteful. gpu=False is explicit because this machine's setup isn't
# confirmed to have CUDA available — safer default for a beginner setup.
_EASYOCR_READER = easyocr.Reader(["en"], gpu=False)

LOW_CONFIDENCE_THRESHOLD = 60  # percent; below this, flag for vision fallback
AGREEMENT_THRESHOLD = 0.7      # text similarity ratio; below this, engines disagree


@dataclass
class OCRResult:
    engine: str
    text: str
    confidence: float  # 0-100 scale, normalized across engines
    word_count: int


@dataclass
class PageOCRRecord:
    tesseract_result: OCRResult
    easyocr_result: OCRResult
    agreement_ratio: float
    needs_vision_fallback: bool
    reason: str = ""


def run_tesseract(img: Image.Image) -> OCRResult:
    """Run Tesseract OCR and compute mean word-level confidence."""
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    words = [w for w in data["text"] if w.strip()]
    confidences = [int(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and int(c) >= 0]

    text = " ".join(words)
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return OCRResult(engine="tesseract", text=text, confidence=mean_conf, word_count=len(words))


def run_easyocr(img: Image.Image) -> OCRResult:
    """Run EasyOCR and compute mean detection-level confidence, normalized to 0-100."""
    import numpy as np

    results = _EASYOCR_READER.readtext(np.array(img))

    if not results:
        return OCRResult(engine="easyocr", text="", confidence=0.0, word_count=0)

    texts = [r[1] for r in results]
    confidences = [r[2] * 100 for r in results]  # EasyOCR returns 0-1, normalize to 0-100

    text = " ".join(texts)
    mean_conf = sum(confidences) / len(confidences)

    return OCRResult(engine="easyocr", text=text, confidence=mean_conf, word_count=len(texts))


def compute_agreement(text_a: str, text_b: str) -> float:
    """
    Return a 0-1 similarity ratio between two OCR outputs using sequence matching.
    This is a cheap proxy for 'do the two engines see the same content', not
    a semantic comparison — exact wording differences still count as disagreement,
    which is intentional: it's a conservative signal.
    """
    return difflib.SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()


def process_page_ocr(img: Image.Image) -> PageOCRRecord:
    """
    Run both OCR engines on a page image and decide whether it needs
    vision-model fallback based on confidence and inter-engine agreement.
    """
    tess_result = run_tesseract(img)
    easy_result = run_easyocr(img)

    agreement = compute_agreement(tess_result.text, easy_result.text)

    needs_fallback = False
    reasons = []

    if tess_result.confidence < LOW_CONFIDENCE_THRESHOLD:
        needs_fallback = True
        reasons.append(f"Tesseract confidence {tess_result.confidence:.1f} below threshold")

    if easy_result.confidence < LOW_CONFIDENCE_THRESHOLD:
        needs_fallback = True
        reasons.append(f"EasyOCR confidence {easy_result.confidence:.1f} below threshold")

    if agreement < AGREEMENT_THRESHOLD:
        needs_fallback = True
        reasons.append(f"Engine agreement {agreement:.2f} below threshold")

    return PageOCRRecord(
        tesseract_result=tess_result,
        easyocr_result=easy_result,
        agreement_ratio=agreement,
        needs_vision_fallback=needs_fallback,
        reason="; ".join(reasons) if reasons else "OK",
    )


if __name__ == "__main__":
    import sys
    import json
    from dataclasses import asdict

    if len(sys.argv) != 2:
        print("Usage: python src/ocr.py <path_to_image>")
        sys.exit(1)

    image = Image.open(sys.argv[1]).convert("RGB")
    record = process_page_ocr(image)
    print(json.dumps(asdict(record), indent=2))
