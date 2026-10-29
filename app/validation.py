
from datetime import date
from decimal import Decimal, InvalidOperation


def validate_invoice(invoice: dict) -> dict:
    errors = []

    # V1: Check required fields
    required_fields = [
        "vendor",
        "trn",
        "invoice_number",
        "date",
        "subtotal",
        "vat",
        "total",
        "currency",
        "vat_treatment",
    ]

    for field in required_fields:
        if not invoice.get(field):
            errors.append(f"Missing required field: {field}")

    # Parse invoice amounts
    try:
        subtotal = Decimal(str(invoice["subtotal"]))
        vat = Decimal(str(invoice["vat"]))
        total = Decimal(str(invoice["total"]))
    except (KeyError, InvalidOperation, TypeError):
        return {
            "valid": False,
            "errors": errors + ["Missing or invalid invoice amounts"],
        }

    # V2: TRN must contain exactly 15 digits
    trn = invoice.get("trn") or ""
    if not trn.isdigit() or len(trn) != 15:
        errors.append("TRN must contain exactly 15 digits")

    # V3: Date must be valid and not in the future
    try:
        invoice_date = date.fromisoformat(invoice["date"])
        if invoice_date > date.today():
            errors.append("Invoice date cannot be in the future")
    except (KeyError, ValueError, TypeError):
        errors.append("Invoice date is missing or invalid")

    # V4 and V5: Validate line items and subtotal
    line_items = invoice.get("line_items")

    if not line_items:
        errors.append("Missing line items")
    else:
        line_total_sum = Decimal("0.00")

        for index, item in enumerate(line_items, start=1):
            try:
                quantity = Decimal(str(item["quantity"]))
                unit_price = Decimal(str(item["unit_price"]))

                if quantity <= 0 or unit_price < 0:
                    errors.append(
                        f"Line {index}: quantity must be positive "
                        "and unit price cannot be negative"
                    )
                    continue

                line_total = (quantity * unit_price).quantize(
                    Decimal("0.01")
                )
                line_total_sum += line_total

            except (KeyError, InvalidOperation, TypeError):
                errors.append(f"Line {index}: missing or invalid amounts")

        if abs(line_total_sum - subtotal) > Decimal("0.01"):
            errors.append("Sum of line totals does not equal subtotal")

    # V6: Check VAT treatment
    vat_treatment = invoice.get("vat_treatment")

    if vat_treatment == "standard":
        expected_vat = (subtotal * Decimal("0.05")).quantize(
            Decimal("0.01")
        )
        if abs(vat - expected_vat) > Decimal("0.01"):
            errors.append("VAT does not match the expected 5% rate")

    elif vat_treatment in ("zero-rated", "exempt"):
        if vat != Decimal("0.00"):
            errors.append("VAT should be zero for this VAT treatment")

    elif "VAT treatment is missing or invalid" not in errors:
        errors.append("VAT treatment is missing or invalid")

    # V7: Total must equal subtotal plus VAT
    expected_total = subtotal + vat
    if abs(total - expected_total) > Decimal("0.01"):
        errors.append("Total does not equal subtotal plus VAT")

    # V8: Currency must be AED
    if invoice.get("currency") != "AED":
        errors.append("Currency must be AED")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }
