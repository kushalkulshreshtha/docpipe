import logging

from src.config import get_settings
from src.schemas import InvoiceExtracted, ClassificationResult
from src.processing.extractor import _call_llm
from src.processing.prompts import CLASSIFICATION_SYSTEM_PROMPT, CLASSIFICATION_USER_PROMPT

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "Office Supplies",
    "Software/SaaS",
    "Travel",
    "Consulting",
    "Marketing",
    "Utilities",
    "Equipment",
    "Other",
}


async def classify_invoice(extracted: InvoiceExtracted) -> ClassificationResult:
    """Classify an invoice into an expense category using an LLM."""
    settings = get_settings()

    line_items_summary = "; ".join(
        item.description or "unnamed item"
        for item in (extracted.line_items or [])[:5]
    )

    user_prompt = CLASSIFICATION_USER_PROMPT.format(
        vendor_name=extracted.vendor_name or "Unknown",
        total=extracted.total or 0,
        currency=extracted.currency or "USD",
        line_items_summary=line_items_summary or "No line items",
        notes=extracted.notes or "None",
    )

    try:
        raw = await _call_llm(
            system=CLASSIFICATION_SYSTEM_PROMPT,
            user=user_prompt,
            model=settings.openai_model,
        )
        result = ClassificationResult.model_validate(raw)

        # Normalise category in case LLM slightly misspells it
        if result.category not in VALID_CATEGORIES:
            logger.warning("LLM returned unknown category '%s', defaulting to Other", result.category)
            result.category = "Other"

        return result
    except Exception as e:
        logger.error("Classification failed: %s", e)
        return ClassificationResult(category="Other", confidence=0.0)
