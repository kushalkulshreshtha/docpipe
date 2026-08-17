import pytest
import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from src.processing.extractor import extract_invoice_data
from src.schemas import InvoiceExtracted


MOCK_LLM_RESPONSE = {
    "vendor_name": "Acme Corp",
    "vendor_address": "123 Main St, New York, NY 10001",
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-01-15",
    "due_date": "2024-02-15",
    "payment_terms": "Net 30",
    "currency": "USD",
    "subtotal": 1000.00,
    "tax": 80.00,
    "total": 1080.00,
    "notes": None,
    "line_items": [
        {
            "description": "Software License",
            "quantity": 1,
            "unit_price": 1000.00,
            "total": 1000.00,
        }
    ],
}


@pytest.mark.asyncio
async def test_extract_invoice_data_success(sample_raw_text: str):
    """Extraction should parse LLM JSON response into InvoiceExtracted schema."""
    with patch("src.processing.extractor._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE

        result = await extract_invoice_data(sample_raw_text)

        assert isinstance(result, InvoiceExtracted)
        assert result.vendor_name == "Acme Corp"
        assert result.invoice_number == "INV-2024-001"
        assert result.total == Decimal("1080.00")
        assert len(result.line_items) == 1
        assert result.line_items[0].description == "Software License"


@pytest.mark.asyncio
async def test_extract_invoice_data_partial_response():
    """Extraction should handle partial LLM responses gracefully."""
    partial_response = {
        "vendor_name": "Partial Corp",
        "total": 500.00,
        "line_items": [],
    }

    with patch("src.processing.extractor._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = partial_response

        result = await extract_invoice_data("Some invoice text")

        assert result.vendor_name == "Partial Corp"
        assert result.total == Decimal("500.00")
        assert result.invoice_number is None
        assert result.line_items == []


@pytest.mark.asyncio
async def test_extract_invoice_data_truncates_long_text():
    """Very long documents should be truncated before sending to LLM."""
    long_text = "A" * 20_000

    with patch("src.processing.extractor._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"line_items": []}

        await extract_invoice_data(long_text)

        # Verify the LLM was called with truncated text
        call_args = mock_llm.call_args
        user_prompt = call_args.kwargs.get("user") or call_args.args[1]
        # The truncated text (12000 chars) should appear in the prompt, not all 20000
        assert len(user_prompt) < 15_000
