import os
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set required environment variables for all tests and clear the settings cache."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    # Clear the lru_cache so each test gets fresh settings from env
    from src import config
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


from src.schemas import InvoiceExtracted, LineItemExtracted


@pytest.fixture
def sample_extracted() -> InvoiceExtracted:
    return InvoiceExtracted(
        vendor_name="Acme Corp",
        vendor_address="123 Main St, New York, NY 10001",
        invoice_number="INV-2024-001",
        invoice_date=date(2024, 1, 15),
        due_date=date(2024, 2, 15),
        payment_terms="Net 30",
        currency="USD",
        subtotal=Decimal("1000.00"),
        tax=Decimal("80.00"),
        total=Decimal("1080.00"),
        line_items=[
            LineItemExtracted(
                description="Software License",
                quantity=Decimal("1"),
                unit_price=Decimal("1000.00"),
                total=Decimal("1000.00"),
            )
        ],
    )


@pytest.fixture
def sample_raw_text() -> str:
    return """
    INVOICE

    Acme Corp
    123 Main St, New York, NY 10001

    Invoice #: INV-2024-001
    Invoice Date: January 15, 2024
    Due Date: February 15, 2024
    Payment Terms: Net 30

    Description          Qty    Unit Price    Total
    Software License      1      $1,000.00    $1,000.00

    Subtotal:   $1,000.00
    Tax (8%):      $80.00
    Total:      $1,080.00

    Thank you for your business!
    """
