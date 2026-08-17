from decimal import Decimal
from typing import Optional

from src.schemas import InvoiceExtracted, ValidationResult


def validate_invoice(extracted: InvoiceExtracted) -> ValidationResult:
    """
    Validate extracted invoice data against business rules.
    Returns a ValidationResult with status 'valid', 'warning', or 'error'.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── Required fields ───────────────────────────────────────────────────────
    if not extracted.vendor_name:
        warnings.append("Missing vendor name")
    if not extracted.invoice_number:
        warnings.append("Missing invoice number")
    if not extracted.total:
        errors.append("Missing invoice total — cannot process without a total amount")
    if not extracted.invoice_date:
        warnings.append("Missing invoice date")

    # ── Date logic ────────────────────────────────────────────────────────────
    if extracted.invoice_date and extracted.due_date:
        if extracted.due_date < extracted.invoice_date:
            errors.append(
                f"Due date ({extracted.due_date}) is before invoice date ({extracted.invoice_date})"
            )

    # ── Math validation ───────────────────────────────────────────────────────
    if extracted.subtotal is not None and extracted.tax is not None and extracted.total is not None:
        expected_total = extracted.subtotal + extracted.tax
        tolerance = Decimal("0.10")
        diff = abs(expected_total - extracted.total)
        if diff > tolerance:
            errors.append(
                f"Total mismatch: subtotal {extracted.subtotal} + tax {extracted.tax} = "
                f"{expected_total}, but stated total = {extracted.total} (diff: {diff})"
            )

    # Line items total vs stated subtotal
    if extracted.line_items and extracted.subtotal is not None:
        line_items_sum = sum(
            item.total for item in extracted.line_items if item.total is not None
        )
        diff = abs(line_items_sum - extracted.subtotal)
        if diff > Decimal("0.10"):
            warnings.append(
                f"Line items sum ({line_items_sum}) differs from stated subtotal ({extracted.subtotal})"
            )

    # ── Determine overall status ──────────────────────────────────────────────
    if errors:
        status = "error"
    elif warnings:
        status = "warning"
    else:
        status = "valid"

    return ValidationResult(status=status, errors=errors, warnings=warnings)
