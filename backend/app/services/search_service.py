"""
FastAPI Hybrid Search Service.
Combines relational database keyword search and Pinecone semantic vector search.
Enforces:
1. Exact terms, names, identifiers, and quoted phrase retrieval.
2. Query vector embedding generation using configured model.
3. Pinecone vector querying with metadata filters and namespace isolation.
4. Reciprocal Rank Fusion / normalized hybrid scoring and ranking.
5. Strict metadata filtering (collection, scheme, department, state/district, language).
6. Prioritization of active and current document versions.
7. Preservation of full page and document metadata.
8. Relevance scores and retrieval reasons for every citation.
9. Score threshold gating rejecting sub-threshold results to prevent hallucination.
"""

import time
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models.db_models import (
    Citation,
    Document,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    QuestionAnswer,
    SearchSession,
)
from backend.app.models.schemas import CitationOut, QueryRequest, QueryResponse, UserOut
from backend.app.services.embedding_service import embedding_service
from backend.app.services.keyword_search import keyword_search_service
from backend.app.services.pinecone_service import pinecone_service
from backend.app.services.query_understanding import query_understanding_service

logger = logging = __import__("logging").getLogger(__name__)


class SearchService:
    """
    Hybrid Search Engine combining Relational Keyword Search and Pinecone Vector Search.
    """

    @classmethod
    def hybrid_search(
        cls,
        db: Session,
        request: QueryRequest,
        current_user: Optional[UserOut] = None,
    ) -> List[CitationOut]:
        """
        Execute combined keyword + semantic search, merge rankings,
        enforce metadata filters and threshold gating, and return citations.
        """
        query_text = request.query.strip()
        if not query_text:
            return []

        is_historical = bool(request.include_historical or request.include_archived)
        active_only = bool(request.active_only and not is_historical)
        limit = request.limit or 5
        scheme_filter = request.scheme or request.scheme_name

        # -------------------------------------------------------------
        # 1. Relational Keyword Retrieval
        # -------------------------------------------------------------
        keyword_results = keyword_search_service.search(
            db=db,
            query=query_text,
            collection_id=request.collection_id,
            scheme=scheme_filter,
            department=request.department,
            state_or_district=request.state_or_district,
            language=request.language,
            include_historical=is_historical,
            limit=limit * 3,
        )

        # -------------------------------------------------------------
        # 2. Pinecone Semantic Vector Retrieval
        # -------------------------------------------------------------
        query_vector = embedding_service.create_embedding(query_text)

        # Build Pinecone metadata filter
        pinecone_filter: Dict[str, Any] = {}
        if request.collection_id:
            pinecone_filter["collection_id"] = request.collection_id
        if scheme_filter:
            pinecone_filter["scheme"] = scheme_filter
        if request.department:
            pinecone_filter["department"] = request.department
        if request.language:
            pinecone_filter["language"] = request.language
        if active_only:
            pinecone_filter["active"] = True

        namespace = pinecone_service.get_namespace(request.collection_id)
        vector_matches = pinecone_service.query_vectors(
            vector=query_vector,
            top_k=limit * 3,
            filter_dict=pinecone_filter if pinecone_filter else None,
            namespace=namespace,
        )

        # -------------------------------------------------------------
        # 3. Candidate Aggregation & Deduplication Map
        # -------------------------------------------------------------
        # Key: (document_id, page_number, chunk_text_hash or vector_id)
        candidates: Dict[str, Dict[str, Any]] = {}

        # Process Keyword Results
        max_kw_score = max((r.match_score for r in keyword_results), default=1.0)
        for kr in keyword_results:
            key = f"{kr.version_id}:{kr.page_number}:{kr.chunk_id}"
            norm_kw_score = min(1.0, kr.match_score / max(1.0, max_kw_score))
            candidates[key] = {
                "chunk_id": kr.chunk_id,
                "document_id": kr.document_id,
                "version_id": kr.version_id,
                "collection_id": kr.collection_id,
                "scheme_name": kr.scheme_name,
                "department": kr.department,
                "state_or_district": kr.state_or_district,
                "language": kr.language,
                "page_number": kr.page_number,
                "page_range": kr.page_range,
                "section_heading": kr.section_heading,
                "chunk_text": kr.chunk_text,
                "is_historical": kr.is_historical,
                "effective_date": kr.effective_date,
                "kw_score": norm_kw_score,
                "vec_score": 0.0,
                "in_keyword": True,
                "in_vector": False,
            }

        # Process Vector Results
        for vm in vector_matches:
            vec_id = vm.get("id", "")
            meta = vm.get("metadata", {})
            v_score = float(vm.get("score", 0.0))

            v_doc_id = meta.get("document_id")
            v_ver_id = meta.get("document_version_id") or meta.get("version_id")
            v_page_num = int(meta.get("page_number", 1))
            v_coll_id = meta.get("collection_id")
            v_text = meta.get("text", "")

            # Match with existing keyword candidate if same version & page
            matched_existing_key = None
            for cand_key, cand_val in candidates.items():
                if cand_val["version_id"] == v_ver_id and cand_val["page_number"] == v_page_num:
                    matched_existing_key = cand_key
                    break

            if matched_existing_key:
                candidates[matched_existing_key]["vec_score"] = v_score
                candidates[matched_existing_key]["in_vector"] = True
            else:
                # New candidate from vector search
                key = vec_id or f"{v_ver_id}:{v_page_num}:{len(candidates)}"
                candidates[key] = {
                    "chunk_id": vec_id,
                    "document_id": v_doc_id,
                    "version_id": v_ver_id,
                    "collection_id": v_coll_id,
                    "scheme_name": meta.get("scheme") or meta.get("scheme_name", "Official Circular"),
                    "department": meta.get("department", ""),
                    "state_or_district": meta.get("state_or_district") or meta.get("state", "National"),
                    "language": meta.get("language", "en"),
                    "page_number": v_page_num,
                    "page_range": meta.get("page_range", str(v_page_num)),
                    "section_heading": meta.get("section_heading"),
                    "chunk_text": v_text,
                    "is_historical": not bool(meta.get("active", True)),
                    "effective_date": meta.get("effective_date"),
                    "kw_score": 0.0,
                    "vec_score": v_score,
                    "in_keyword": False,
                    "in_vector": True,
                }

        # -------------------------------------------------------------
        # 4. Fusion Scoring, Active Boost & Retrieval Reasons
        # -------------------------------------------------------------
        scored_citations: List[CitationOut] = []

        for cand in candidates.values():
            # Apply Post-Filters: collection_id, scheme, department, state_or_district, language
            if request.collection_id and cand["collection_id"] and cand["collection_id"] != request.collection_id:
                continue
            if scheme_filter and scheme_filter.lower() not in cand["scheme_name"].lower():
                continue
            if request.department and request.department.lower() not in cand["department"].lower():
                continue
            if request.state_or_district and cand["state_or_district"] and request.state_or_district.lower() not in cand["state_or_district"].lower():
                continue
            if request.language and cand["language"] and request.language.lower() != cand["language"].lower():
                continue
            if active_only and cand["is_historical"]:
                continue

            kw = cand["kw_score"]
            vec = cand["vec_score"]
            is_active = not cand["is_historical"]

            if cand["in_keyword"] and cand["in_vector"]:
                # Dual match: blend scores with hybrid boost
                combined_score = (0.5 * kw) + (0.5 * vec) + 0.10
                reason = f"Hybrid Match: Exact keyword match + Semantic similarity ({vec:.2f})"
            elif cand["in_keyword"]:
                combined_score = min(0.92, 0.45 + (0.45 * kw))
                reason = f"Keyword Match: Exact term/phrase match in document text"
            else:
                combined_score = vec
                reason = f"Semantic Match: High vector similarity ({vec:.2f})"

            # Active document version preference boost (only for viable candidates)
            if is_active and combined_score >= 0.35:
                combined_score = min(1.0, combined_score + 0.05)

            combined_score = round(max(0.0, min(1.0, combined_score)), 4)

            # -------------------------------------------------------------
            # 5. Threshold Gating (Discard below threshold)
            # -------------------------------------------------------------
            if combined_score < settings.SEARCH_SIMILARITY_THRESHOLD:
                continue

            # Fetch version number if available
            ver_num = 1
            if cand["version_id"]:
                db_ver = db.query(DocumentVersion).filter(DocumentVersion.id == cand["version_id"]).first()
                if db_ver:
                    ver_num = db_ver.version_number

            doc_title = cand["scheme_name"]
            if ver_num > 1:
                doc_title = f"{cand['scheme_name']} (v{ver_num})"

            citation = CitationOut(
                document_id=cand["document_id"] or "doc-unknown",
                document_title=doc_title,
                version_id=cand["version_id"],
                version_number=ver_num,
                page_number=cand["page_number"],
                page_range=cand["page_range"],
                section_heading=cand["section_heading"],
                excerpt=cand["chunk_text"][:400] + ("..." if len(cand["chunk_text"]) > 400 else ""),
                score=combined_score,
                retrieval_reason=reason,
                status="ARCHIVED" if cand["is_historical"] else "ACTIVE",
                is_historical=cand["is_historical"],
                department=cand["department"],
                state_or_district=cand["state_or_district"],
                language=cand["language"],
                effective_date=cand["effective_date"],
            )
            scored_citations.append(citation)

        # Sort descending by score, prioritizing active status and higher version number
        scored_citations.sort(
            key=lambda c: (
                c.score,
                0 if c.is_historical else 1,
                c.version_number or 1,
            ),
            reverse=True,
        )

        return scored_citations[:limit]

    @classmethod
    def execute_query(
        cls,
        db: Session,
        request: QueryRequest,
        session_id: Optional[str] = "session-anonymous",
        current_user: Optional[UserOut] = None,
    ) -> QueryResponse:
        """
        Execute document search and return grounded answer structure with exact citations.
        Adheres to zero-hallucination refusal, active-version default, and role-based permissions.
        """
        start_time = time.time()
        is_historical = bool(request.include_historical or request.include_archived)

        # 0. Query Understanding before retrieval
        understanding = query_understanding_service.understand_query(request.query)

        # Augment location filter if not explicitly specified by caller
        if not request.state_or_district and understanding.state_or_district:
            request.state_or_district = understanding.state_or_district

        # 1. Historical Search Authorization Check
        if is_historical:
            user_perms = set(current_user.permissions) if current_user else set()
            is_admin = (
                "admin:all" in user_perms
                or "docs:all" in user_perms
                or "docs:archive" in user_perms
            )
            if not is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Historical search across archived documents is restricted to administrators.",
                )

        # 2. Run Hybrid Search (Keyword + Pinecone)
        citations = cls.hybrid_search(db=db, request=request, current_user=current_user)

        # 3. Determine Grounded Answer or Zero-Hallucination Refusal
        if not citations:
            is_refusal = True
            if understanding.follow_up_question and not understanding.is_safe_to_answer:
                answer = (
                    f"To evaluate your eligibility safely without guessing: {understanding.follow_up_question}"
                )
            else:
                answer = (
                    "The requested information is not found in the uploaded official scheme documents. "
                    "Please consult the nearest official department counter or authorized helpdesk."
                )
        else:
            is_refusal = False
            top_cit = citations[0]
            if understanding.follow_up_question and not understanding.is_safe_to_answer:
                answer = (
                    f"Based on official scheme circulars for '{request.query}': "
                    f"Under {top_cit.document_title}, Page {top_cit.page_number} "
                    f"[{top_cit.section_heading or 'General Guidelines'}]: {top_cit.excerpt.strip()} "
                    f"[Source: {top_cit.document_title}, Page {top_cit.page_number}]. "
                    f"Note: To determine your personal eligibility safely: {understanding.follow_up_question}"
                )
            else:
                answer = (
                    f"Based on official scheme circulars for '{request.query}': "
                    f"Under {top_cit.document_title}, Page {top_cit.page_number} "
                    f"[{top_cit.section_heading or 'General Guidelines'}]: {top_cit.excerpt.strip()} "
                    f"[Source: {top_cit.document_title}, Page {top_cit.page_number}]."
                )

        latency_ms = int((time.time() - start_time) * 1000)

        # 4. Log Session & QA Analytics
        try:
            sess = None
            if session_id:
                sess = db.query(SearchSession).filter(SearchSession.session_token == session_id).first()
                if not sess:
                    sess = SearchSession(
                        session_token=session_id,
                        collection_id=request.collection_id,
                    )
                    db.add(sess)
                    db.commit()
                    db.refresh(sess)

            qa_log = QuestionAnswer(
                session_id=sess.id if sess else None,
                collection_id=request.collection_id,
                question=request.query,
                answer=answer,
                latency_ms=latency_ms,
                is_refusal=is_refusal,
            )
            db.add(qa_log)
            db.commit()
            db.refresh(qa_log)

            # Persist relational citations
            for c in citations:
                doc_rec = db.query(Document).filter(Document.id == c.document_id).first()
                if doc_rec:
                    db_cit = Citation(
                        qa_id=qa_log.id,
                        document_id=doc_rec.id,
                        page_number=c.page_number,
                        document_title=c.document_title,
                        excerpt=c.excerpt,
                        confidence_score=c.score,
                    )
                    db.add(db_cit)
            db.commit()
        except Exception as log_err:
            logger.warning(f"QA audit logging encountered non-fatal error: {log_err}")
            db.rollback()

        return QueryResponse(
            qa_id=qa_log.id if 'qa_log' in locals() and qa_log else None,
            answer=answer,
            citations=citations,
            is_refusal=is_refusal,
            follow_up_question=understanding.follow_up_question,
            query_understanding=understanding,
            latency_ms=latency_ms,
        )


search_service = SearchService()
