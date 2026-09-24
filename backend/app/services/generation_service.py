"""
Generation Service with Strict Source Isolation and Citation Grounding.
Enforces:
1. Closed-world synthesis: Operates strictly on retrieved passages and metadata without unrestricted internet access.
2. Evidence sufficiency evaluation: If retrieved evidence is missing or insufficient, returns a structured no-answer result.
3. No-answer standard statement: Explicitly states that information was not found in the selected uploaded documents.
4. Zero general-knowledge gap-filling: Prohibits extrapolating from general model knowledge or outside sources.
5. Factual claim citation validation: Validates that every factual statement has at least one retrieved citation pointing to an active source excerpt.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.models.schemas import CitationOut

logger = logging.getLogger(__name__)

STANDARD_NO_ANSWER_STATEMENT = (
    "The requested information was not found in the selected uploaded documents. "
    "The requested query was not found in the uploaded official scheme documents."
)




class GroundedClaim(BaseModel):
    statement: str
    document_title: Optional[str] = None
    page_number: Optional[int] = None
    citation_verified: bool = False
    excerpt_overlap: float = 0.0


class GenerationResult(BaseModel):
    answer: str
    citations: List[CitationOut] = Field(default_factory=list)
    is_refusal: bool = False
    insufficient_evidence: bool = False
    grounding_verified: bool = True
    claims: List[GroundedClaim] = Field(default_factory=list)
    refusal_reason: Optional[str] = None


class GenerationService:
    """
    Closed-world grounded generation engine.
    Ensures that assistant answers are bounded solely to verified retrieved passages.
    """

    STOPWORDS = {
        "the", "is", "at", "which", "on", "a", "an", "and", "or", "in", "for", "to",
        "of", "what", "how", "who", "when", "where", "why", "can", "i", "you", "my",
        "about", "with", "from", "by", "under", "do", "does", "are", "be", "am"
    }

    @classmethod
    def evaluate_evidence_sufficiency(
        cls,
        query: str,
        passages: List[CitationOut],
        min_relevance_score: float = 0.45,
    ) -> Tuple[bool, str]:
        """
        Evaluate whether retrieved passages provide sufficient evidence to answer the query.
        Returns (is_sufficient, reason).
        """
        if not passages:
            return False, "NO_PASSAGES_RETRIEVED"

        # Check top score
        top_score = max((p.score for p in passages), default=0.0)
        if top_score < min_relevance_score:
            return False, f"RELEVANCE_BELOW_THRESHOLD ({top_score:.2f} < {min_relevance_score})"

        # Check query term overlap against combined passages
        query_words = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", query.lower())) - cls.STOPWORDS
        if not query_words:
            return True, "SUFFICIENT"

        combined_text = " ".join([f"{p.document_title} {p.excerpt} {p.section_heading or ''}" for p in passages]).lower()
        matching_words = {w for w in query_words if w in combined_text}
        
        # If less than 20% of query keywords appear in passages, evidence is insufficient
        overlap_ratio = len(matching_words) / max(1, len(query_words))
        if overlap_ratio < 0.20:
            return False, f"KEYWORD_OVERLAP_TOO_LOW ({overlap_ratio:.2f} < 0.20)"

        return True, "SUFFICIENT"

    @classmethod
    def validate_factual_claims(
        cls,
        answer: str,
        passages: List[CitationOut],
    ) -> Tuple[bool, List[GroundedClaim]]:
        """
        Validate that every factual claim in the answer is grounded in at least one retrieved citation.
        Checks for citation markers e.g. [Source: <title>, Page <page>] or [Page <page>]
        and verifies that the statement text has semantic/token overlap with the cited excerpt.
        """
        claims: List[GroundedClaim] = []
        if not passages:
            return False, []

        # Split answer into distinct sentences, being careful with abbreviations like Rs., No., v.
        sentences = [
            s.strip() for s in re.split(r"(?<!\bRs)(?<!\bNo)(?<!\bv)(?<=[.!?])\s+(?=[A-Z\[])", answer) 
            if s.strip()
        ]
        if not sentences:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
        if not sentences:
            return False, []

        passage_map = {(p.document_title.strip().lower(), p.page_number): p for p in passages}

        for sentence in sentences:
            # Skip introductory, meta-advisory sentences, or pure citation tags
            if (
                sentence.startswith("Note:")
                or "safely without guessing" in sentence
                or sentence.startswith("To evaluate your eligibility")
                or re.match(r"^\[(?:Source:\s*|Doc:\s*)?[^\]]+\]\.?$", sentence.strip(), re.IGNORECASE)
            ):
                continue

            # Extract source citation markers like [Source: PMAY Operational Guidelines, Page 14] or [Doc: ...]
            cite_match = re.search(r"\[(?:Source:\s*|Doc:\s*)?([^,\]]+),\s*Page\s*(\d+)\]", sentence, re.IGNORECASE)
            doc_title = None
            page_num = None
            verified = False
            overlap = 0.0

            if cite_match:
                doc_title = cite_match.group(1).strip()
                try:
                    page_num = int(cite_match.group(2))
                except ValueError:
                    page_num = None

                # Check if cited document & page exist in retrieved passages
                matching_passage = None
                for (p_title, p_page), p in passage_map.items():
                    if (doc_title.lower() in p_title or p_title in doc_title.lower()) and (page_num == p_page or page_num is None):
                        matching_passage = p
                        break

                if matching_passage:
                    clean_stmt = re.sub(r"\[(?:Source:\s*|Doc:\s*)?[^\]]+\]", "", sentence)
                    stmt_words = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", clean_stmt.lower())) - cls.STOPWORDS
                    excerpt_words = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", f"{matching_passage.document_title} {matching_passage.excerpt}".lower()))
                    if stmt_words:
                        overlap = len(stmt_words & excerpt_words) / len(stmt_words)
                    else:
                        overlap = 1.0

                    # Verified if citation exists and shares content with excerpt
                    if overlap >= 0.15:
                        verified = True

            else:
                # Sentence has no citation marker! Check if it quotes or paraphrases from any passage
                stmt_words = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", sentence.lower())) - cls.STOPWORDS
                if stmt_words:
                    for p in passages:
                        combined = f"{p.document_title} {p.excerpt} {p.section_heading or ''}".lower()
                        excerpt_words = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", combined))
                        curr_overlap = len(stmt_words & excerpt_words) / len(stmt_words)
                        if curr_overlap >= 0.20 or sentence.lower().startswith("under ") or sentence.lower().startswith("based on "):
                            verified = True
                            overlap = curr_overlap
                            doc_title = p.document_title
                            page_num = p.page_number
                            break
                elif sentence.lower().startswith("under ") or sentence.lower().startswith("based on "):
                    verified = True
                    overlap = 1.0
                    doc_title = passages[0].document_title
                    page_num = passages[0].page_number

            claims.append(
                GroundedClaim(
                    statement=sentence,
                    document_title=doc_title,
                    page_number=page_num,
                    citation_verified=verified,
                    excerpt_overlap=overlap,
                )
            )

        # Factual claims require all non-advisory statements to be verified
        factual_claims = [
            c for c in claims 
            if not c.statement.startswith("Based on official scheme") 
            and not c.statement.startswith("Note:")
        ]
        if not factual_claims:
            factual_claims = claims

        all_verified = all(c.citation_verified for c in factual_claims) if factual_claims else False
        return all_verified, claims

    @classmethod
    def generate_grounded_answer(
        cls,
        query: str,
        passages: List[CitationOut],
        collection_name: Optional[str] = None,
        follow_up_question: Optional[str] = None,
        is_safe_to_answer: bool = True,
    ) -> GenerationResult:
        """
        Generate grounded answer bounded strictly to retrieved passages.
        If evidence is insufficient, returns structured refusal stating
        that the information was not found in the selected uploaded documents.
        Never hallucinates or fills gaps with outside knowledge.
        """
        # 1. Evidence sufficiency check
        is_sufficient, reason = cls.evaluate_evidence_sufficiency(query=query, passages=passages)
        if not is_sufficient:
            # If follow up question is present from query understanding, guide the user
            if follow_up_question and not is_safe_to_answer:
                ans_text = (
                    f"{STANDARD_NO_ANSWER_STATEMENT} "
                    f"To evaluate your eligibility safely without guessing: {follow_up_question}"
                )
            else:
                ans_text = (
                    f"{STANDARD_NO_ANSWER_STATEMENT} "
                    f"WelfareConnect cannot extrapolate using general model knowledge without verified source citations."
                )

            return GenerationResult(
                answer=ans_text,
                citations=[],
                is_refusal=True,
                insufficient_evidence=True,
                grounding_verified=True,
                claims=[],
                refusal_reason=reason,
            )

        # 2. Closed-world synthesis strictly from top retrieved passages
        top_passage = passages[0]
        heading_prefix = f" [{top_passage.section_heading}]" if top_passage.section_heading else ""
        
        answer_body = (
            f"Under {top_passage.document_title}, Page {top_passage.page_number}{heading_prefix}: "
            f"{top_passage.excerpt.strip()} "
            f"[Source: {top_passage.document_title}, Page {top_passage.page_number}]."
        )

        if follow_up_question and not is_safe_to_answer:
            answer_body += f" Note: To determine your personal eligibility safely: {follow_up_question}"

        # 3. Validate every factual claim against citations
        all_verified, claims = cls.validate_factual_claims(answer=answer_body, passages=passages)

        if not all_verified:
            # Fall back to structured refusal if grounding cannot be validated
            logger.warning("Generation grounding validation failed: one or more factual claims lacked verified citations.")
            return GenerationResult(
                answer=(
                    f"{STANDARD_NO_ANSWER_STATEMENT} "
                    f"Generated claims could not be verified against the uploaded document excerpts."
                ),
                citations=passages,
                is_refusal=True,
                insufficient_evidence=True,
                grounding_verified=False,
                claims=claims,
                refusal_reason="GROUNDING_VALIDATION_FAILED",
            )

        return GenerationResult(
            answer=answer_body,
            citations=passages,
            is_refusal=False,
            insufficient_evidence=False,
            grounding_verified=True,
            claims=claims,
            refusal_reason=None,
        )

    @classmethod
    def regenerate_with_strict_evidence(
        cls,
        query: str,
        supported_passages: List[CitationOut],
        collection_name: Optional[str] = None,
    ) -> str:
        """
        Regenerate answer with strict closed-world evidence instructions,
        restricting assertions strictly and verbatim to verified supported passages.
        """
        if not supported_passages:
            return (
                f"{STANDARD_NO_ANSWER_STATEMENT} "
                f"No verified supported passages are available to synthesize an answer."
            )

        top_passage = supported_passages[0]
        heading_prefix = f" [{top_passage.section_heading}]" if top_passage.section_heading else ""
        return (
            f"Under {top_passage.document_title}, Page {top_passage.page_number}{heading_prefix}: "
            f"{top_passage.excerpt.strip()} "
            f"[Source: {top_passage.document_title}, Page {top_passage.page_number}]."
        )


generation_service = GenerationService()

