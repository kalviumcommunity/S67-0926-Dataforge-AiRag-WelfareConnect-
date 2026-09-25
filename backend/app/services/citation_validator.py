"""
Post-Generation Citation Validation and Grounding Verification Service.

Enforces:
1. Document existence confirmation against relational database.
2. Collection boundary confirmation (must belong to selected collection).
3. Authorization confirmation (private collection ownership and archived document access).
4. Page number existence confirmation against document page structures.
5. Evidence provenance confirmation (cited text must originate from retrieved passages).
6. Filtering or flagging of unsupported citations.
7. Factual claims validation with strict evidence regeneration or verification warning.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from backend.app.models.db_models import (
    Document,
    DocumentCollection,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
)
from backend.app.models.schemas import (
    CitationOut,
    CitationValidationItem,
    CitationValidationReport,
    UserOut,
)
from backend.app.services.generation_service import (
    STANDARD_NO_ANSWER_STATEMENT,
    GenerationService,
)

logger = logging.getLogger(__name__)


class CitationValidatorService:
    """
    Service for validating citations post-generation and verifying factual claim grounding.
    """

    STOPWORDS: Set[str] = {
        "the", "is", "at", "which", "on", "a", "an", "and", "or", "in", "for", "to",
        "of", "what", "how", "who", "when", "where", "why", "can", "i", "you", "my",
        "about", "with", "from", "by", "under", "do", "does", "are", "be", "am"
    }

    @classmethod
    def validate_single_citation(
        cls,
        db: Session,
        citation: CitationOut,
        selected_collection_id: str,
        current_user: Optional[UserOut] = None,
        include_historical: bool = False,
        retrieved_passages: Optional[List[CitationOut]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a single citation against 5 integrity requirements:
        1. Document exists.
        2. Belongs to selected collection.
        3. Authorized for user.
        4. Page number exists.
        5. Cited text came from retrieved evidence.

        Returns (is_valid, error_reason).
        """
        # 1. Confirm the cited document exists
        doc = db.query(Document).filter(Document.id == citation.document_id).first()
        if not doc:
            # Also attempt title fallback in case title was cited instead of ID
            doc = db.query(Document).filter(Document.scheme_name.ilike(f"%{citation.document_title}%")).first()
            if not doc:
                return False, "DOCUMENT_NOT_FOUND"

        # 2. Confirm it belongs to the selected collection
        if doc.collection_id != selected_collection_id:
            return False, "WRONG_COLLECTION"

        # 3. Confirm it is authorized for the current user
        collection = db.query(DocumentCollection).filter(DocumentCollection.id == selected_collection_id).first()
        if collection and getattr(collection, "is_private", False):
            if not current_user:
                return False, "UNAUTHORIZED_PRIVATE_COLLECTION"
            user_perms = set(current_user.permissions or [])
            is_admin = bool({"admin:all", "docs:all", "collections:manage"} & user_perms)
            is_owner = (collection.owner_user_id == current_user.id)
            if not (is_admin or is_owner):
                return False, "UNAUTHORIZED_PRIVATE_COLLECTION"

        # Check archived status authorization
        is_archived = (doc.status == DocumentStatus.ARCHIVED.value)
        if citation.version_id:
            ver = db.query(DocumentVersion).filter(DocumentVersion.id == citation.version_id).first()
            if ver and ver.status == DocumentStatus.ARCHIVED.value:
                is_archived = True

        if is_archived:
            user_perms = set(current_user.permissions or []) if current_user else set()
            is_admin = bool({"admin:all", "docs:all", "docs:archive"} & user_perms)
            if not (include_historical and is_admin):
                return False, "UNAUTHORIZED_ARCHIVED_DOCUMENT"

        # 4. Confirm the page number exists
        if citation.page_number <= 0:
            return False, "INVALID_PAGE_NUMBER"

        # Check if page exists in document_pages table
        page_rec = (
            db.query(DocumentPage)
            .filter(
                DocumentPage.document_id == doc.id,
                DocumentPage.page_number == citation.page_number,
            )
            .first()
        )
        if not page_rec:
            # If not in document_pages table, check total_pages on active version
            version_rec = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == doc.id)
                .order_by(DocumentVersion.version_number.desc())
                .first()
            )
            max_pages = version_rec.total_pages if (version_rec and version_rec.total_pages) else None
            if max_pages is not None:
                if citation.page_number > max_pages:
                    return False, "INVALID_PAGE_NUMBER"
            else:
                # If total_pages is not set and no page records exist, reject invalid page
                return False, "INVALID_PAGE_NUMBER"

        # 5. Confirm the cited text came from the retrieved evidence
        if retrieved_passages:
            cited_words = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", citation.excerpt.lower())) - cls.STOPWORDS
            evidence_matched = False
            for p in retrieved_passages:
                # Check match against this passage if same document
                if p.document_id == doc.id or p.document_id == citation.document_id:
                    p_words = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", p.excerpt.lower()))
                    if cited_words:
                        overlap = len(cited_words & p_words) / len(cited_words)
                        if overlap >= 0.25 or citation.excerpt.lower() in p.excerpt.lower() or p.excerpt.lower() in citation.excerpt.lower():
                            evidence_matched = True
                            break
                    else:
                        evidence_matched = True
                        break

            if not evidence_matched:
                return False, "NOT_IN_RETRIEVED_EVIDENCE"

        return True, None

    @classmethod
    def validate_citations(
        cls,
        db: Session,
        citations: List[CitationOut],
        selected_collection_id: str,
        current_user: Optional[UserOut] = None,
        include_historical: bool = False,
        retrieved_passages: Optional[List[CitationOut]] = None,
    ) -> Tuple[List[CitationOut], CitationValidationReport]:
        """
        Validate all generated citations.
        Returns:
            (supported_citations, validation_report)
        Unsupported citations are either flagged or removed from supported_citations.
        """
        supported_citations: List[CitationOut] = []
        details: List[CitationValidationItem] = []
        warnings: List[str] = []

        for idx, cit in enumerate(citations):
            is_valid, err = cls.validate_single_citation(
                db=db,
                citation=cit,
                selected_collection_id=selected_collection_id,
                current_user=current_user,
                include_historical=include_historical,
                retrieved_passages=retrieved_passages,
            )

            # Update citation model
            cit_copy = cit.model_copy()
            cit_copy.is_verified = is_valid
            cit_copy.validation_error = err

            details.append(
                CitationValidationItem(
                    citation_index=idx,
                    document_id=cit.document_id,
                    document_title=cit.document_title,
                    page_number=cit.page_number,
                    is_valid=is_valid,
                    error_reason=err,
                )
            )

            if is_valid:
                supported_citations.append(cit_copy)
            else:
                msg = f"Citation #{idx + 1} ({cit.document_title}, Page {cit.page_number}) rejected: {err}"
                warnings.append(msg)
                logger.warning(msg)

        report = CitationValidationReport(
            total_citations=len(citations),
            valid_citations_count=len(supported_citations),
            invalid_citations_count=len(citations) - len(supported_citations),
            has_unsupported_claims=False,
            warnings=warnings,
            details=details,
        )

        return supported_citations, report

    @classmethod
    def validate_and_reconcile_answer(
        cls,
        db: Session,
        query: str,
        answer: str,
        citations: List[CitationOut],
        selected_collection_id: str,
        current_user: Optional[UserOut] = None,
        include_historical: bool = False,
        retrieved_passages: Optional[List[CitationOut]] = None,
        collection_name: Optional[str] = None,
    ) -> Tuple[str, List[CitationOut], bool, Optional[str], CitationValidationReport]:
        """
        Validate all citations, verify factual claims, and reconcile answer.
        If unsupported factual claims exist:
        1. Attempt regeneration with strict evidence instructions using verified supported passages.
        2. If still unverified or no supported passages remain, return verification warning.

        Returns:
            (final_answer, supported_citations, grounding_verified, verification_warning, validation_report)
        """
        # Step 1: Validate all citations against database and retrieved evidence
        supported_citations, report = cls.validate_citations(
            db=db,
            citations=citations,
            selected_collection_id=selected_collection_id,
            current_user=current_user,
            include_historical=include_historical,
            retrieved_passages=retrieved_passages,
        )

        # If zero supported citations remain
        if not supported_citations:
            logger.warning("All citations failed validation or zero supported citations exist.")
            warning_msg = (
                "Warning: The answer could not be fully verified against official document records. "
                "No supported citations were confirmed for this collection."
            )
            report.has_unsupported_claims = True
            report.warnings.append(warning_msg)

            refusal_text = (
                f"{STANDARD_NO_ANSWER_STATEMENT} "
                f"Citations could not be validated against official uploaded documents for this collection."
            )
            return refusal_text, [], False, warning_msg, report

        # Step 2: Validate factual claims in the answer against supported citations
        all_grounded, claims = GenerationService.validate_factual_claims(
            answer=answer,
            passages=supported_citations,
        )

        # Check if any claim in the answer is unsupported
        unsupported_claims = [c for c in claims if not c.citation_verified]

        if not all_grounded or unsupported_claims or report.invalid_citations_count > 0:
            report.has_unsupported_claims = True

            # Attempt strict regeneration bounded strictly to supported citations
            regenerated_ans = GenerationService.regenerate_with_strict_evidence(
                query=query,
                supported_passages=supported_citations,
                collection_name=collection_name,
            )

            # Re-verify claims on regenerated answer
            regen_ok, regen_claims = GenerationService.validate_factual_claims(
                answer=regenerated_ans,
                passages=supported_citations,
            )

            if regen_ok:
                logger.info("Successfully regenerated answer with stricter evidence instructions.")
                warning_note = None
                if report.invalid_citations_count > 0:
                    warning_note = (
                        f"Notice: {report.invalid_citations_count} unverified citation(s) were removed. "
                        f"The answer has been regenerated strictly from verified official sources."
                    )
                    report.warnings.append(warning_note)
                return regenerated_ans, supported_citations, True, warning_note, report

            # If regeneration still contains unverified statements, return warning
            warning_msg = (
                "Warning: This answer could not be fully verified against official document records. "
                "One or more factual claims lacked verified citations."
            )
            report.warnings.append(warning_msg)
            return answer, supported_citations, False, warning_msg, report

        # All claims and citations verified successfully
        return answer, supported_citations, True, None, report


citation_validator = CitationValidatorService()
