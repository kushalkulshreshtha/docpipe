import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Text, Numeric, Boolean, Integer, DateTime,
    Date, ForeignKey, JSON, Enum as SAEnum, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    WARNING = "warning"


class ExpenseCategory(str, enum.Enum):
    OFFICE_SUPPLIES = "Office Supplies"
    SOFTWARE_SAAS = "Software/SaaS"
    TRAVEL = "Travel"
    CONSULTING = "Consulting"
    MARKETING = "Marketing"
    UTILITIES = "Utilities"
    EQUIPMENT = "Equipment"
    OTHER = "Other"


class Document(Base):
    """Raw document metadata — one row per uploaded file."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    is_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus), default=ProcessingStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="document", uselist=False)
    processing_logs: Mapped[list["ProcessingLog"]] = relationship(back_populates="document")


class Invoice(Base):
    """Structured data extracted from an invoice document."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), unique=True, nullable=False)

    # Vendor
    vendor_name: Mapped[Optional[str]] = mapped_column(String(255))
    vendor_address: Mapped[Optional[str]] = mapped_column(Text)

    # Invoice meta
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_date: Mapped[Optional[date]] = mapped_column(Date)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Amounts
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    total_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))

    # Classification & enrichment
    category: Mapped[Optional[ExpenseCategory]] = mapped_column(SAEnum(ExpenseCategory))
    category_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    days_until_due: Mapped[Optional[int]] = mapped_column(Integer)
    is_overdue: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_flags: Mapped[Optional[dict]] = mapped_column(JSON)

    # Validation
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")
    validation_errors: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="invoice")
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class LineItem(Base):
    """Individual line items within an invoice."""

    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))

    invoice: Mapped["Invoice"] = relationship(back_populates="line_items")


class ProcessingLog(Base):
    """Audit trail for every pipeline task execution."""

    __tablename__ = "processing_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error: Mapped[Optional[str]] = mapped_column(Text)
    task_metadata: Mapped[Optional[dict]] = mapped_column(JSON, name="metadata")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="processing_logs")
