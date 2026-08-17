"""
DocPipe Prefect Pipeline Orchestrator.

Defines the main Prefect flow and individual tasks for each pipeline step.
Each task has retry logic and structured logging.
"""

import time
import uuid
import logging
from typing import Optional

from prefect import flow, task
from prefect.logging import get_run_logger

from src.models import ProcessingStatus
from src.schemas import (
    InvoiceExtracted, ClassificationResult,
    ValidationResult, EnrichmentResult,
)
from src.storage.repository import (
    get_session_factory,
    create_document,
    get_document_by_hash,
    update_document_status,
    get_existing_invoice_numbers,
    create_invoice,
    log_task,
)
from src.ingestion.pdf_parser import ParsedDocument
from src.processing.extractor import extract_invoice_data
from src.processing.classifier import classify_invoice
from src.processing.summarizer import summarize_invoice
from src.processing.enricher import enrich_invoice
from src.validation.validator import validate_invoice


# ─── Tasks ────────────────────────────────────────────────────────────────────

@task(name="extract-fields", retries=2, retry_delay_seconds=5)
async def task_extract_fields(raw_text: str) -> InvoiceExtracted:
    logger = get_run_logger()
    logger.info("Starting LLM extraction")
    result = await extract_invoice_data(raw_text)
    logger.info("Extracted: vendor=%s, total=%s %s", result.vendor_name, result.total, result.currency)
    return result


@task(name="classify-document", retries=2, retry_delay_seconds=5)
async def task_classify(extracted: InvoiceExtracted) -> ClassificationResult:
    logger = get_run_logger()
    logger.info("Classifying invoice")
    result = await classify_invoice(extracted)
    logger.info("Category: %s (confidence=%.2f)", result.category, result.confidence)
    return result


@task(name="validate-data")
async def task_validate(extracted: InvoiceExtracted) -> ValidationResult:
    logger = get_run_logger()
    result = validate_invoice(extracted)
    logger.info("Validation status: %s (%d errors, %d warnings)", result.status, len(result.errors), len(result.warnings))
    return result


@task(name="summarize-document", retries=2, retry_delay_seconds=5)
async def task_summarize(extracted: InvoiceExtracted, classification: ClassificationResult) -> str:
    logger = get_run_logger()
    summary = await summarize_invoice(extracted, classification)
    logger.info("Summary: %s", summary[:80])
    return summary


@task(name="enrich-data")
async def task_enrich(extracted: InvoiceExtracted, existing_invoice_numbers: set[str]) -> EnrichmentResult:
    logger = get_run_logger()
    result = await enrich_invoice(extracted, existing_invoice_numbers)
    logger.info(
        "Enrichment: total_usd=%s, overdue=%s, duplicate=%s, flags=%s",
        result.total_usd, result.is_overdue, result.is_duplicate, list(result.anomaly_flags.keys()),
    )
    return result


@task(name="store-results")
async def task_store(
    document_id: uuid.UUID,
    extracted: InvoiceExtracted,
    classification: ClassificationResult,
    validation: ValidationResult,
    enrichment: EnrichmentResult,
    summary: str,
) -> None:
    logger = get_run_logger()
    session_factory = get_session_factory()

    async with session_factory() as session:
        async with session.begin():
            invoice = await create_invoice(
                session=session,
                document_id=document_id,
                extracted=extracted,
                classification=classification,
                validation=validation,
                enrichment=enrichment,
                summary=summary,
            )
            status = ProcessingStatus.WARNING if validation.status == "warning" else ProcessingStatus.COMPLETED
            await update_document_status(session, document_id, status)
            await log_task(session, document_id, "store-results", "completed")

    logger.info("Stored invoice %s for document %s", invoice.id, document_id)


# ─── Main Flow ────────────────────────────────────────────────────────────────

@flow(name="process-invoice", log_prints=True)
async def process_invoice_flow(
    document_id: uuid.UUID,
    parsed: ParsedDocument,
    filename: str,
) -> dict:
    """
    End-to-end invoice processing pipeline.
    Orchestrated as a Prefect flow with individual tasks for each step.
    """
    logger = get_run_logger()
    logger.info("Starting pipeline for document %s (%s)", document_id, filename)

    session_factory = get_session_factory()

    try:
        # Step 1: Extract fields via LLM
        extracted = await task_extract_fields(parsed.raw_text)

        # Step 2 & 3: Classification and validation can run conceptually in parallel
        # but since they're fast LLM calls we chain them for simplicity
        classification = await task_classify(extracted)
        validation = await task_validate(extracted)

        # Step 4: Summarize
        summary = await task_summarize(extracted, classification)

        # Step 5: Enrich (needs existing invoice numbers for duplicate check)
        async with session_factory() as session:
            existing_numbers = await get_existing_invoice_numbers(session)
        enrichment = await task_enrich(extracted, existing_numbers)

        # Step 6: Store everything
        await task_store(
            document_id=document_id,
            extracted=extracted,
            classification=classification,
            validation=validation,
            enrichment=enrichment,
            summary=summary,
        )

        logger.info("Pipeline completed successfully for %s", filename)
        return {
            "document_id": str(document_id),
            "status": "completed",
            "validation_status": validation.status,
            "category": classification.category,
        }

    except Exception as e:
        logger.error("Pipeline failed for document %s: %s", document_id, str(e))
        async with session_factory() as session:
            async with session.begin():
                await update_document_status(
                    session, document_id, ProcessingStatus.FAILED, error_message=str(e)
                )
                await log_task(session, document_id, "pipeline", "failed", error=str(e))
        raise
