"""
Semantic Chunking Module.
Implements intelligent semantic document chunking for extracted PDF/OCR page text.

Key Capabilities:
1. Document and Page Traceability: Retains document_id, version_id, page_id, page_number, and page_range.
2. Section Heading Detection & Propagation: Tracks section headings (e.g., 'Section 1:', 'Eligibility Criteria:', '## Heading')
   and attaches the active section heading to chunks.
3. Table & Structured Block Preservation: Detects tabular rows (pipe-delimited '|', colon pairs, key-value bullets)
   and keeps rows with their headers within chunk boundaries.
4. Balanced Sizing & Overlap: Configurable chunk word limits (default 250-400 words) with sliding-window overlap (30-50 words).
5. Verbatim vs Normalized Text: Produces exact verbatim text for citation display and normalized text for lexical/vector search.
6. Rich Metadata Attachment: Attaches scheme_name, department, location, language, effective_date, active_version, heading, etc.
7. Noise & Empty Filter: Discards empty or meaningless chunks (< 5 words or pure symbols).
"""

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SemanticChunk(BaseModel):
    """Structured chunk representation ready for database persistence and search indexing."""
    chunk_index: int
    page_number: int
    page_range: str = "1"
    section_heading: Optional[str] = None
    chunk_text: str  # Verbatim exact text for frontend citation display
    normalized_text: str  # Cleaned / standardized text for search
    token_count: int
    word_count: int
    start_char_offset: int
    end_char_offset: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticChunker:
    """
    Intelligent semantic text chunker that preserves structure,
    table integrity, section context, and dual text representations.
    """

    DEFAULT_MAX_WORDS: int = 350
    DEFAULT_OVERLAP_WORDS: int = 40
    MIN_CHUNK_WORDS: int = 5

    # Heading detection patterns (e.g., "1. Scheme Overview", "SECTION 4: BENEFITS", "## Guidelines", "Scheme Objective:")
    HEADING_PATTERNS = [
        re.compile(r"^(?:section\s+\d+|clause\s+\d+|article\s+\d+|chapter\s+\d+)\b[:\.\-]?\s*.*$", re.IGNORECASE),
        re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-Za-z0-9\s,\-\(\)\/\']{2,80}$"),
        re.compile(r"^#{1,6}\s+.*$"),
        re.compile(r"^[A-Z0-9\s,\-\(\)\/\']{4,80}:(?:\s*.*)?$"),
        re.compile(r"^(?:eligibility|benefits|application process|documents required|financial assistance|guidelines|overview|terms and conditions|objectives|target group)\b.*$", re.IGNORECASE),
    ]

    # Table or structured key-value line pattern
    TABLE_OR_KV_PATTERN = re.compile(r"(?:\|.*\|)|(?:\b[A-Za-z0-9\s]{2,30}\s*:\s*.+)|(?:^[\-\*]\s+[A-Za-z0-9\s]{2,30}\s*:\s*.+)")

    @classmethod
    def normalize_text_for_search(cls, text: str) -> str:
        """
        Normalize text for lexical and semantic search:
        - Unicode normalization (NFKC)
        - Lowercase
        - Replace dashes, bullets, and excessive punctuation with standard whitespace
        - Standardize multiple whitespace and newline characters
        """
        if not text:
            return ""
        # 1. Normalize unicode
        normalized = unicodedata.normalize("NFKC", text)
        # 2. Lowercase
        normalized = normalized.lower()
        # 3. Replace special punctuation/symbols with space while keeping alphanumeric and essential terms
        normalized = re.sub(r"[^\w\s\.\,\-\%\/\:\;]", " ", normalized)
        # 4. Collapse multiple spaces / tabs / newlines into a single space
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def is_heading(cls, line: str) -> bool:
        """Check if a line looks like a structural section heading."""
        cleaned = line.strip()
        if not cleaned or len(cleaned) > 120:
            return False
        for pattern in cls.HEADING_PATTERNS:
            if pattern.match(cleaned):
                return True
        # Check for short ALL-CAPS titles (e.g., "ELIGIBILITY CRITERIA")
        if cleaned.isupper() and len(cleaned.split()) <= 8 and len(cleaned) >= 4:
            return True
        return False

    @classmethod
    def is_meaningful(cls, text: str, min_words: int = MIN_CHUNK_WORDS) -> bool:
        """
        Check if text is meaningful (not empty, has at least min_words, and contains alphanumeric chars).
        """
        if not text:
            return False
        words = text.split()
        if len(words) < min_words:
            return False
        # Must contain at least some alphanumeric content
        alphanumeric_count = sum(1 for c in text if c.isalnum())
        if alphanumeric_count < 10:
            return False
        return True

    @classmethod
    def _group_lines_into_blocks(cls, text: str) -> List[Dict[str, Any]]:
        """
        Parse text into semantic blocks (headings, tables/key-value clusters, paragraphs).
        Keeps table rows together with their headers.
        """
        raw_lines = text.split("\n")
        blocks: List[Dict[str, Any]] = []
        current_block_lines: List[str] = []
        current_block_type = "PARAGRAPH"  # HEADING, TABLE, PARAGRAPH
        active_heading: Optional[str] = None

        def flush_block():
            nonlocal current_block_lines, current_block_type
            if current_block_lines:
                block_content = "\n".join(current_block_lines).strip()
                if block_content:
                    blocks.append({
                        "type": current_block_type,
                        "text": block_content,
                        "heading": active_heading,
                        "lines": list(current_block_lines),
                    })
                current_block_lines = []

        i = 0
        while i < len(raw_lines):
            line = raw_lines[i].rstrip()
            stripped = line.strip()

            if not stripped:
                # Blank line indicates paragraph boundary (unless inside a table)
                if current_block_type != "TABLE":
                    flush_block()
                    current_block_type = "PARAGRAPH"
                i += 1
                continue

            # Check if this line is a heading
            if cls.is_heading(stripped):
                flush_block()
                active_heading = stripped.lstrip("#").strip()
                blocks.append({
                    "type": "HEADING",
                    "text": stripped,
                    "heading": active_heading,
                    "lines": [stripped],
                })
                current_block_type = "PARAGRAPH"
                i += 1
                continue

            # Check if line belongs to a table or key-value list
            is_table_row = bool(cls.TABLE_OR_KV_PATTERN.match(stripped))
            if is_table_row:
                if current_block_type != "TABLE":
                    flush_block()
                    current_block_type = "TABLE"
                current_block_lines.append(line)
                i += 1
                continue
            else:
                if current_block_type == "TABLE":
                    # Finished table block
                    flush_block()
                    current_block_type = "PARAGRAPH"
                current_block_lines.append(line)
                i += 1

        flush_block()
        return blocks

    @classmethod
    def chunk_page(
        cls,
        page_number: int,
        text: str,
        start_chunk_index: int = 0,
        page_range: Optional[str] = None,
        max_words: int = DEFAULT_MAX_WORDS,
        overlap_words: int = DEFAULT_OVERLAP_WORDS,
        metadata_context: Optional[Dict[str, Any]] = None,
    ) -> List[SemanticChunk]:
        """
        Chunk a single page's text into semantic chunks with headings, tables,
        metadata, and dual text outputs.
        """
        if not text or not text.strip():
            return []

        resolved_page_range = page_range or str(page_number)
        blocks = cls._group_lines_into_blocks(text)
        if not blocks:
            return []

        chunks: List[SemanticChunk] = []
        chunk_idx = start_chunk_index
        current_words: List[str] = []
        current_raw_pieces: List[str] = []
        current_heading: Optional[str] = None
        current_offset = 0

        def emit_chunk():
            nonlocal chunk_idx, current_words, current_raw_pieces, current_offset
            if not current_words:
                return

            verbatim_text = "\n\n".join(current_raw_pieces).strip()
            if not verbatim_text:
                verbatim_text = " ".join(current_words)

            if not cls.is_meaningful(verbatim_text):
                current_words = []
                current_raw_pieces = []
                return

            word_count = len(verbatim_text.split())
            token_count = max(1, int(word_count * 1.3))
            normalized = cls.normalize_text_for_search(verbatim_text)

            meta = dict(metadata_context or {})
            meta["page_number"] = page_number
            meta["page_range"] = resolved_page_range
            if current_heading:
                meta["section_heading"] = current_heading

            end_offset = current_offset + len(verbatim_text)

            chunk = SemanticChunk(
                chunk_index=chunk_idx,
                page_number=page_number,
                page_range=resolved_page_range,
                section_heading=current_heading,
                chunk_text=verbatim_text,
                normalized_text=normalized,
                token_count=token_count,
                word_count=word_count,
                start_char_offset=current_offset,
                end_char_offset=end_offset,
                metadata=meta,
            )
            chunks.append(chunk)
            chunk_idx += 1
            current_offset = end_offset + 1

            # Sliding window overlap
            if overlap_words > 0 and len(current_words) > overlap_words:
                overlap_text = " ".join(current_words[-overlap_words:])
                current_words = overlap_text.split()
                current_raw_pieces = [overlap_text]
            else:
                current_words = []
                current_raw_pieces = []

        for block in blocks:
            b_text = block["text"]
            b_heading = block.get("heading")
            if b_heading:
                current_heading = b_heading

            b_words = b_text.split()

            # If block is a Heading alone, store heading context and include it in next piece
            if block["type"] == "HEADING":
                current_raw_pieces.append(b_text)
                current_words.extend(b_words)
                continue

            # If adding this block exceeds max_words, emit existing chunk first
            if current_words and (len(current_words) + len(b_words) > max_words):
                emit_chunk()

            # For large blocks (e.g. huge paragraphs) exceeding max_words on their own,
            # split by sentences or word windows
            if len(b_words) > max_words:
                raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", b_text) if s.strip()]
                expanded_pieces: List[str] = []
                for s in raw_sentences:
                    s_words = s.split()
                    if len(s_words) > max_words:
                        # Chunk the long sentence/block into max_words pieces
                        for w_start in range(0, len(s_words), max_words):
                            sub_piece = " ".join(s_words[w_start : w_start + max_words])
                            if sub_piece:
                                expanded_pieces.append(sub_piece)
                    else:
                        expanded_pieces.append(s)

                for piece in expanded_pieces:
                    p_words = piece.split()
                    if current_words and (len(current_words) + len(p_words) > max_words):
                        emit_chunk()
                    current_words.extend(p_words)
                    current_raw_pieces.append(piece)
                    # If this single piece fills or exceeds max_words, emit immediately
                    if len(current_words) >= max_words:
                        emit_chunk()
            else:
                current_words.extend(b_words)
                current_raw_pieces.append(b_text)

        # Emit remaining content
        if current_words:
            emit_chunk()

        return chunks

    @classmethod
    def chunk_document_pages(
        cls,
        pages: List[Dict[str, Any]],
        document_metadata: Optional[Dict[str, Any]] = None,
        max_words: int = DEFAULT_MAX_WORDS,
        overlap_words: int = DEFAULT_OVERLAP_WORDS,
    ) -> List[SemanticChunk]:
        """
        Chunk multiple document pages sequentially, maintaining overall chunk index,
        propagating cross-page headings where applicable, and building metadata.
        
        pages input:
        [
            {
                "page_number": 1,
                "text": "...",
                "page_range": "1", # optional
            }, ...
        ]
        """
        all_chunks: List[SemanticChunk] = []
        current_chunk_index = 0
        active_heading: Optional[str] = None

        doc_meta = document_metadata or {}

        for page_data in pages:
            page_num = page_data["page_number"]
            page_text = page_data.get("text") or page_data.get("raw_text") or ""
            page_range = page_data.get("page_range") or str(page_num)

            meta_ctx = {
                "scheme_name": doc_meta.get("scheme_name"),
                "department": doc_meta.get("department"),
                "state_or_district": doc_meta.get("state_or_district"),
                "language": doc_meta.get("language", "English"),
                "effective_date": str(doc_meta.get("effective_date")) if doc_meta.get("effective_date") else None,
                "active_version": doc_meta.get("active_version", 1),
                "is_active_version": doc_meta.get("is_active_version", True),
            }

            page_chunks = cls.chunk_page(
                page_number=page_num,
                text=page_text,
                start_chunk_index=current_chunk_index,
                page_range=page_range,
                max_words=max_words,
                overlap_words=overlap_words,
                metadata_context=meta_ctx,
            )

            # If page chunks have section headings, update active_heading
            for ch in page_chunks:
                if ch.section_heading:
                    active_heading = ch.section_heading
                elif active_heading and not ch.section_heading:
                    ch.section_heading = active_heading
                    ch.metadata["section_heading"] = active_heading

            current_chunk_index += len(page_chunks)
            all_chunks.extend(page_chunks)

        return all_chunks


chunker_service = SemanticChunker()
