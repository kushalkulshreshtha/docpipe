import pytest
from unittest.mock import AsyncMock, patch

from src.processing.classifier import classify_invoice
from src.schemas import InvoiceExtracted, ClassificationResult, LineItemExtracted
from decimal import Decimal


@pytest.mark.asyncio
async def test_classify_software_invoice(sample_extracted: InvoiceExtracted):
    """A software license invoice should be classified as Software/SaaS."""
    mock_response = {
        "category": "Software/SaaS",
        "confidence": 0.95,
        "reasoning": "Invoice contains a software license line item",
    }

    with patch("src.processing.classifier._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_invoice(sample_extracted)

        assert result.category == "Software/SaaS"
        assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_classify_defaults_unknown_category():
    """An unknown category returned by LLM should default to 'Other'."""
    mock_response = {
        "category": "Miscellaneous XYZ",  # Not a valid category
        "confidence": 0.5,
        "reasoning": "...",
    }

    invoice = InvoiceExtracted(vendor_name="Test", total=Decimal("100"))

    with patch("src.processing.classifier._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_invoice(invoice)

        assert result.category == "Other"


@pytest.mark.asyncio
async def test_classify_handles_llm_failure():
    """Classification should gracefully handle LLM failures."""
    invoice = InvoiceExtracted(vendor_name="Test", total=Decimal("100"))

    with patch("src.processing.classifier._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("OpenAI API timeout")
        result = await classify_invoice(invoice)

        # Should fall back to "Other" with 0 confidence
        assert result.category == "Other"
        assert result.confidence == 0.0
