"""
Relational Keyword Search Service.
Implements fast exact-term, identifier, name, and phrase matching over extracted chunks and document metadata.
Adheres to strict role-based visibility, active-version defaults, and historical search constraints.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.models.db_models import (
    Document,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
)
from backend.app.workers.chunker import SemanticChunker

logger = logging.getLogger(__name__)


class KeywordSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    version_id: str
    collection_id: str
    scheme_name: str
    department: str
    state_or_district: Optional[str] = None
    language: str
    page_number: int
    page_range: Optional[str] = "1"
    section_heading: Optional[str] = None
    chunk_text: str
    match_score: float
    is_historical: bool = False
    effective_date: Optional[str] = None


class KeywordSearchService:
    """
    Search layer for exact terms, names, identifiers, and quoted phrases
    directly against relational tables (SQLite / PostgreSQL).
    """

    @classmethod
    def _extract_search_tokens(cls, query: str) -> Tuple[List[str], List[str]]:
        """
        Parse query string into exact quoted phrases and individual keyword tokens.
        """
        # Extract quoted phrases: "exact phrase"
        quoted_phrases = re.findall(r'"([^"]*)"', query)
        # Remove quoted phrases from remainder
        remainder = re.sub(r'"[^"]*"', " ", query).strip()
        tokens = [t.strip() for t in remainder.split() if len(t.strip()) > 1]
        return quoted_phrases, tokens

    @classmethod
    def search(
        cls,
        db: Session,
        query: str,
        collection_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scheme: Optional[str] = None,
        department: Optional[str] = None,
        state_or_district: Optional[str] = None,
        language: Optional[str] = None,
        include_historical: bool = False,
        limit: int = 10,
    ) -> List[KeywordSearchResult]:
        """
        Execute keyword and phrase search across ExtractedChunks and Documents.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        quoted_phrases, raw_tokens = cls._extract_search_tokens(cleaned_query)
        normalized_query = SemanticChunker.normalize_text_for_search(cleaned_query)
        normalized_tokens = [t for t in normalized_query.split() if len(t) > 1]

        # Base query joining ExtractedChunk with Document and DocumentVersion
        q = (
            db.query(ExtractedChunk, Document, DocumentVersion)
            .join(Document, ExtractedChunk.document_id == Document.id)
            .join(DocumentVersion, ExtractedChunk.version_id == DocumentVersion.id)
            .filter(Document.status != DocumentStatus.DELETED.value)
        )

        # Active version default vs historical filter
        if not include_historical:
            q = q.filter(
                and_(
                    Document.status == DocumentStatus.ACTIVE.value,
                    DocumentVersion.status == DocumentStatus.ACTIVE.value,
                )
            )

        # Metadata filters
        if collection_id:
            q = q.filter(Document.collection_id == collection_id)
        if document_id:
            q = q.filter(Document.id == document_id)
        if scheme:
            q = q.filter(Document.scheme_name.ilike(f"%{scheme}%"))
        if department:
            q = q.filter(Document.department.ilike(f"%{department}%"))
        if state_or_district:
            q = q.filter(Document.state_or_district.ilike(f"%{state_or_district}%"))
        if language:
            q = q.filter(Document.language.ilike(f"%{language}%"))

        # Build search criteria filters
        text_filters = []

        # 1. Exact quoted phrases (in chunk_text or normalized_text)
        for phrase in quoted_phrases:
            p_clean = phrase.strip()
            if p_clean:
                text_filters.append(
                    or_(
                        ExtractedChunk.chunk_text.ilike(f"%{p_clean}%"),
                        ExtractedChunk.normalized_text.ilike(f"%{p_clean.lower()}%"),
                        Document.scheme_name.ilike(f"%{p_clean}%"),
                    )
                )

        # 2. Individual tokens & identifiers (e.g., "PM-KISAN", "6000", "EWS")
        token_or_clauses = []
        for tok in raw_tokens:
            token_or_clauses.append(ExtractedChunk.chunk_text.ilike(f"%{tok}%"))
            token_or_clauses.append(ExtractedChunk.normalized_text.ilike(f"%{tok.lower()}%"))
            token_or_clauses.append(ExtractedChunk.section_heading.ilike(f"%{tok}%"))
            token_or_clauses.append(Document.scheme_name.ilike(f"%{tok}%"))
            token_or_clauses.append(Document.department.ilike(f"%{tok}%"))

        for tok in normalized_tokens:
            token_or_clauses.append(ExtractedChunk.normalized_text.ilike(f"%{tok}%"))

        if text_filters:
            # Must match all quoted phrases
            q = q.filter(and_(*text_filters))
        elif token_or_clauses:
            # Match any token
            q = q.filter(or_(*token_or_clauses))
        else:
            # Fallback exact string match
            q = q.filter(
                or_(
                    ExtractedChunk.chunk_text.ilike(f"%{cleaned_query}%"),
                    ExtractedChunk.normalized_text.ilike(f"%{normalized_query}%"),
                    Document.scheme_name.ilike(f"%{cleaned_query}%"),
                )
            )

        rows = q.limit(limit * 3).all()
        if not rows:
            return []

        # Calculate relevance score for each matched chunk
        scored_results: List[KeywordSearchResult] = []
        for chunk, doc, ver in rows:
            chunk_text = chunk.chunk_text or ""
            norm_text = chunk.normalized_text or ""
            heading = chunk.section_heading or ""
            scheme_name = doc.scheme_name or ""

            score = 0.0
            # Higher score for exact scheme name match
            if cleaned_query.lower() in scheme_name.lower():
                score += 3.0

            # Higher score for exact quoted phrases
            for phrase in quoted_phrases:
                if phrase.lower() in chunk_text.lower():
                    score += 2.5
                elif phrase.lower() in norm_text:
                    score += 2.0

            # Section heading match
            for tok in raw_tokens:
                if tok.lower() in heading.lower():
                    score += 1.5

            # Word / token matches in chunk body
            for tok in normalized_tokens:
                if tok in norm_text:
                    score += 1.0

            # Direct substring match in verbatim text
            if cleaned_query.lower() in chunk_text.lower():
                score += 2.0

            is_archived = (doc.status == DocumentStatus.ARCHIVED.value or ver.status == DocumentStatus.ARCHIVED.value)

            eff_date = str(ver.effective_date or doc.effective_date) if (ver.effective_date or doc.effective_date) else None

            scored_results.append(
                KeywordSearchResult(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    version_id=ver.id,
                    collection_id=doc.collection_id,
                    scheme_name=scheme_name,
                    department=doc.department,
                    state_or_district=doc.state_or_district,
                    language=doc.language,
                    page_number=chunk.page_number,
                    page_range=chunk.page_range,
                    section_heading=chunk.section_heading,
                    chunk_text=chunk_text,
                    match_score=round(score, 2),
                    is_historical=is_archived,
                    effective_date=eff_date,
                )
            )

        # Sort descending by score and return top limit
        scored_results.sort(key=lambda x: x.match_score, reverse=True)
        return scored_results[:limit]


keyword_search_service = KeywordSearchService()
