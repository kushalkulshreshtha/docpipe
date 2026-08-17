import pytest
from decimal import Decimal
from datetime import date

from src.validation.validator import validate_invoice
from src.schemas import InvoiceExtracted, LineItemExtracted


def test_valid_invoice_passes(sample_extracted: InvoiceExtracted):
    """A well-formed invoice should pass validation."""
    result = validate_invoice(sample_extracted)
    assert result.status == "valid"
    assert result.errors == []


def test_missing_total_is_error():
    """Missing total should produce a validation error."""
    invoice = InvoiceExtracted(vendor_name="Acme", total=None)
    result = validate_invoice(invoice)
    assert result.status == "error"
    assert any("total" in e.lower() for e in result.errors)


def test_missing_vendor_is_warning():
    """Missing vendor name should produce a warning, not an error."""
    invoice = InvoiceExtracted(vendor_name=None, total=Decimal("100.00"))
    result = validate_invoice(invoice)
    assert result.status == "warning"
    assert any("vendor" in w.lower() for w in result.warnings)


def test_due_date_before_invoice_date_is_error():
    """Due date before invoice date should be an error."""
    invoice = InvoiceExtracted(
        vendor_name="Acme",
        total=Decimal("100.00"),
        invoice_date=date(2024, 3, 1),
        due_date=date(2024, 1, 1),
    )
    result = validate_invoice(invoice)
    assert result.status == "error"
    assert any("due date" in e.lower() for e in result.errors)


def test_math_mismatch_is_error():
    """Subtotal + tax not equalling total should be an error."""
    invoice = InvoiceExtracted(
        vendor_name="Acme",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        total=Decimal("200.00"),  # Wrong!
    )
    result = validate_invoice(invoice)
    assert result.status == "error"
    assert any("mismatch" in e.lower() for e in result.errors)


def test_math_within_tolerance_passes():
    """Small rounding differences (≤ $0.10) should not cause errors."""
    invoice = InvoiceExtracted(
        vendor_name="Acme",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        total=Decimal("110.05"),  # 5 cents off — within tolerance
    )
    result = validate_invoice(invoice)
    # Should not have a math mismatch error
    assert not any("mismatch" in e.lower() for e in result.errors)


def test_line_items_sum_mismatch_is_warning():
    """Line items not summing to subtotal should produce a warning."""
    invoice = InvoiceExtracted(
        vendor_name="Acme",
        total=Decimal("200.00"),
        subtotal=Decimal("200.00"),
        line_items=[
            LineItemExtracted(description="Item A", total=Decimal("50.00")),
            LineItemExtracted(description="Item B", total=Decimal("50.00")),
            # Sum = 100, but subtotal = 200
        ],
    )
    result = validate_invoice(invoice)
    assert any("line items" in w.lower() for w in result.warnings)
