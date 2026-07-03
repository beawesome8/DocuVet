"""
Document intake and preprocessing module.

Responsibilities:
1. Compute a SHA-256 hash of the original file for audit purposes.
2. Normalize any accepted format (PDF, PNG, JPEG, TIFF) into a list of
   page images, since every downstream step (OCR, vision LLM) works on images.
3. Apply baseline preprocessing: autocontrast and a minimum-resolution check.

Document type classification is intentionally stubbed here. Real classification
requires extracted text, which is produced in Phase 2 (OCR). Wiring a filename-based
guess at this stage would be a placeholder masquerading as a feature.
"""

import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone

import fitz  # PyMuPDF
from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
MIN_RESOLUTION_PX = 800  # shorter edge; below this, OCR accuracy drops sharply


def compute_file_hash(filepath: str) -> str:
    """Return the SHA-256 hash of a file's raw bytes, read in chunks to handle large files."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_document_as_images(filepath: str) -> list[Image.Image]:
    """
    Convert any supported document into a list of PIL Images, one per page.
    PDFs are rendered page-by-page at 200 DPI. Image files return as a single-item list.
    """
    ext = Path(filepath).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    if ext == ".pdf":
        images = []
        pdf = fitz.open(filepath)
        zoom = 200 / 72  # PDF default is 72 DPI, render at 200 DPI for OCR quality
        matrix = fitz.Matrix(zoom, zoom)
        for page in pdf:
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)
        pdf.close()
        return images
    else:
        return [Image.open(filepath).convert("RGB")]


def preprocess_image(img: Image.Image) -> tuple[Image.Image, dict]:
    """
    Apply baseline preprocessing and return the processed image plus a metadata
    dict describing what was done and any quality flags raised.
    """
    metadata = {"steps_applied": [], "warnings": []}

    processed = ImageOps.autocontrast(img)
    metadata["steps_applied"].append("autocontrast")

    width, height = processed.size
    shorter_edge = min(width, height)
    if shorter_edge < MIN_RESOLUTION_PX:
        metadata["warnings"].append(
            f"Low resolution: shorter edge is {shorter_edge}px, "
            f"below the {MIN_RESOLUTION_PX}px threshold. OCR accuracy may suffer."
        )

    metadata["original_size"] = img.size
    metadata["final_size"] = processed.size
    return processed, metadata


def classify_document_type_stub(filepath: str) -> str:
    """
    Placeholder classifier. Returns 'unclassified' until Phase 2 provides
    extracted text for real content-based classification.
    """
    return "unclassified"


def process_document(filepath: str, output_dir: str = "data/processed") -> dict:
    """
    Run full intake for a single document: hash it, normalize to page images,
    preprocess each page, and save results. Returns an intake record.
    """
    os.makedirs(output_dir, exist_ok=True)

    file_hash = compute_file_hash(filepath)
    original_filename = Path(filepath).name
    pages = load_document_as_images(filepath)

    page_records = []
    for i, page_img in enumerate(pages):
        processed_img, page_meta = preprocess_image(page_img)
        output_path = os.path.join(output_dir, f"{file_hash[:12]}_page{i+1}.png")
        processed_img.save(output_path)
        page_records.append({"page_number": i + 1, "output_path": output_path, **page_meta})

    record = {
        "original_filename": original_filename,
        "file_hash": file_hash,
        "document_type": classify_document_type_stub(filepath),
        "page_count": len(pages),
        "pages": page_records,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    return record


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("Usage: python src/preprocess.py <path_to_document>")
        sys.exit(1)

    result = process_document(sys.argv[1])
    print(json.dumps(result, indent=2))
