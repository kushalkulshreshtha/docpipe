import logging

from src.config import get_settings
from src.schemas import InvoiceExtracted, ClassificationResult
from src.processing.extractor import _call_llm
from src.processing.prompts import SUMMARIZATION_SYSTEM_PROMPT, SUMMARIZATION_USER_PROMPT

logger = logging.getLogger(__name__)


async def summarize_invoice(
    extracted: InvoiceExtracted,
    classification: ClassificationResult,
) -> str:
    """Generate a concise human-readable summary of an invoice."""
    settings = get_settings()

    line_items_summary = "; ".join(
        item.description or "unnamed item"
        for item in (extracted.line_items or [])[:5]
    )

    user_prompt = SUMMARIZATION_USER_PROMPT.format(
        vendor_name=extracted.vendor_name or "Unknown vendor",
        invoice_number=extracted.invoice_number or "N/A",
        invoice_date=extracted.invoice_date or "N/A",
        due_date=extracted.due_date or "N/A",
        total=extracted.total or 0,
        currency=extracted.currency or "USD",
        category=classification.category,
        line_items_summary=line_items_summary or "No line items",
    )

    try:
        raw = await _call_llm(
            system=SUMMARIZATION_SYSTEM_PROMPT,
            user=user_prompt,
            model=settings.openai_model,
        )
        return raw.get("summary", "")
    except Exception as e:
        logger.error("Summarization failed: %s", e)
        # Fallback to a simple template summary
        return (
            f"{extracted.total} {extracted.currency} invoice from "
            f"{extracted.vendor_name or 'Unknown'} — {classification.category}"
        )
