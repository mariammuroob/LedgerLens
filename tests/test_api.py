
import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, Invoice
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

    # Make extraction deterministic for this endpoint test.
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
        lambda description: {"category": "office supplies", "confidence": 0.9},
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
        lambda description: {"category": "office supplies", "confidence": 0.9},
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