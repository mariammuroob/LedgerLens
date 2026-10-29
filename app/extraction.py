
import re
from pathlib import Path

import pdfplumber


def extract_invoice(pdf_path: str | Path) -> dict:
    """Extract basic invoice fields from a text-based PDF."""

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages
        )

    def find(pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None

    quantity = find(r"Quantity:\s*(\d+)")
    unit_price = find(r"Unit Price:\s*([\d,.]+)")

    return {
        "vendor": find(r"Vendor:\s*(.+)"),
        "description": find(r"Description:\s*(.+)"),
        "trn": find(r"TRN:\s*(\d{15})"),
        "invoice_number": find(r"Invoice Number:\s*(.+)"),
        "date": find(r"Date:\s*(\d{4}-\d{2}-\d{2})"),
        "quantity": quantity,
        "unit_price": unit_price,
        "line_items": (
            [{"quantity": quantity, "unit_price": unit_price}]
            if quantity and unit_price
            else []
        ),
        "subtotal": find(r"^Subtotal:\s*([\d,.]+)"),
        "vat": find(r"^VAT(?:\s*\(5%\))?:\s*([\d,.]+)"),
        "total": find(r"^Total:\s*([\d,.]+)"),
        "currency": find(r"Currency:\s*([A-Z]{3})"),
        "vat_treatment": find(
            r"VAT Treatment:\s*(standard|zero-rated|exempt)"
        ),
    }
