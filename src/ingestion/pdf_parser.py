import hashlib
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    raw_text: str
    page_count: int
    file_hash: str
    file_size_bytes: int
    is_ocr: bool


def _extract_text_pdfplumber(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text from a text-based PDF using pdfplumber."""
    text_parts: list[str] = []
    page_count = 0

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n\n".join(text_parts), page_count


def _extract_text_ocr(pdf_bytes: bytes) -> tuple[str, int]:
    """OCR fallback for image-based PDFs using pytesseract + pdf2image."""
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError as e:
        raise RuntimeError(
            "OCR dependencies not installed. Run: pip install pytesseract pdf2image"
        ) from e

    images = convert_from_bytes(pdf_bytes, dpi=300)
    text_parts: list[str] = []

    for img in images:
        text = pytesseract.image_to_string(img, config="--psm 6")
        if text.strip():
            text_parts.append(text)

    return "\n\n".join(text_parts), len(images)


def parse_pdf(file_bytes: bytes, filename: str = "") -> ParsedDocument:
    """
    Parse a PDF, automatically falling back to OCR if text extraction yields
    insufficient content (i.e. the PDF is image-based / scanned).
    """
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size = len(file_bytes)
    is_ocr = False

    try:
        text, page_count = _extract_text_pdfplumber(file_bytes)
    except Exception as e:
        logger.warning("pdfplumber failed for %s: %s — falling back to OCR", filename, e)
        text = ""
        page_count = 0

    # If we got very little text, the PDF is likely scanned — try OCR
    min_text_length = 50
    if len(text.strip()) < min_text_length:
        logger.info("Insufficient text extracted from %s (%d chars), attempting OCR", filename, len(text))
        try:
            text, page_count = _extract_text_ocr(file_bytes)
            is_ocr = True
        except Exception as e:
            logger.error("OCR failed for %s: %s", filename, e)
            # Return whatever we have from pdfplumber (even if empty)

    logger.info(
        "Parsed %s: %d pages, %d chars, ocr=%s",
        filename, page_count, len(text), is_ocr,
    )

    return ParsedDocument(
        raw_text=text,
        page_count=page_count,
        file_hash=file_hash,
        file_size_bytes=file_size,
        is_ocr=is_ocr,
    )


def parse_pdf_from_path(path: Path) -> ParsedDocument:
    return parse_pdf(path.read_bytes(), filename=path.name)
