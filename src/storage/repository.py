import uuid
import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from src.config import get_settings
from src.models import Document, Invoice, LineItem, ProcessingLog, ProcessingStatus
from src.schemas import (
    InvoiceExtracted, ClassificationResult, ValidationResult,
    EnrichmentResult, CategoryBreakdown, VendorBreakdown,
)

logger = logging.getLogger(__name__)

# ─── Engine & Session Factory ──────────────────────────────────────────────────

def create_engine():
    settings = get_settings()
    url = settings.database_url
    connect_args = {}

    # asyncpg doesn't accept ?sslmode=require — strip it and pass ssl=True via connect_args
    if "sslmode=require" in url:
        url = url.replace("?sslmode=require", "").replace("&sslmode=require", "")
        connect_args["ssl"] = True

    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args,
    )


_engine = None
_session_factory = None


def get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine()
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


# ─── Document Repository ───────────────────────────────────────────────────────

async def create_document(
    session: AsyncSession,
    filename: str,
    file_hash: str,
    file_size_bytes: int,
    page_count: Optional[int],
    is_ocr: bool,
    raw_text: str,
) -> Document:
    doc = Document(
        filename=filename,
        file_hash=file_hash,
        file_size_bytes=file_size_bytes,
        page_count=page_count,
        is_ocr=is_ocr,
        raw_text=raw_text,
        status=ProcessingStatus.PENDING,
    )
    session.add(doc)
    await session.flush()
    return doc


async def get_document_by_hash(session: AsyncSession, file_hash: str) -> Optional[Document]:
    result = await session.execute(select(Document).where(Document.file_hash == file_hash))
    return result.scalar_one_or_none()


async def update_document_status(
    session: AsyncSession,
    document_id: uuid.UUID,
    status: ProcessingStatus,
    error_message: Optional[str] = None,
) -> None:
    await session.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status=status, error_message=error_message)
    )


async def list_documents(session: AsyncSession, limit: int = 50, offset: int = 0) -> list[Document]:
    result = await session.execute(
        select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def get_document_with_invoice(session: AsyncSession, document_id: uuid.UUID) -> Optional[Document]:
    result = await session.execute(
        select(Document)
        .options(selectinload(Document.invoice).selectinload(Invoice.line_items))
        .where(Document.id == document_id)
    )
    return result.scalar_one_or_none()


# ─── Invoice Repository ────────────────────────────────────────────────────────

async def get_existing_invoice_numbers(session: AsyncSession) -> set[str]:
    result = await session.execute(
        select(Invoice.invoice_number).where(Invoice.invoice_number.isnot(None))
    )
    return {row[0] for row in result.all()}


async def create_invoice(
    session: AsyncSession,
    document_id: uuid.UUID,
    extracted: InvoiceExtracted,
    classification: ClassificationResult,
    validation: ValidationResult,
    enrichment: EnrichmentResult,
    summary: str,
) -> Invoice:
    invoice = Invoice(
        document_id=document_id,
        vendor_name=extracted.vendor_name,
        vendor_address=extracted.vendor_address,
        invoice_number=extracted.invoice_number,
        invoice_date=extracted.invoice_date,
        due_date=extracted.due_date,
        payment_terms=extracted.payment_terms,
        notes=extracted.notes,
        currency=extracted.currency,
        subtotal=extracted.subtotal,
        tax=extracted.tax,
        total=extracted.total,
        total_usd=enrichment.total_usd,
        category=classification.category,
        category_confidence=classification.confidence,
        summary=summary,
        days_until_due=enrichment.days_until_due,
        is_overdue=enrichment.is_overdue,
        is_duplicate=enrichment.is_duplicate,
        anomaly_flags=enrichment.anomaly_flags or {},
        validation_status=validation.status,
        validation_errors={
            "errors": validation.errors,
            "warnings": validation.warnings,
        } if (validation.errors or validation.warnings) else None,
    )
    session.add(invoice)
    await session.flush()

    # Insert line items
    for item in extracted.line_items:
        li = LineItem(
            invoice_id=invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total=item.total,
        )
        session.add(li)

    return invoice


# ─── Processing Logs ───────────────────────────────────────────────────────────

async def log_task(
    session: AsyncSession,
    document_id: uuid.UUID,
    task_name: str,
    status: str,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    log = ProcessingLog(
        document_id=document_id,
        task_name=task_name,
        status=status,
        duration_ms=duration_ms,
        error=error,
        task_metadata=metadata,
    )
    session.add(log)


# ─── Analytics ────────────────────────────────────────────────────────────────

async def get_spend_by_category(session: AsyncSession) -> list[CategoryBreakdown]:
    result = await session.execute(
        select(
            Invoice.category,
            func.count(Invoice.id).label("count"),
            func.sum(Invoice.total_usd).label("total_usd"),
        )
        .where(Invoice.total_usd.isnot(None))
        .group_by(Invoice.category)
        .order_by(func.sum(Invoice.total_usd).desc())
    )
    return [
        CategoryBreakdown(
            category=row.category or "Uncategorized",
            count=row.count,
            total_usd=row.total_usd or Decimal(0),
        )
        for row in result.all()
    ]


async def get_spend_by_vendor(session: AsyncSession, limit: int = 20) -> list[VendorBreakdown]:
    result = await session.execute(
        select(
            Invoice.vendor_name,
            func.count(Invoice.id).label("count"),
            func.sum(Invoice.total_usd).label("total_usd"),
        )
        .where(Invoice.vendor_name.isnot(None), Invoice.total_usd.isnot(None))
        .group_by(Invoice.vendor_name)
        .order_by(func.sum(Invoice.total_usd).desc())
        .limit(limit)
    )
    return [
        VendorBreakdown(
            vendor_name=row.vendor_name,
            count=row.count,
            total_usd=row.total_usd or Decimal(0),
        )
        for row in result.all()
    ]
