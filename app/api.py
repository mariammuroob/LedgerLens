
import json
import tempfile
from pathlib import Path
from typing import Literal

import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.classifier import predict_category
from app.db import Invoice, Review, SessionLocal, init_db
from app.duplicates import calculate_file_hash, is_duplicate_invoice
from app.extraction import extract_invoice
from app.validation import validate_invoice

app = FastAPI(title="LedgerLens API", version="0.3.0")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    category: str | None = Field(default=None, max_length=100)
    reviewer: str = Field(default="human", max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/invoices")
async def upload_invoice(file: UploadFile = File(...)):
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    content = await file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="PDF must be 10 MB or smaller.",
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="File is not a valid PDF.",
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)

        file_hash = calculate_file_hash(temp_path)

        with SessionLocal() as session:
            # Check for an identical file.
            existing = session.scalar(
                select(Invoice).where(Invoice.file_hash == file_hash)
            )

            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate PDF. Existing invoice ID: {existing.id}",
                )

            try:
                with pdfplumber.open(temp_path) as pdf:
                    if len(pdf.pages) > 20:
                        raise HTTPException(
                            status_code=400,
                            detail="PDF cannot contain more than 20 pages.",
                        )

                # Extract invoice fields before checking invoice identity.
                extracted = extract_invoice(temp_path)

            except HTTPException:
                raise
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Could not read this PDF.",
                )

            # Check for the same vendor and invoice number.
            if is_duplicate_invoice(
                extracted.get("vendor") or "",
                extracted.get("invoice_number") or "",
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Duplicate invoice: the same vendor and "
                        "invoice number already exist."
                    ),
                )

            validation = validate_invoice(extracted)

            classification = None
            description = extracted.get("description") or ""

            if description.strip():
                try:
                    classification = predict_category(description)
                except Exception:
                    classification = None

            category = (
                classification.get("category")
                if classification else None
            )
            confidence = (
                classification.get("confidence")
                if classification else None
            )

            # All uploads require human review in this prototype.
            # Auto-approve only when extraction is complete,
            # validation passes, and confidence is at least 0.85.
            required_fields = [
                "vendor",
                "trn",
                "invoice_number",
                "date",
                "subtotal",
                "vat",
                "total",
                "currency",
            ]

            extraction_complete = (
                all(
                    str(extracted.get(field) or "").strip()
                    for field in required_fields
                )
                and bool(extracted.get("line_items"))
            )

            confidence_qualified = (
                confidence is not None
                and confidence >= 0.85
            )

            if (
                extraction_complete
                and validation["valid"]
                and confidence_qualified
            ):
                status = "approved"
            else:
                status = "pending_review"

            invoice = Invoice(
                file_hash=file_hash,
                filename=Path(file.filename).name,
                vendor=extracted.get("vendor"),
                invoice_number=extracted.get("invoice_number"),
                invoice_date=extracted.get("date"),
                subtotal=(
                    float(extracted["subtotal"].replace(",", ""))
                    if extracted.get("subtotal")
                    else None
                ),
                vat=(
                    float(extracted["vat"].replace(",", ""))
                    if extracted.get("vat")
                    else None
                ),
                total=(
                    float(extracted["total"].replace(",", ""))
                    if extracted.get("total")
                    else None
                ),
                currency=extracted.get("currency"),
                category=category,
                category_confidence=confidence,
                status=status,
                is_valid=validation["valid"],
                validation_errors=json.dumps(validation["errors"]),
            )

            session.add(invoice)
            session.commit()
            session.refresh(invoice)

            return {
                "invoice_id": invoice.id,
                "filename": invoice.filename,
                "extracted": extracted,
                "validation": validation,
                "classification": classification,
                "status": invoice.status,
            }

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@app.get("/invoices")
def list_invoices():
    with SessionLocal() as session:
        invoices = session.scalars(
            select(Invoice).order_by(Invoice.id.desc())
        ).all()

        return [
            {
                "id": invoice.id,
                "filename": invoice.filename,
                "vendor": invoice.vendor,
                "invoice_number": invoice.invoice_number,
                "category": invoice.category,
                "category_confidence": invoice.category_confidence,
                "status": invoice.status,
                "is_valid": invoice.is_valid,
            }
            for invoice in invoices
        ]


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    with SessionLocal() as session:
        invoice = session.get(Invoice, invoice_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            )

        reviews = session.scalars(
            select(Review)
            .where(Review.invoice_id == invoice_id)
            .order_by(Review.id.desc())
        ).all()

        return {
            "id": invoice.id,
            "filename": invoice.filename,
            "vendor": invoice.vendor,
            "invoice_number": invoice.invoice_number,
            "date": invoice.invoice_date,
            "subtotal": invoice.subtotal,
            "vat": invoice.vat,
            "total": invoice.total,
            "currency": invoice.currency,
            "category": invoice.category,
            "category_confidence": invoice.category_confidence,
            "status": invoice.status,
            "is_valid": invoice.is_valid,
            "validation_errors": json.loads(
                invoice.validation_errors or "[]"
            ),
            "reviews": [
                {
                    "action": review.action,
                    "reviewer": review.reviewer,
                    "notes": review.notes,
                    "created_at": (
                        review.created_at.isoformat()
                        if review.created_at
                        else None
                    ),
                }
                for review in reviews
            ],
        }



@app.post("/invoices/{invoice_id}/review")
def review_invoice(invoice_id: int, request: ReviewRequest):
    with SessionLocal() as session:
        invoice = session.get(Invoice, invoice_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            )

        if request.action == "approve" and not invoice.is_valid:
            raise HTTPException(
                status_code=400,
                detail="Cannot approve an invoice that failed validation.",
            )

        previous_category = invoice.category
        new_category = previous_category

        if request.category is not None:
            category = request.category.strip()

            if not category:
                raise HTTPException(
                    status_code=422,
                    detail="Category cannot be empty when supplied.",
                )

            new_category = category
            invoice.category = category

        if request.action == "approve":
            invoice.status = "approved"
        else:
            invoice.status = "rejected"

        # Record the review action and any category change.
        review = Review(
            invoice_id=invoice.id,
            action=request.action,
            reviewer=request.reviewer.strip() or "human",
            notes=request.notes,
            previous_category=previous_category,
            new_category=new_category,
        )

        session.add(review)
        session.commit()
        session.refresh(review)

        return {
            "invoice_id": invoice.id,
            "status": invoice.status,
            "category": invoice.category,
            "review": {
                "action": review.action,
                "reviewer": review.reviewer,
                "notes": review.notes,
                "previous_category": review.previous_category,
                "new_category": review.new_category,
            },
        }
