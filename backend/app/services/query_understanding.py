"""
Query Understanding Service for WelfareConnect.
Extracts structured fields before document retrieval:
- Scheme category (housing, agriculture, healthcare, education, pension, etc.)
- Beneficiary type (farmer, student, senior citizen, widow, artisan, etc.)
- Age (extracted integer and age boundaries)
- Gender where relevant (female, male, transgender)
- Income range and maximum income threshold
- Occupation (farmer, weaver, artisan, construction worker, etc.)
- State, district, or locality (rural vs urban)
- Disability status (PwD, benchmark percentage, divyang)
- Profile terms (student, farmer, widow, senior-citizen, etc.)
- Requested information type (eligibility, benefit, documents, process, deadline, contact, status)

Generates concise follow-up questions instead of guessing when required fields are missing
to answer eligibility safely.
Validates against Pydantic schema and provides safe fallback if extraction fails.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.models.schemas import InformationType, QueryUnderstandingResult

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Knowledge Lexicons & Entity Patterns
# ----------------------------------------------------------------------

SCHEME_CATEGORIES: Dict[str, List[str]] = {
    "housing": ["housing", "house", "awas", "pmay", "shelter", "home loan", "clss", "basti", "slum"],
    "agriculture": ["agriculture", "farmer", "farming", "kisan", "crop", "fertilizer", "irrigation", "pm-kisan", "pm kisan", "landholding", "fpo", "mandi", "seed"],
    "healthcare": ["healthcare", "health", "medical", "ayushman", "pmjay", "hospital", "treatment", "medicine", "insurance", "arogya", "swasthya", "clinic"],
    "education": ["education", "scholarship", "school", "college", "tuition", "student", "stipend", "fellowship", "fee waiver", "vidya", "coaching", "hostel"],
    "pension": ["pension", "retirement", "epfo", "atal pension", "old age pension", "ignoaps", "superannuation", "monthly pension", "elderly pension"],
    "social_security": ["social security", "welfare", "bpl", "subsidy", "ration", "food security", "destitute", "annapurna", "antyodaya", "ration card"],
    "women_and_child": ["maternal", "maternity", "pregnancy", "pregnant", "girl child", "sukanya", "ladli", "poshan", "anganwadi", "matru vandana", "beti padhao"],
    "employment": ["employment", "job", "mgnregs", "mgnrega", "skill", "training", "apprentice", "rozgar", "pmkvy", "unemployed", "wage", "work"],
    "sanitation": ["sanitation", "toilet", "swachh", "swachh bharat", "drainage", "sewer", "hygiene"],
    "energy": ["electricity", "solar", "lpg", "ujjwala", "gas cylinder", "gas connection", "power", "urja"],
    "finance": ["loan", "mudra", "credit", "subsidy", "bank account", "jan dhan", "insurance", "financial assistance", "cash grant", "interest subsidy"],
    "disability": ["disability", "divyang", "divyangjan", "handicap", "pwd", "aid and appliance", "wheelchair", "tricycle", "prosthetic"],
}

# Ordered by specificity: specialized groups first before generic 'woman' or 'individual'
BENEFICIARY_TYPES: Dict[str, List[str]] = {
    "shg": ["shg", "self help group", "women group", "samiti"],
    "farmer": ["farmer", "farmers", "kisan", "cultivator", "sharecropper", "agricultural worker"],
    "student": ["student", "students", "scholar", "scholars", "pupil", "youth", "learner"],
    "senior_citizen": ["senior citizen", "senior citizens", "elderly", "aged", "old age", "pensioner"],
    "widow": ["widow", "widows", "destitute woman", "single mother"],
    "artisan": ["artisan", "artisans", "weaver", "weavers", "craftsman", "carpenter", "blacksmith", "potter", "handicraft worker"],
    "unorganized_worker": ["unorganized worker", "daily wage worker", "construction worker", "laborer", "labourer", "migrant worker", "street vendor"],
    "bpl_family": ["bpl", "below poverty line", "ews", "poor family", "low income family", "antyodaya"],
    "person_with_disability": ["pwd", "disabled", "person with disability", "divyang", "differently abled"],
    "woman": ["woman", "women", "female", "girl", "mother", "lady"],
    "individual": ["individual", "citizen", "person", "applicant"],
}

OCCUPATIONS: Dict[str, List[str]] = {
    "farmer": ["farmer", "cultivator", "agricultural labourer", "sharecropper", "farm worker"],
    "artisan": ["artisan", "weaver", "craftsman", "carpenter", "blacksmith", "potter", "mason", "sculptor"],
    "construction_worker": ["construction worker", "building worker", "daily wage worker", "coolie", "mazdoor"],
    "street_vendor": ["street vendor", "vendor", "hawker", "cart puller", "small shopkeeper"],
    "student": ["student", "research scholar", "postgraduate", "undergraduate"],
    "healthcare_worker": ["asha worker", "anganwadi worker", "nurse", "paramedic"],
    "fisherman": ["fisherman", "fisherfolk", "aquaculture worker"],
    "domestic_worker": ["domestic worker", "maid", "cook", "cleaner", "housekeeper"],
    "unemployed": ["unemployed", "job seeker", "fresher"],
}

INDIAN_STATES_UTS: Dict[str, str] = {
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west bengal": "West Bengal",
    "delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "puducherry": "Puducherry",
    "chandigarh": "Chandigarh",
    "national": "National / All India",
    "all india": "National / All India",
}

MAJOR_DISTRICTS: Dict[str, Tuple[str, str]] = {
    "mumbai": ("Mumbai", "Maharashtra"),
    "pune": ("Pune", "Maharashtra"),
    "nagpur": ("Nagpur", "Maharashtra"),
    "bengaluru": ("Bengaluru", "Karnataka"),
    "bangalore": ("Bengaluru", "Karnataka"),
    "mysuru": ("Mysuru", "Karnataka"),
    "hyderabad": ("Hyderabad", "Telangana"),
    "chennai": ("Chennai", "Tamil Nadu"),
    "coimbatore": ("Coimbatore", "Tamil Nadu"),
    "madurai": ("Madurai", "Tamil Nadu"),
    "varanasi": ("Varanasi", "Uttar Pradesh"),
    "lucknow": ("Lucknow", "Uttar Pradesh"),
    "kanpur": ("Kanpur", "Uttar Pradesh"),
    "jaipur": ("Jaipur", "Rajasthan"),
    "jodhpur": ("Jodhpur", "Rajasthan"),
    "ahmedabad": ("Ahmedabad", "Gujarat"),
    "surat": ("Surat", "Gujarat"),
    "patna": ("Patna", "Bihar"),
    "kolkata": ("Kolkata", "West Bengal"),
    "bhopal": ("Bhopal", "Madhya Pradesh"),
    "indore": ("Indore", "Madhya Pradesh"),
    "ranchi": ("Ranchi", "Jharkhand"),
    "chandigarh": ("Chandigarh", "Chandigarh"),
}

INFO_TYPE_KEYWORDS: Dict[InformationType, List[str]] = {
    InformationType.ELIGIBILITY: [
        "eligible", "eligibility", "qualify", "criteria", "who can apply", "can i get",
        "am i eligible", "can i apply", "can i avail", "am i entitled", "entitlement",
        "age limit", "income limit", "conditions", "prerequisites", "allowed",
    ],
    InformationType.BENEFIT: [
        "benefit", "benefits", "how much money", "financial assistance", "amount", "subsidy",
        "pension amount", "grant", "stipend amount", "installment", "cash transfer", "how much",
    ],
    InformationType.DOCUMENTS: [
        "document", "documents", "paper", "papers", "paperwork", "certificate", "id proof",
        "proof of", "aadhaar", "ration card", "income certificate", "caste certificate", "what documents",
    ],
    InformationType.PROCESS: [
        "how to apply", "application process", "process", "procedure", "where to apply",
        "online application", "portal", "registration", "steps", "apply online", "fill form",
    ],
    InformationType.DEADLINE: [
        "deadline", "last date", "due date", "closing date", "cutoff", "expiry", "end date",
        "final date", "time limit",
    ],
    InformationType.CONTACT: [
        "contact", "helpline", "phone number", "toll free", "toll-free", "email", "officer",
        "nodal officer", "office address", "counter", "helpdesk", "whom to contact",
    ],
    InformationType.STATUS: [
        "status", "application status", "track", "tracking", "check status", "reference number",
        "application number", "list", "name in list", "beneficiary list",
    ],
}


class QueryUnderstandingService:
    """
    Intelligent query understanding service for extracting structured welfare domain entities
    and generating safe clarification questions prior to retrieval.
    """

    def extract_information_type(self, query: str) -> InformationType:
        """Classify requested information type."""
        q_lower = query.lower().strip()
        for info_type, keywords in INFO_TYPE_KEYWORDS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                    return info_type
        return InformationType.GENERAL

    def extract_age(self, query: str) -> Optional[int]:
        """Extract explicit applicant age if specified."""
        q_lower = query.lower().strip()
        patterns = [
            r"\b(?:age(?:d)?|years? old)\s*[:=]?\s*(\d{1,3})\b",
            r"\b(\d{1,3})\s*(?:years?(?:\s*old)?|yo|yrs?)\b",
            r"\b(?:above|over|more than|exceeding)\s*(\d{1,3})\b",
            r"\b(?:under|below|less than)\s*(\d{1,3})\b",
            r"\bage\s*of\s*(\d{1,3})\b",
            r"\bi am\s*(\d{1,3})\b",
        ]
        for pat in patterns:
            match = re.search(pat, q_lower)
            if match:
                try:
                    val = int(match.group(1))
                    if 0 < val <= 120:
                        return val
                except ValueError:
                    continue
        return None

    def extract_gender(self, query: str) -> Optional[str]:
        """Extract gender where relevant."""
        q_lower = query.lower().strip()
        if re.search(r"\b(transgender|trans\s*woman|trans\s*man|third\s*gender)\b", q_lower):
            return "transgender"
        if re.search(r"\b(woman|women|female|girl|mother|widow|daughter|she|her|lady)\b", q_lower):
            return "female"
        if re.search(r"\b(man|men|male|boy|father|son|he|him|gentleman)\b", q_lower):
            return "male"
        return None

    def extract_scheme_category(self, query: str) -> Optional[str]:
        """Extract primary scheme domain/category."""
        q_lower = query.lower().strip()
        for cat, kws in SCHEME_CATEGORIES.items():
            for kw in kws:
                if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                    return cat
        return None

    def extract_beneficiary_type(self, query: str) -> Optional[str]:
        """Extract primary beneficiary group."""
        q_lower = query.lower().strip()
        for b_type, kws in BENEFICIARY_TYPES.items():
            for kw in kws:
                if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                    return b_type
        return None

    def extract_occupation(self, query: str) -> Optional[str]:
        """Extract applicant occupation."""
        q_lower = query.lower().strip()
        for occ, kws in OCCUPATIONS.items():
            for kw in kws:
                if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                    return occ
        return None

    def extract_income(self, query: str) -> Tuple[Optional[str], Optional[float]]:
        """Extract income range descriptor and parsed upper bound."""
        q_lower = query.lower().strip()
        # Check standard category keywords
        if re.search(r"\b(bpl|below poverty line)\b", q_lower):
            return "BPL", 150000.0
        if re.search(r"\b(ews|economically weaker section)\b", q_lower):
            return "EWS", 300000.0
        if re.search(r"\b(antyodaya|aay)\b", q_lower):
            return "Antyodaya", 100000.0

        # Numeric income matching e.g. "income 2.5 lakh", "income below 300000", "salary 20000"
        pat = r"\b(?:income|salary|earnings?)\s*(?:is|of|below|under|up\s*to|<|less\s*than)?\s*(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|lac|k|thousand|crore)?\b"
        match = re.search(pat, q_lower)
        if match:
            raw_num_str = match.group(1).replace(",", "")
            unit = match.group(2)
            try:
                base_val = float(raw_num_str)
                if unit in ["lakh", "lakhs", "lac"]:
                    parsed_val = base_val * 100000.0
                elif unit in ["k", "thousand"]:
                    parsed_val = base_val * 1000.0
                elif unit == "crore":
                    parsed_val = base_val * 10000000.0
                else:
                    parsed_val = base_val

                descriptor = f"<= Rs. {parsed_val:,.0f}"
                return descriptor, parsed_val
            except ValueError:
                pass

        # Standalone lakh/amount pattern e.g. "under 3 lakh"
        standalone_pat = r"\b(?:under|below|less\s*than|up\s*to)\s*(?:rs\.?|inr)?\s*([\d.]+)\s*(lakh|lakhs|lac)\b"
        st_match = re.search(standalone_pat, q_lower)
        if st_match:
            try:
                val = float(st_match.group(1)) * 100000.0
                return f"<= Rs. {val:,.0f}", val
            except ValueError:
                pass

        return None, None

    def extract_location(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract state/district and locality (rural vs urban)."""
        q_lower = query.lower().strip()
        state_or_district = None
        locality = None

        # Locality
        if re.search(r"\b(rural|village|gram\s*panchayat|taluka|tehsil)\b", q_lower):
            locality = "rural"
        elif re.search(r"\b(urban|city|town|municipality|municipal|metro|slum)\b", q_lower):
            locality = "urban"

        # Check districts first (more specific)
        for dist_key, (dist_name, state_name) in MAJOR_DISTRICTS.items():
            if re.search(r"\b" + re.escape(dist_key) + r"\b", q_lower):
                state_or_district = f"{dist_name}, {state_name}"
                break

        # Check states if no district found
        if not state_or_district:
            for st_key, st_name in INDIAN_STATES_UTS.items():
                if re.search(r"\b" + re.escape(st_key) + r"\b", q_lower):
                    state_or_district = st_name
                    break

        return state_or_district, locality

    def extract_disability(self, query: str) -> Optional[str]:
        """Extract disability status and percentage."""
        q_lower = query.lower().strip()
        if re.search(
            r"\b(pwd|disabled|disability|divyang|divyangjan|handicapped|physically challenged|blind|visually impaired|locomotor|hearing impaired)\b",
            q_lower,
        ):
            # Check for percentage e.g. "40% disability", "50%"
            pct_match = re.search(r"\b(\d{1,3})%\s*(?:disability|benchmark)?\b", q_lower)
            if pct_match:
                return f"PwD ({pct_match.group(1)}% benchmark disability)"
            return "PwD / Divyangjan"
        return None

    def extract_profile_terms(self, query: str) -> List[str]:
        """Aggregate list of recognized demographic and socio-economic profile terms."""
        q_lower = query.lower().strip()
        terms: Set[str] = set()

        profile_mapping = {
            "student": ["student", "students", "scholar"],
            "farmer": ["farmer", "farmers", "kisan", "cultivator"],
            "widow": ["widow", "widows"],
            "senior-citizen": ["senior citizen", "senior citizens", "elderly", "pensioner", "aged"],
            "bpl": ["bpl", "below poverty line", "antyodaya", "ews"],
            "artisan": ["artisan", "artisans", "weaver", "weavers", "craftsman"],
            "disabled": ["pwd", "disabled", "disability", "divyang"],
            "transgender": ["transgender", "third gender"],
            "unorganized-worker": ["daily wage worker", "construction worker", "laborer", "labourer", "migrant worker", "vendor"],
            "woman": ["woman", "women", "female", "girl child", "mother"],
            "sc-st": ["sc", "st", "scheduled caste", "scheduled tribe", "dalit", "adivasi"],
            "minority": ["minority", "minorities"],
        }

        for badge, keywords in profile_mapping.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                    terms.add(badge)
                    break

        # If age is 60 or above, automatically tag as senior-citizen
        age = self.extract_age(q_lower)
        if age is not None and age >= 60:
            terms.add("senior-citizen")

        return sorted(list(terms))

    def evaluate_safety_and_followup(
        self,
        query: str,
        query_lower: str,
        info_type: InformationType,
        scheme_cat: Optional[str],
        age: Optional[int],
        gender: Optional[str],
        income_range: Optional[str],
        occupation: Optional[str],
        state_or_district: Optional[str],
        disability_status: Optional[str],
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Evaluate if query can be answered safely without guessing.
        Generates a concise follow-up question when critical parameters are missing for eligibility determination.
        Returns (is_safe_to_answer, follow_up_question, missing_critical_fields).
        """
        # Informational queries (documents, benefit amounts, process steps, deadlines, contact, status)
        # do not require personal demographic disclosures to answer safely from official documents.
        if info_type in [
            InformationType.DOCUMENTS,
            InformationType.BENEFIT,
            InformationType.PROCESS,
            InformationType.DEADLINE,
            InformationType.CONTACT,
            InformationType.STATUS,
            InformationType.GENERAL,
        ]:
            return True, None, []

        # When evaluating eligibility, check whether required criteria are present
        missing: List[str] = []

        # 1. Housing Schemes (e.g., PMAY) require income tier
        if scheme_cat == "housing" or "pmay" in query_lower or "housing" in query_lower:
            if income_range is None:
                missing.append("annual_income")
                return (
                    False,
                    "To verify eligibility for housing assistance (such as PMAY), what is your annual household income?",
                    missing,
                )

        # 2. Old Age / Pension schemes require age
        if scheme_cat == "pension" or "old age" in query_lower or "pension" in query_lower or "senior" in query_lower:
            if age is None:
                missing.append("age")
                return (
                    False,
                    "To check eligibility for the old-age pension scheme, could you please specify your current age?",
                    missing,
                )

        # 3. Agriculture / PM-Kisan schemes require landholding or farmer status
        if scheme_cat == "agriculture" or "kisan" in query_lower or "pm-kisan" in query_lower or "pm kisan" in query_lower:
            if occupation != "farmer" and "farmer" not in query_lower and "land" not in query_lower:
                missing.append("farmer_status_and_landholding")
                return (
                    False,
                    "To determine eligibility for PM-Kisan benefits, do you own cultivable agricultural land as a farmer?",
                    missing,
                )

        # 4. Disability schemes require certified status or benchmark percentage
        if scheme_cat == "disability" or "disability" in query_lower or "divyang" in query_lower:
            if disability_status is None:
                missing.append("disability_status")
                return (
                    False,
                    "To check eligibility for disability welfare schemes, what is your certified benchmark disability percentage (e.g. 40% or above)?",
                    missing,
                )

        # 5. Generic eligibility question with no scheme context or demographics
        if info_type == InformationType.ELIGIBILITY:
            if not scheme_cat and not age and not income_range and not occupation and not disability_status:
                missing.append("scheme_name_or_category")
                return (
                    False,
                    "Which government welfare scheme or category (e.g., housing, agriculture, pension, education) would you like to check eligibility for?",
                    missing,
                )

        return True, None, []

    def understand_query(self, query: str) -> QueryUnderstandingResult:
        """
        Analyze user query, extract structured fields, validate against schema,
        and generate safe follow-up questions when necessary.
        Guaranteed to never fail or block ordinary search.
        """
        if not query or not query.strip():
            return QueryUnderstandingResult(
                raw_query="",
                information_type=InformationType.GENERAL,
                is_safe_to_answer=True,
            )

        clean_query = query.strip()
        query_lower = clean_query.lower()

        try:
            # 1. Extract structured entities using instance methods
            info_type = self.extract_information_type(clean_query)
            scheme_cat = self.extract_scheme_category(clean_query)
            beneficiary_type = self.extract_beneficiary_type(clean_query)
            age = self.extract_age(clean_query)
            gender = self.extract_gender(clean_query)
            income_range, max_income = self.extract_income(clean_query)
            occupation = self.extract_occupation(clean_query)
            state_or_district, locality = self.extract_location(clean_query)
            disability_status = self.extract_disability(clean_query)
            profile_terms = self.extract_profile_terms(clean_query)

            # Auto-align beneficiary type if specific profiles detected
            if not beneficiary_type:
                if "widow" in profile_terms:
                    beneficiary_type = "widow"
                elif "student" in profile_terms:
                    beneficiary_type = "student"
                elif "farmer" in profile_terms:
                    beneficiary_type = "farmer"
                elif "senior-citizen" in profile_terms:
                    beneficiary_type = "senior_citizen"

            # 2. Evaluate safety and generate concise follow-up question if required
            is_safe, follow_up, missing = self.evaluate_safety_and_followup(
                query=clean_query,
                query_lower=query_lower,
                info_type=info_type,
                scheme_cat=scheme_cat,
                age=age,
                gender=gender,
                income_range=income_range,
                occupation=occupation,
                state_or_district=state_or_district,
                disability_status=disability_status,
            )

            extracted_entities = {
                k: v
                for k, v in {
                    "scheme_category": scheme_cat,
                    "beneficiary_type": beneficiary_type,
                    "age": age,
                    "gender": gender,
                    "income_range": income_range,
                    "max_income": max_income,
                    "occupation": occupation,
                    "state_or_district": state_or_district,
                    "locality": locality,
                    "disability_status": disability_status,
                    "profile_terms": profile_terms,
                    "information_type": info_type.value,
                }.items()
                if v is not None and v != []
            }

            # 3. Construct and validate result
            result_data = {
                "raw_query": clean_query,
                "scheme_category": scheme_cat,
                "beneficiary_type": beneficiary_type,
                "age": age,
                "gender": gender,
                "income_range": income_range,
                "max_income": max_income,
                "occupation": occupation,
                "state_or_district": state_or_district,
                "locality": locality,
                "disability_status": disability_status,
                "profile_terms": profile_terms,
                "information_type": info_type,
                "follow_up_question": follow_up,
                "is_safe_to_answer": is_safe,
                "missing_critical_fields": missing,
                "extracted_entities": extracted_entities,
                "confidence": 1.0,
            }

            return QueryUnderstandingResult.model_validate(result_data)

        except Exception as e:
            logger.warning(
                f"Query understanding extraction or validation encountered an error: {e}. "
                f"Falling back safely to unparsed query to avoid blocking search."
            )
            # Fail-safe non-blocking fallback
            return QueryUnderstandingResult(
                raw_query=clean_query,
                information_type=InformationType.GENERAL,
                is_safe_to_answer=True,
                confidence=0.0,
            )


query_understanding_service = QueryUnderstandingService()
