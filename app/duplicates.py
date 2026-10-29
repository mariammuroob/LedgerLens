
import hashlib
from pathlib import Path

from sqlalchemy import select

from app.db import Invoice, SessionLocal


def calculate_file_hash(file_path: str | Path) -> str:
    """Return a SHA-256 hash of a file's contents."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def is_duplicate_file(file_path: str | Path) -> bool:
    """Check whether this exact file already exists in the database."""
    file_hash = calculate_file_hash(file_path)

    with SessionLocal() as session:
        existing_invoice = session.scalar(
            select(Invoice.id).where(Invoice.file_hash == file_hash)
        )

    return existing_invoice is not None


def is_duplicate_invoice(
    vendor: str,
    invoice_number: str,
) -> bool:
    """Check whether the same vendor and invoice number already exist."""
    vendor = vendor.strip().casefold()
    invoice_number = invoice_number.strip().casefold()

    if not vendor or not invoice_number:
        return False

    with SessionLocal() as session:
        invoices = session.scalars(
            select(Invoice).where(
                Invoice.invoice_number.is_not(None)
            )
        ).all()

        for invoice in invoices:
            existing_vendor = (invoice.vendor or "").strip().casefold()
            existing_number = (
                invoice.invoice_number or ""
            ).strip().casefold()

            if (
                existing_vendor == vendor
                and existing_number == invoice_number
            ):
                return True

    return False
