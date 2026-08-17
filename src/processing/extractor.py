import json
import logging
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings
from src.schemas import InvoiceExtracted
from src.processing.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT

logger = logging.getLogger(__name__)


def _get_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _call_llm(system: str, user: str, model: str) -> dict[str, Any]:
    """Call OpenAI API with JSON mode and automatic retries."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    return json.loads(content)


async def extract_invoice_data(document_text: str) -> InvoiceExtracted:
    """
    Extract structured invoice fields from raw document text using an LLM.
    Returns an InvoiceExtracted schema with all available fields populated.
    """
    settings = get_settings()

    # Truncate very long documents to avoid token limits
    max_chars = 12_000
    text = document_text[:max_chars]
    if len(document_text) > max_chars:
        logger.warning("Document truncated from %d to %d chars for extraction", len(document_text), max_chars)

    user_prompt = EXTRACTION_USER_PROMPT.format(document_text=text)

    try:
        raw = await _call_llm(
            system=EXTRACTION_SYSTEM_PROMPT,
            user=user_prompt,
            model=settings.openai_model,
        )
        logger.info("Extraction LLM returned %d top-level keys", len(raw))
        return InvoiceExtracted.model_validate(raw)
    except Exception as e:
        logger.error("Extraction failed: %s", e)
        raise
