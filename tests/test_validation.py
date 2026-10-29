from app.validation import validate_invoice


def valid_invoice():
    return {
        "vendor": "Example Trading LLC",
        "trn": "123456789012345",
        "invoice_number": "INV-001",
        "date": "2026-10-20",
        "subtotal": "100.00",
        "vat": "5.00",
        "total": "105.00",
        "currency": "AED",
        "vat_treatment": "standard",
        "quantity": "1",
        "unit_price": "100.00",
        "line_items": [
            {"quantity": "1", "unit_price": "100.00"}
        ],
    }


def test_valid_invoice_passes():
    result = validate_invoice(valid_invoice())
    assert result["valid"] is True
    assert result["errors"] == []


def test_incorrect_total_fails():
    invoice = valid_invoice()
    invoice["total"] = "120.00"

    result = validate_invoice(invoice)

    assert result["valid"] is False
    assert "Total does not equal subtotal plus VAT" in result["errors"]


def test_missing_trn_fails():
    invoice = valid_invoice()
    invoice["trn"] = None

    result = validate_invoice(invoice)

    assert result["valid"] is False


def test_wrong_currency_fails():
    invoice = valid_invoice()
    invoice["currency"] = "USD"

    result = validate_invoice(invoice)

    assert result["valid"] is False
    assert "Currency must be AED" in result["errors"]



def test_zero_rated_invoice_with_nonzero_vat_fails():
    invoice = valid_invoice()
    invoice["vat_treatment"] = "zero-rated"
    invoice["vat"] = "5.00"
    invoice["total"] = "105.00"

    result = validate_invoice(invoice)

    assert result["valid"] is False
    assert "VAT should be zero for this VAT treatment" in result["errors"]


def test_exempt_invoice_with_nonzero_vat_fails():
    invoice = valid_invoice()
    invoice["vat_treatment"] = "exempt"
    invoice["vat"] = "5.00"
    invoice["total"] = "105.00"

    result = validate_invoice(invoice)

    assert result["valid"] is False
    assert "VAT should be zero for this VAT treatment" in result["errors"]
