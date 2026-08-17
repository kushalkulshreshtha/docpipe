import uuid
import logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models import ProcessingStatus
from src.schemas import (
    DocumentOut, DocumentDetailOut, CategoryBreakdown, VendorBreakdown,
)
from src.storage.repository import (
    get_session_factory,
    create_document,
    get_document_by_hash,
    list_documents,
    get_document_with_invoice,
    get_spend_by_category,
    get_spend_by_vendor,
    update_document_status,
)
from src.ingestion.pdf_parser import parse_pdf
from src.pipeline.orchestrator import process_invoice_flow

logger = logging.getLogger(__name__)


# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DocPipe — Invoice Processing API",
    description=(
        "LLM-powered invoice processing pipeline. "
        "Upload PDF invoices to extract, classify, validate, and store structured data."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Dependency ───────────────────────────────────────────────────────────────

async def get_session() -> AsyncSession:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "docpipe"}


# ─── Documents ────────────────────────────────────────────────────────────────

@app.post(
    "/documents/upload",
    response_model=DocumentOut,
    status_code=202,
    tags=["Documents"],
    summary="Upload a PDF invoice",
    description=(
        "Upload a PDF invoice or receipt. The document will be parsed, "
        "processed through the LLM pipeline, and stored in the database. "
        "Returns immediately with the document record while processing continues in the background."
    ),
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF invoice or receipt"),
    session: AsyncSession = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(file_bytes) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    # Parse PDF
    try:
        parsed = parse_pdf(file_bytes, filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {e}")

    # Duplicate check by file hash
    existing = await get_document_by_hash(session, parsed.file_hash)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This exact file was already uploaded (document_id={existing.id})",
        )

    # Create document record
    async with session.begin():
        doc = await create_document(
            session=session,
            filename=file.filename,
            file_hash=parsed.file_hash,
            file_size_bytes=parsed.file_size_bytes,
            page_count=parsed.page_count,
            is_ocr=parsed.is_ocr,
            raw_text=parsed.raw_text,
        )

    # Kick off pipeline in background
    background_tasks.add_task(
        process_invoice_flow,
        document_id=doc.id,
        parsed=parsed,
        filename=file.filename,
    )

    logger.info("Accepted document %s (%s), pipeline queued", doc.id, file.filename)
    return doc


@app.get(
    "/documents",
    response_model=list[DocumentOut],
    tags=["Documents"],
    summary="List all documents",
)
async def list_all_documents(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    docs = await list_documents(session, limit=limit, offset=offset)
    return docs


@app.get(
    "/documents/{document_id}",
    response_model=DocumentDetailOut,
    tags=["Documents"],
    summary="Get document + extracted invoice data",
)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    doc = await get_document_with_invoice(session, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetailOut(document=doc, invoice=doc.invoice)


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.get(
    "/analytics/by-category",
    response_model=list[CategoryBreakdown],
    tags=["Analytics"],
    summary="Spend breakdown by expense category",
)
async def analytics_by_category(session: AsyncSession = Depends(get_session)):
    return await get_spend_by_category(session)


@app.get(
    "/analytics/by-vendor",
    response_model=list[VendorBreakdown],
    tags=["Analytics"],
    summary="Spend breakdown by vendor (top 20)",
)
async def analytics_by_vendor(session: AsyncSession = Depends(get_session)):
    return await get_spend_by_vendor(session)
