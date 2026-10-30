
import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, Invoice, Review
from app import api, duplicates


def make_test_pdf(vendor, invoice_number):
    """Create a small PDF containing fields the extractor can read."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 800, f"Vendor: {vendor}")
    pdf.drawString(50, 780, "TRN: 100123456789012")
    pdf.drawString(50, 760, f"Invoice Number: {invoice_number}")
    pdf.drawString(50, 740, "Date: 2026-06-27")
    pdf.drawString(50, 720, "Description: Office supplies")
    pdf.drawString(50, 700, "Quantity: 1")
    pdf.drawString(50, 680, "Unit Price: 100.00")
    pdf.drawString(50, 660, "Subtotal: 100.00")
    pdf.drawString(50, 640, "VAT: 5.00")
    pdf.drawString(50, 620, "Total: 105.00")
    pdf.drawString(50, 600, "Currency: AED")
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def setup_test_database(monkeypatch):
    """Replace the API database with an isolated in-memory database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(api, "SessionLocal", TestSession)
    monkeypatch.setattr(duplicates, "SessionLocal", TestSession)
    monkeypatch.setattr(api, "init_db", lambda: None)

    return engine, TestSession


def test_upload_rejects_same_vendor_and_invoice_number(monkeypatch):
    engine, TestSession = setup_test_database(monkeypatch)

    monkeypatch.setattr(
        api,
        "extract_invoice",
        lambda path: {
            "vendor": "Example Trading LLC",
            "invoice_number": "INV-100",
            "date": "2026-06-27",
            "subtotal": "100.00",
            "vat": "5.00",
            "total": "105.00",
            "currency": "AED",
            "description": "Office supplies",
            "trn": "100123456789012",
            "quantity": "1",
            "unit_price": "100.00",
            "line_items": [],
            "vat_treatment": "standard",
        },
    )
    monkeypatch.setattr(
        api,
        "predict_category",
        lambda description: {
            "category": "office supplies",
            "confidence": 0.9,
        },
    )

    with TestClient(api.app) as client:
        first = client.post(
            "/invoices",
            files={
                "file": (
                    "first.pdf",
                    make_test_pdf("Example Trading LLC", "INV-100"),
                    "application/pdf",
                )
            },
        )
        assert first.status_code == 200

        second = client.post(
            "/invoices",
            files={
                "file": (
                    "second.pdf",
                    make_test_pdf("Example Trading LLC", "INV-100"),
                    "application/pdf",
                )
            },
        )
        assert second.status_code == 409
        assert "Duplicate invoice" in second.json()["detail"]

    with TestSession() as session:
        saved = session.scalars(select(Invoice)).all()
        assert len(saved) == 1

    engine.dispose()


def test_upload_rejects_identical_pdf(monkeypatch):
    engine, TestSession = setup_test_database(monkeypatch)

    monkeypatch.setattr(
        api,
        "extract_invoice",
        lambda path: {
            "vendor": "Example Trading LLC",
            "invoice_number": "INV-HASH-001",
            "date": "2026-06-27",
            "subtotal": "100.00",
            "vat": "5.00",
            "total": "105.00",
            "currency": "AED",
            "description": "Office supplies",
            "trn": "100123456789012",
            "quantity": "1",
            "unit_price": "100.00",
            "line_items": [],
            "vat_treatment": "standard",
        },
    )
    monkeypatch.setattr(
        api,
        "predict_category",
        lambda description: {
            "category": "office supplies",
            "confidence": 0.9,
        },
    )

    pdf_bytes = make_test_pdf("Example Trading LLC", "INV-HASH-001")

    with TestClient(api.app) as client:
        first = client.post(
            "/invoices",
            files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        )
        assert first.status_code == 200

        second = client.post(
            "/invoices",
            files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        )
        assert second.status_code == 409
        assert "Duplicate PDF" in second.json()["detail"]

    with TestSession() as session:
        saved = session.scalars(select(Invoice)).all()
        assert len(saved) == 1

    engine.dispose()


def test_upload_auto_approves_complete_valid_high_confidence_invoice(monkeypatch):
    engine, TestSession = setup_test_database(monkeypatch)

    monkeypatch.setattr(
        api,
        "extract_invoice",
        lambda path: {
            "vendor": "Example Trading LLC",
            "invoice_number": "INV-AUTO-001",
            "date": "2026-06-27",
            "subtotal": "100.00",
            "vat": "5.00",
            "total": "105.00",
            "currency": "AED",
            "description": "Office supplies",
            "trn": "100123456789012",
            "quantity": "1",
            "unit_price": "100.00",
            "line_items": [
                {
                    "description": "Office supplies",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "subtotal": "100.00",
                    "vat": "5.00",
                    "total": "105.00",
                }
            ],
            "vat_treatment": "standard",
        },
    )
    monkeypatch.setattr(
        api,
        "predict_category",
        lambda description: {
            "category": "office supplies",
            "confidence": 0.90,
        },
    )

    with TestClient(api.app) as client:
        response = client.post(
            "/invoices",
            files={
                "file": (
                    "auto-approve.pdf",
                    make_test_pdf("Example Trading LLC", "INV-AUTO-001"),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    engine.dispose()


def test_review_records_category_change_in_audit_log(monkeypatch):
    engine, TestSession = setup_test_database(monkeypatch)

    invoice = Invoice(
        file_hash="a" * 64,
        filename="audit-test.pdf",
        vendor="Example Trading LLC",
        invoice_number="INV-AUDIT-001",
        status="pending_review",
        is_valid=True,
        category="uncategorized",
    )

    with TestSession() as session:
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        invoice_id = invoice.id

    with TestClient(api.app) as client:
        response = client.post(
            f"/invoices/{invoice_id}/review",
            json={
                "action": "approve",
                "reviewer": "test-user",
                "notes": "Corrected category after review",
                "category": "office supplies",
            },
        )

    assert response.status_code == 200
    assert response.json()["category"] == "office supplies"
    assert response.json()["review"]["previous_category"] == "uncategorized"
    assert response.json()["review"]["new_category"] == "office supplies"

    with TestSession() as session:
        reviews = session.scalars(select(Review)).all()
        assert len(reviews) == 1
        assert reviews[0].reviewer == "test-user"
        assert reviews[0].previous_category == "uncategorized"
        assert reviews[0].new_category == "office supplies"

    engine.dispose()
