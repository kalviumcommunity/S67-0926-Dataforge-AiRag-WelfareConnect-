"""
Unit and Integration Tests for Pre-Retrieval Query Understanding.
Tests:
1. Structured field extraction:
   - Scheme category
   - Beneficiary type
   - Age
   - Gender
   - Income range & max_income
   - Occupation
   - State, district, and locality
   - Disability status
   - Profile terms
   - Requested information type
2. Safety evaluation & concise follow-up question generation:
   - Generates follow-up question when required fields are missing for safe eligibility answers.
   - Does NOT generate unnecessary follow-up questions for informational queries (documents, benefits, process, deadline, contact).
   - Validates that questions provide clear guidance without guessing.
3. Schema validation & fail-safe fallback:
   - Handles empty, malformed, or unusual inputs gracefully.
   - Never raises unhandled exceptions or blocks ordinary search.
4. API endpoint integration:
   - POST /api/v1/query/understand
   - POST /api/v1/query/search contains query_understanding and follow_up_question fields.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.schemas import InformationType, QueryUnderstandingResult
from backend.app.services.query_understanding import query_understanding_service


client = TestClient(app)


# =====================================================================
# 1. Structured Field Extraction Unit Tests
# =====================================================================

def test_extract_scheme_categories():
    """Verify accurate extraction of primary scheme domain categories."""
    assert query_understanding_service.extract_scheme_category("how to apply for pmay housing scheme") == "housing"
    assert query_understanding_service.extract_scheme_category("subsidy for kisan tractor and crop seeds") == "agriculture"
    assert query_understanding_service.extract_scheme_category("ayushman arogya treatment in hospital") == "healthcare"
    assert query_understanding_service.extract_scheme_category("national scholarship fellowship for college student") == "education"
    assert query_understanding_service.extract_scheme_category("old age pension monthly disbursement") == "pension"
    assert query_understanding_service.extract_scheme_category("mgnrega job card employment in village") == "employment"
    assert query_understanding_service.extract_scheme_category("ujjwala free lpg gas cylinder connection") == "energy"


def test_extract_beneficiary_types():
    """Verify accurate extraction of intended beneficiary groups."""
    assert query_understanding_service.extract_beneficiary_type("financial assistance for small farmer") == "farmer"
    assert query_understanding_service.extract_beneficiary_type("tuition fee waiver for college student") == "student"
    assert query_understanding_service.extract_beneficiary_type("monthly pension for elderly senior citizens") == "senior_citizen"
    assert query_understanding_service.extract_beneficiary_type("welfare grant for destitute widow") == "widow"
    assert query_understanding_service.extract_beneficiary_type("artisan tool kit assistance for weaver") == "artisan"
    assert query_understanding_service.extract_beneficiary_type("interest free loan for women shg") == "shg"
    assert query_understanding_service.extract_beneficiary_type("ration card support for bpl family") == "bpl_family"


def test_extract_age():
    """Verify regex extraction of applicant age across various syntactic expressions."""
    assert query_understanding_service.extract_age("I am 65 years old looking for pension") == 65
    assert query_understanding_service.extract_age("eligibility for senior citizen aged 72") == 72
    assert query_understanding_service.extract_age("applicant age: 45 for housing loan") == 45
    assert query_understanding_service.extract_age("student scholarship for 21 yo girl") == 21
    assert query_understanding_service.extract_age("scheme for persons above 60") == 60
    assert query_understanding_service.extract_age("general information on scholarships") is None


def test_extract_gender():
    """Verify detection of gender where relevant."""
    assert query_understanding_service.extract_gender("maternity allowance for pregnant woman") == "female"
    assert query_understanding_service.extract_gender("welfare scheme for single widow") == "female"
    assert query_understanding_service.extract_gender("subsidized housing for elderly man") == "male"
    assert query_understanding_service.extract_gender("pension for transgender community members") == "transgender"
    assert query_understanding_service.extract_gender("how to apply for kisan credit card") is None


def test_extract_income_and_max_income():
    """Verify parsing of income categories and numeric boundaries."""
    desc, val = query_understanding_service.extract_income("family holding bpl ration card")
    assert desc == "BPL"
    assert val == 150000.0

    desc, val = query_understanding_service.extract_income("qualifying under ews quota")
    assert desc == "EWS"
    assert val == 300000.0

    desc, val = query_understanding_service.extract_income("household annual income below 3 lakh")
    assert val == 300000.0
    assert "<= Rs. 300,000" in desc

    desc, val = query_understanding_service.extract_income("family with income under 2.5 lakhs")
    assert val == 250000.0

    desc, val = query_understanding_service.extract_income("monthly salary 25000")
    assert val == 25000.0

    desc, val = query_understanding_service.extract_income("what is the process to apply")
    assert desc is None
    assert val is None


def test_extract_occupations():
    """Verify extraction of targeted occupations."""
    assert query_understanding_service.extract_occupation("tractor subsidy for marginal cultivator farmer") == "farmer"
    assert query_understanding_service.extract_occupation("handloom loom subsidy for weaver artisan") == "artisan"
    assert query_understanding_service.extract_occupation("accidental insurance for construction worker") == "construction_worker"
    assert query_understanding_service.extract_occupation("pm swanidhi loan for street vendor") == "street_vendor"
    assert query_understanding_service.extract_occupation("honorarium for asha worker") == "healthcare_worker"


def test_extract_location_and_locality():
    """Verify extraction of states, districts, and rural/urban locality indicators."""
    state_dist, locality = query_understanding_service.extract_location("welfare housing in Varanasi, Uttar Pradesh")
    assert "Varanasi" in state_dist
    assert "Uttar Pradesh" in state_dist

    state_dist, locality = query_understanding_service.extract_location("farming subsidy for rural village in Maharashtra")
    assert state_dist == "Maharashtra"
    assert locality == "rural"

    state_dist, locality = query_understanding_service.extract_location("urban slum development in Pune city")
    assert "Pune" in state_dist
    assert locality == "urban"


def test_extract_disability_status():
    """Verify extraction of disability indicators and certified percentages."""
    assert query_understanding_service.extract_disability("aid and appliance for divyangjan") == "PwD / Divyangjan"
    res = query_understanding_service.extract_disability("pension for person with 40% disability")
    assert "PwD" in res
    assert "40%" in res
    assert query_understanding_service.extract_disability("general public school scholarship") is None


def test_extract_profile_terms():
    """Verify extraction of aggregated profile badge terms."""
    terms = query_understanding_service.extract_profile_terms(
        "65 year old widow and marginal farmer with bpl card"
    )
    assert "widow" in terms
    assert "farmer" in terms
    assert "bpl" in terms
    assert "senior-citizen" in terms


def test_extract_information_types():
    """Verify classification of requested information intent."""
    assert (
        query_understanding_service.extract_information_type("am i eligible to receive pm-kisan benefits")
        == InformationType.ELIGIBILITY
    )
    assert (
        query_understanding_service.extract_information_type("how much financial assistance amount is provided")
        == InformationType.BENEFIT
    )
    assert (
        query_understanding_service.extract_information_type("what documents and id proof are required")
        == InformationType.DOCUMENTS
    )
    assert (
        query_understanding_service.extract_information_type("what is the step by step process to apply online")
        == InformationType.PROCESS
    )
    assert (
        query_understanding_service.extract_information_type("what is the last date and deadline for submission")
        == InformationType.DEADLINE
    )
    assert (
        query_understanding_service.extract_information_type("toll-free helpline phone number or contact officer")
        == InformationType.CONTACT
    )
    assert (
        query_understanding_service.extract_information_type("how to check application status and track reference")
        == InformationType.STATUS
    )


# =====================================================================
# 2. Safety & Concise Follow-up Question Tests
# =====================================================================

def test_follow_up_question_for_ambiguous_housing_eligibility():
    """
    If user asks about housing eligibility (e.g. PMAY) without specifying income,
    the service must NOT guess and must generate a concise follow-up question.
    """
    res = query_understanding_service.understand_query("Am I eligible to get a house under PMAY?")
    assert res.information_type == InformationType.ELIGIBILITY
    assert res.scheme_category == "housing"
    assert res.is_safe_to_answer is False
    assert res.follow_up_question is not None
    assert "annual household income" in res.follow_up_question.lower()
    assert "annual_income" in res.missing_critical_fields


def test_follow_up_question_for_ambiguous_pension_eligibility():
    """
    If user asks about old-age pension eligibility without specifying age,
    the service must generate a concise follow-up question for age.
    """
    res = query_understanding_service.understand_query("Can I apply for the old age pension scheme?")
    assert res.information_type == InformationType.ELIGIBILITY
    assert res.scheme_category == "pension"
    assert res.is_safe_to_answer is False
    assert res.follow_up_question is not None
    assert "age" in res.follow_up_question.lower()
    assert "age" in res.missing_critical_fields


def test_follow_up_question_for_ambiguous_pm_kisan_eligibility():
    """
    If user asks about PM-Kisan eligibility without specifying farmer/landholding status,
    the service generates a concise follow-up question.
    """
    res = query_understanding_service.understand_query("Am I eligible to receive PM-Kisan 6000 rupees?")
    assert res.information_type == InformationType.ELIGIBILITY
    assert res.scheme_category == "agriculture"
    assert res.is_safe_to_answer is False
    assert res.follow_up_question is not None
    assert "land" in res.follow_up_question.lower()


def test_safe_eligibility_when_prerequisites_are_provided():
    """
    When all necessary criteria are provided, no follow-up question is needed,
    and is_safe_to_answer must be True.
    """
    query = "I am a 68 year old citizen, am I eligible for old age pension?"
    res = query_understanding_service.understand_query(query)
    assert res.information_type == InformationType.ELIGIBILITY
    assert res.age == 68
    assert res.is_safe_to_answer is True
    assert res.follow_up_question is None
    assert len(res.missing_critical_fields) == 0


def test_informational_queries_do_not_generate_unnecessary_follow_ups():
    """
    Queries requesting factual document information (documents, process, deadline, contact)
    do NOT require personal demographics and must be safe to answer directly.
    """
    doc_query = "What documents are required for PMAY housing application?"
    res = query_understanding_service.understand_query(doc_query)
    assert res.information_type == InformationType.DOCUMENTS
    assert res.scheme_category == "housing"
    assert res.is_safe_to_answer is True
    assert res.follow_up_question is None

    process_query = "What is the process to apply for PM-Kisan online?"
    res_proc = query_understanding_service.understand_query(process_query)
    assert res_proc.information_type == InformationType.PROCESS
    assert res_proc.is_safe_to_answer is True
    assert res_proc.follow_up_question is None


# =====================================================================
# 3. Schema Validation & Fail-Safe Fallback Tests
# =====================================================================

def test_schema_validation_and_model_properties():
    """Verify that QueryUnderstandingResult conforms strictly to Pydantic schema."""
    query = "Subsidized home loan in Pune for EWS woman with annual income under 3 lakh"
    res = query_understanding_service.understand_query(query)

    assert isinstance(res, QueryUnderstandingResult)
    assert res.scheme_category == "housing"
    assert res.gender == "female"
    assert res.income_range == "EWS"
    assert "Pune" in res.state_or_district
    assert res.confidence == 1.0
    assert isinstance(res.profile_terms, list)
    assert isinstance(res.extracted_entities, dict)


def test_empty_and_whitespace_queries():
    """Verify handling of empty or blank queries."""
    res_empty = query_understanding_service.understand_query("")
    assert res_empty.raw_query == ""
    assert res_empty.is_safe_to_answer is True
    assert res_empty.follow_up_question is None

    res_blank = query_understanding_service.understand_query("   ")
    assert res_blank.raw_query == ""
    assert res_blank.is_safe_to_answer is True


def test_fallback_resilience_on_exception(monkeypatch):
    """
    Verify that if an internal error or exception occurs in the extraction logic,
    the service safely falls back to a valid QueryUnderstandingResult and does NOT raise an error.
    """
    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("Simulated unexpected regex parser failure")

    monkeypatch.setattr(query_understanding_service, "extract_scheme_category", raise_runtime_error)

    res = query_understanding_service.understand_query("Test query with simulated exception")
    assert isinstance(res, QueryUnderstandingResult)
    assert res.raw_query == "Test query with simulated exception"
    assert res.is_safe_to_answer is True
    assert res.confidence == 0.0


# =====================================================================
# 4. API End-to-End Integration Tests
# =====================================================================

def test_api_understand_endpoint():
    """Verify POST /api/v1/query/understand returns validated structured result."""
    payload = {
        "query": "What are the required documents for senior citizen pension in Maharashtra for age 65?",
    }
    response = client.post("/api/v1/query/understand", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["scheme_category"] == "pension"
    assert data["age"] == 65
    assert data["state_or_district"] == "Maharashtra"
    assert data["information_type"] == "documents"
    assert data["is_safe_to_answer"] is True
    assert "senior-citizen" in data["profile_terms"]


def test_api_search_includes_query_understanding():
    """Verify POST /api/v1/query/search includes query_understanding in the response."""
    payload = {
        "query": "Am I eligible for PMAY housing loan subsidy?",
    }
    response = client.post("/api/v1/query/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "query_understanding" in data
    assert data["query_understanding"] is not None
    assert data["query_understanding"]["scheme_category"] == "housing"
    assert "follow_up_question" in data
    assert data["follow_up_question"] is not None
    assert "annual household income" in data["follow_up_question"].lower()
