"""
FastAPI wrapper around the existing DocuVet pipeline modules.

This file adds no new pipeline logic. It exposes preprocess.py, ocr.py,
extract.py, and validate.py as HTTP endpoints so the React review UI
(Phase 5) can call them, and adds a lightweight in-memory store to track
which documents have been reviewed. In-memory storage is a documented
simplification: a restart loses review state. PostgreSQL persistence is
the spec's stated target and is a named next step, not built here, since
adding a database is a separate concern from wiring the API surface.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from preprocess import process_document
from extract import extract_invoice
from validate import validate_extraction

app = FastAPI(title="DocuVet API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default dev port
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "data/uploads"
PROCESSED_DIR = "data/processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

app.mount("/images", StaticFiles(directory=PROCESSED_DIR), name="images")

# In-memory store. Documented limitation: lost on restart. Key is document_id.
DOCUMENTS: dict[str, dict] = {}


@app.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    """
    Accept a document upload, run it through the full pipeline
    (preprocess -> extract -> validate), and store the result.
    """
    document_id = str(uuid.uuid4())[:8]
    upload_path = os.path.join(UPLOAD_DIR, f"{document_id}_{file.filename}")

    with open(upload_path, "wb") as f:
        f.write(await file.read())

    intake_record = process_document(upload_path, output_dir=PROCESSED_DIR)

    page_results = []
    for page in intake_record["pages"]:
        extraction_record = extract_invoice(page["output_path"])
        validation_result = validate_extraction(extraction_record)

        page_results.append({
            "page_number": page["page_number"],
            "image_url": f"/images/{Path(page['output_path']).name}",
            "extraction": extraction_record["extraction"],
            "ocr_diagnostic": extraction_record["ocr_diagnostic"],
            "decision": validation_result.decision,
            "decision_reasons": validation_result.decision_reasons,
            "issues": [
                {"rule": i.rule, "severity": i.severity, "detail": i.detail}
                for i in validation_result.issues
            ],
            "reviewed": False,
        })

    DOCUMENTS[document_id] = {
        "document_id": document_id,
        "original_filename": file.filename,
        "file_hash": intake_record["file_hash"],
        "pages": page_results,
    }

    return DOCUMENTS[document_id]


@app.get("/documents")
async def list_documents():
    """Return all processed documents, summary view for the queue list."""
    return [
        {
            "document_id": doc["document_id"],
            "original_filename": doc["original_filename"],
            "page_count": len(doc["pages"]),
            "decision": doc["pages"][0]["decision"] if doc["pages"] else "unknown",
            "reviewed": all(p["reviewed"] for p in doc["pages"]),
        }
        for doc in DOCUMENTS.values()
    ]


@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Return full detail for one document, for the review detail view."""
    if document_id not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")
    return DOCUMENTS[document_id]


@app.post("/documents/{document_id}/pages/{page_number}/review")
async def mark_reviewed(document_id: str, page_number: int):
    """Mark a specific page as reviewed. Correction capture is a named next step, not built here."""
    if document_id not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")

    for page in DOCUMENTS[document_id]["pages"]:
        if page["page_number"] == page_number:
            page["reviewed"] = True
            return page

    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/stats")
async def get_stats():
    """
    Aggregate metrics across all processed documents: auto-approval rate,
    vision-fallback rate, and a breakdown of what triggered each review -
    this is where the extraction_notes false-positive question becomes
    a real, growing number instead of a two-document anecdote in the README.
    """
    all_pages = [p for doc in DOCUMENTS.values() for p in doc["pages"]]
    total = len(all_pages)

    if total == 0:
        return {"total_pages": 0}

    auto_approved = sum(1 for p in all_pages if p["decision"] == "auto_approved")
    needed_fallback = sum(1 for p in all_pages if p["ocr_diagnostic"]["needs_vision_fallback"])
    flagged_by_notes_only = sum(
        1 for p in all_pages
        if p["decision"] == "needs_review"
        and not p["ocr_diagnostic"]["needs_vision_fallback"]
        and not any(i["severity"] == "error" for i in p["issues"])
    )

    return {
        "total_pages": total,
        "auto_approved": auto_approved,
        "auto_approval_rate": round(auto_approved / total, 3),
        "vision_fallback_rate": round(needed_fallback / total, 3),
        "flagged_by_notes_only": flagged_by_notes_only,
        "notes_only_flag_rate": round(flagged_by_notes_only / total, 3) if total else 0,
    }
