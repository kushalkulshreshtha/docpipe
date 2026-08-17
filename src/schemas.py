from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ─── Line Items ────────────────────────────────────────────────────────────────

class LineItemExtracted(BaseModel):
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    total: Optional[Decimal] = None


class LineItemOut(LineItemExtracted):
    id: UUID

    model_config = {"from_attributes": True}


# ─── Extracted Invoice Data (from LLM) ────────────────────────────────────────

class InvoiceExtracted(BaseModel):
    """Structured output from the LLM extraction step."""

    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    currency: Optional[str] = Field(None, description="ISO 4217 currency code, e.g. USD, EUR")
    subtotal: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    total: Optional[Decimal] = None
    line_items: list[LineItemExtracted] = Field(default_factory=list)


# ─── Classification ────────────────────────────────────────────────────────────

class ClassificationResult(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None


# ─── Validation ────────────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    status: str  # "valid" | "warning" | "error"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ─── Enrichment ────────────────────────────────────────────────────────────────

class EnrichmentResult(BaseModel):
    total_usd: Optional[Decimal] = None
    days_until_due: Optional[int] = None
    is_overdue: Optional[bool] = None
    is_duplicate: bool = False
    anomaly_flags: dict = Field(default_factory=dict)


# ─── API Response Schemas ──────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: UUID
    filename: str
    status: str
    page_count: Optional[int]
    is_ocr: bool
    created_at: datetime
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class InvoiceOut(BaseModel):
    id: UUID
    document_id: UUID
    vendor_name: Optional[str]
    vendor_address: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[date]
    due_date: Optional[date]
    payment_terms: Optional[str]
    notes: Optional[str]
    currency: Optional[str]
    subtotal: Optional[Decimal]
    tax: Optional[Decimal]
    total: Optional[Decimal]
    total_usd: Optional[Decimal]
    category: Optional[str]
    category_confidence: Optional[float]
    summary: Optional[str]
    days_until_due: Optional[int]
    is_overdue: Optional[bool]
    is_duplicate: bool
    anomaly_flags: Optional[dict]
    validation_status: str
    validation_errors: Optional[dict]
    line_items: list[LineItemOut] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailOut(BaseModel):
    document: DocumentOut
    invoice: Optional[InvoiceOut]

    model_config = {"from_attributes": True}


# ─── Analytics ────────────────────────────────────────────────────────────────

class CategoryBreakdown(BaseModel):
    category: str
    count: int
    total_usd: Decimal


class VendorBreakdown(BaseModel):
    vendor_name: str
    count: int
    total_usd: Decimal
