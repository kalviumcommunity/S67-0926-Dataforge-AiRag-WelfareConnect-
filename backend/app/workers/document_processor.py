"""
Document processing worker.
Performs PDF validation, page-by-page extraction, scanned page detection,
selective page rendering, OCR execution with confidence tracking, text deduplication,
and semantic page-bounded chunking.
"""

import hashlib
import io
import logging
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
from pydantic import BaseModel, Field
import pypdf
from backend.app.config import settings
from backend.app.services.ocr_service import OcrResult, ocr_service
from backend.app.workers.chunker import SemanticChunk, SemanticChunker

logger = logging.getLogger(__name__)


class ProcessedChunk(BaseModel):
    chunk_index: int
    page_number: int
    page_range: str = "1"
    section_heading: Optional[str] = None
    chunk_text: str  # Verbatim exact text for citation display
    normalized_text: Optional[str] = None  # Cleaned / normalized text for search
    token_count: int = 0
    word_count: int = 0
    start_char_offset: int = 0
    end_char_offset: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessedPage(BaseModel):
    page_number: int
    raw_text: str  # Canonical deduplicated text
    native_text: Optional[str] = None
    ocr_text: Optional[str] = None
    extraction_method: str = "NATIVE"  # "NATIVE", "OCR", "HYBRID"
    ocr_confidence: Optional[float] = None
    is_scanned: bool = False
    requires_admin_review: bool = False
    review_reason: Optional[str] = None
    word_count: int = 0
    chunks: List[ProcessedChunk] = []


class ProcessingPipelineResult(BaseModel):
    success: bool
    document_id: str
    version_id: str
    file_hash: str
    file_size_bytes: int
    total_pages: int
    native_text_pages: int
    ocr_pages: int
    failed_pages: int
    low_confidence_pages: int
    scanned_pages: int
    pages: List[ProcessedPage] = []
    chunks: List[ProcessedChunk] = []
    error_message: Optional[str] = None


class DocumentProcessor:
    @staticmethod
    def calculate_sha256(file_bytes: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(file_bytes).hexdigest()

    @staticmethod
    def validate_pdf(file_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate PDF format and readability.
        Checks header signature and verifies pypdf can read page structure.
        """
        if not file_bytes:
            return False, "File is empty (0 bytes)."

        if not file_bytes.startswith(b"%PDF-"):
            return False, "Invalid PDF file: Missing '%PDF-' header signature."

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if len(reader.pages) == 0:
                return False, "PDF contains zero readable pages."
            # Attempt access to the first page structure
            _ = reader.pages[0]
            return True, None
        except Exception as e:
            return False, f"Corrupted or unreadable PDF: {str(e)}"

    @classmethod
    def render_page_image(cls, file_bytes: bytes, page_index: int, dpi: int = 200) -> Optional[Image.Image]:
        """
        Render a single PDF page into a PIL Image at specified DPI using pypdfium2.
        Operates entirely in-memory to prevent exposing temporary images.
        """
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_bytes)
            if page_index >= len(pdf):
                return None
            page = pdf[page_index]
            # scale = dpi / 72.0
            scale = dpi / 72.0
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            return pil_image
        except Exception as e:
            logger.warning(f"pypdfium2 rendering failed for page {page_index + 1}: {e}")
            # Fallback: check if image can be created from embedded page images in pypdf
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pdf_page = reader.pages[page_index]
                if pdf_page.images:
                    # Return first embedded image
                    first_img = pdf_page.images[0]
                    return Image.open(io.BytesIO(first_img.data))
            except Exception:
                pass
            # Return placeholder clean image for processing continuity
            return Image.new("RGB", (800, 1100), color=(255, 255, 255))

    @staticmethod
    def clean_text_structure(text: str) -> str:
        """
        Preserve headings and paragraph boundaries while normalizing whitespace.
        """
        if not text:
            return ""

        # Normalize line breaks
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split into logical lines
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
            elif cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")  # Preserve single empty line for paragraph boundary

        # Join preserving double newlines for paragraphs
        result = "\n".join(cleaned_lines)
        # Collapse multiple blank lines into two newlines
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    @classmethod
    def deduplicate_text(cls, native_text: Optional[str], ocr_text: Optional[str]) -> Tuple[str, str]:
        """
        Intelligently merge native text and OCR text without duplicating overlapping content.
        Returns: (canonical_raw_text, extraction_method)
        """
        clean_native = cls.clean_text_structure(native_text or "")
        clean_ocr = cls.clean_text_structure(ocr_text or "")

        native_words = clean_native.split()
        ocr_words = clean_ocr.split()

        if clean_native and clean_ocr:
            # Exact match: prefer native
            if clean_native.lower() == clean_ocr.lower():
                return clean_native, "NATIVE"
            # Native text is comprehensive
            if len(native_words) >= settings.OCR_MIN_WORD_THRESHOLD:
                return clean_native, "NATIVE"
            # Native text is just a tiny fragment inside OCR
            if clean_native.lower() in clean_ocr.lower() and len(ocr_words) > len(native_words):
                return clean_ocr, "OCR"
            # OCR is a substring of native
            if clean_ocr.lower() in clean_native.lower():
                return clean_native, "NATIVE"
            # Combine distinct sections preserving order
            combined = f"{clean_native}\n\n{clean_ocr}"
            return cls.clean_text_structure(combined), "HYBRID"

        if clean_native:
            return clean_native, "NATIVE"
        if clean_ocr:
            return clean_ocr, "OCR"
        return "", "NATIVE"


    @classmethod
    def chunk_page_text(
        cls,
        page_number: int,
        text: str,
        start_chunk_index: int = 0,
        page_range: Optional[str] = None,
        max_words_per_chunk: int = 350,
        overlap_words: int = 40,
        metadata_context: Optional[Dict[str, Any]] = None,
    ) -> List[ProcessedChunk]:
        """
        Divide page text into semantic chunks bounded by headings, tables, and paragraph boundaries.
        Utilizes SemanticChunker for structural integrity and search normalization.
        """
        semantic_chunks = SemanticChunker.chunk_page(
            page_number=page_number,
            text=text,
            start_chunk_index=start_chunk_index,
            page_range=page_range,
            max_words=max_words_per_chunk,
            overlap_words=overlap_words,
            metadata_context=metadata_context,
        )
        return [
            ProcessedChunk(
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                page_range=c.page_range,
                section_heading=c.section_heading,
                chunk_text=c.chunk_text,
                normalized_text=c.normalized_text,
                token_count=c.token_count,
                word_count=c.word_count,
                start_char_offset=c.start_char_offset,
                end_char_offset=c.end_char_offset,
                metadata=c.metadata,
            )
            for c in semantic_chunks
        ]

    @classmethod
    def process_document_bytes(
        cls,
        file_bytes: bytes,
        document_id: str,
        version_id: str,
    ) -> ProcessingPipelineResult:
        """
        Execute full document processing pipeline:
        1. Validate PDF readability.
        2. Extract page-by-page native text and preserve headings/paragraphs.
        3. Detect scanned pages (low word count).
        4. Render scanned pages and run OCR with confidence scoring.
        5. Deduplicate native and OCR text.
        6. Generate page-bounded semantic chunks.
        7. Compile processing summary metrics.
        """
        is_valid, validation_err = cls.validate_pdf(file_bytes)
        if not is_valid:
            return ProcessingPipelineResult(
                success=False,
                document_id=document_id,
                version_id=version_id,
                file_hash=cls.calculate_sha256(file_bytes) if file_bytes else "empty",
                file_size_bytes=len(file_bytes),
                total_pages=0,
                native_text_pages=0,
                ocr_pages=0,
                failed_pages=1,
                low_confidence_pages=0,
                scanned_pages=0,
                error_message=validation_err,
            )

        file_hash = cls.calculate_sha256(file_bytes)
        file_size = len(file_bytes)

        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        total_pages = len(reader.pages)

        processed_pages: List[ProcessedPage] = []
        all_chunks: List[ProcessedChunk] = []

        native_count = 0
        ocr_count = 0
        scanned_count = 0
        low_conf_count = 0
        failed_count = 0
        current_chunk_idx = 0

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            try:
                # 1. Native text extraction
                page_obj = reader.pages[page_idx]
                raw_native = page_obj.extract_text() or ""
                cleaned_native = cls.clean_text_structure(raw_native)
                native_word_count = len(cleaned_native.split())

                # 2. Detect if page is scanned / low text
                is_scanned = native_word_count < settings.OCR_MIN_WORD_THRESHOLD
                ocr_text: Optional[str] = None
                ocr_conf: Optional[float] = None
                req_review = False
                review_reason: Optional[str] = None
                method = "NATIVE"

                if is_scanned:
                    scanned_count += 1
                    # Render page image securely in-memory
                    page_img = cls.render_page_image(file_bytes, page_idx, dpi=settings.OCR_DPI)
                    if page_img is not None:
                        ocr_res = ocr_service.perform_ocr(
                            page_img,
                            confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD,
                        )
                        ocr_text = ocr_res.text
                        ocr_conf = ocr_res.confidence
                        req_review = ocr_res.requires_review
                        review_reason = ocr_res.review_reason

                        if req_review:
                            low_conf_count += 1

                # 3. Deduplicate native and OCR text
                canonical_text, method = cls.deduplicate_text(cleaned_native, ocr_text)

                if method in ("OCR", "HYBRID"):
                    ocr_count += 1
                else:
                    native_count += 1

                word_count = len(canonical_text.split())

                # 4. Chunk page text
                page_chunks = cls.chunk_page_text(
                    page_number=page_num,
                    text=canonical_text,
                    start_chunk_index=current_chunk_idx,
                )
                current_chunk_idx += len(page_chunks)
                all_chunks.extend(page_chunks)

                processed_page = ProcessedPage(
                    page_number=page_num,
                    raw_text=canonical_text,
                    native_text=cleaned_native if cleaned_native else None,
                    ocr_text=ocr_text,
                    extraction_method=method,
                    ocr_confidence=ocr_conf,
                    is_scanned=is_scanned,
                    requires_admin_review=req_review,
                    review_reason=review_reason,
                    word_count=word_count,
                    chunks=page_chunks,
                )
                processed_pages.append(processed_page)

            except Exception as page_err:
                logger.error(f"Error processing page {page_num}: {page_err}")
                failed_count += 1
                processed_pages.append(
                    ProcessedPage(
                        page_number=page_num,
                        raw_text=f"Extraction failed for page {page_num}.",
                        extraction_method="FAILED",
                        requires_admin_review=True,
                        review_reason=f"Page extraction error: {str(page_err)}",
                        word_count=0,
                    )
                )

        return ProcessingPipelineResult(
            success=True,
            document_id=document_id,
            version_id=version_id,
            file_hash=file_hash,
            file_size_bytes=file_size,
            total_pages=total_pages,
            native_text_pages=native_count,
            ocr_pages=ocr_count,
            failed_pages=failed_count,
            low_confidence_pages=low_conf_count,
            scanned_pages=scanned_count,
            pages=processed_pages,
            chunks=all_chunks,
        )
