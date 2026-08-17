import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

import httpx

from src.schemas import InvoiceExtracted, EnrichmentResult

logger = logging.getLogger(__name__)

# Threshold above which we flag an invoice as "high value"
HIGH_VALUE_THRESHOLD_USD = Decimal("10000")


async def _get_exchange_rate(from_currency: str, to_currency: str = "USD") -> Optional[float]:
    """
    Fetch live exchange rate from the Open Exchange Rates API (free, no key required
    for the latest endpoint via exchangerate.host).
    Falls back to None if the request fails.
    """
    if from_currency.upper() == to_currency.upper():
        return 1.0
    try:
        url = f"https://open.er-api.com/v6/latest/{from_currency.upper()}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            data = resp.json()
            rate = data.get("rates", {}).get(to_currency.upper())
            return float(rate) if rate else None
    except Exception as e:
        logger.warning("Exchange rate lookup failed for %s→%s: %s", from_currency, to_currency, e)
        return None


async def enrich_invoice(
    extracted: InvoiceExtracted,
    existing_invoice_numbers: set[str],
) -> EnrichmentResult:
    """
    Add derived fields to an extracted invoice:
    - USD normalization
    - Days until due / overdue flag
    - Duplicate detection
    - Anomaly flags
    """
    result = EnrichmentResult()
    today = date.today()
    anomaly_flags: dict[str, str] = {}

    # ── Currency normalization ────────────────────────────────────────────────
    if extracted.total is not None:
        currency = (extracted.currency or "USD").upper()
        rate = await _get_exchange_rate(currency)
        if rate is not None:
            result.total_usd = (extracted.total * Decimal(str(rate))).quantize(Decimal("0.01"))
        else:
            # Assume USD if we can't get a rate
            result.total_usd = extracted.total
            if currency != "USD":
                anomaly_flags["exchange_rate"] = f"Could not fetch rate for {currency}, assuming 1:1 USD"

    # ── Due date enrichment ───────────────────────────────────────────────────
    if extracted.due_date:
        delta = (extracted.due_date - today).days
        result.days_until_due = delta
        result.is_overdue = delta < 0

    # ── Duplicate detection ───────────────────────────────────────────────────
    if extracted.invoice_number and extracted.invoice_number in existing_invoice_numbers:
        result.is_duplicate = True
        anomaly_flags["duplicate"] = f"Invoice number {extracted.invoice_number} already exists"

    # ── Anomaly flags ─────────────────────────────────────────────────────────
    # High-value flag
    if result.total_usd and result.total_usd > HIGH_VALUE_THRESHOLD_USD:
        anomaly_flags["high_value"] = f"Invoice total ${result.total_usd} exceeds ${HIGH_VALUE_THRESHOLD_USD}"

    # Date logic sanity check
    if extracted.invoice_date and extracted.due_date:
        if extracted.due_date < extracted.invoice_date:
            anomaly_flags["date_inconsistency"] = "Due date is before invoice date"

    # Math check: does total ≈ subtotal + tax?
    if extracted.subtotal is not None and extracted.tax is not None and extracted.total is not None:
        expected = extracted.subtotal + extracted.tax
        diff = abs(expected - extracted.total)
        if diff > Decimal("0.10"):
            anomaly_flags["math_mismatch"] = (
                f"subtotal ({extracted.subtotal}) + tax ({extracted.tax}) = {expected}, "
                f"but total = {extracted.total}"
            )

    result.anomaly_flags = anomaly_flags
    return result
