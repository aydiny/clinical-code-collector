"""
Node 3: Validator / Critic Agent — METADATA-DRIVEN DISCOVERY
Matches new OpenCodelists Index while preserving legacy NICEState boolean flags.
"""
import asyncio
import sys
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.state import NICEState, ValidatedCode
from config.opencodelists_index import OPENCODELISTS_INDEX
from tools.opencodelists_loader import load_codelist_from_url
import numpy as np

# Load environment variables (ensures OPENAI_API_KEY is available)
load_dotenv()

# Define the embedding model globally for the node
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

# Instantiate the model
embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME)

# -------------------------------------------------------------------
# UNIVERSAL Confidence Weights (Metadata-Driven)
# -------------------------------------------------------------------
CONFIDENCE_WEIGHTS = {
    "intent_qof_register":          +0.45,  # Highest clinical anchor
    "intent_nhsd_curated":          +0.40,  # Official NHS audit lists
    "intent_safety_audit":          +0.35,  # e.g., PINCER
    "intent_epidemiology":          +0.25,  # e.g., OpenSAFELY, QCovid
    "clinical_course_matches":      +0.10,
    "clinical_course_mismatch":     -0.50,
}

TIER_THRESHOLDS = {
    "tier_1": 0.70,
    "tier_2": 0.45,
    "tier_3": 0.25,
    "exclude": 0.25
}

def calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculates the cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# ===================================================================
# LAYER 1: OpenCodelists Discovery 
# ===================================================================
def _fetch_opencodelists(
    primary_condition: str,
    search_terms: list[str],
    relevant_medications: list[str],
    relevant_observations: list[str]
) -> list[dict]:
    
    diag_text = " ".join([primary_condition] + search_terms).lower()
    med_text = " ".join(relevant_medications).lower()
    obs_text = " ".join(relevant_observations).lower()

    codelists = []
    seen_urls = set()

    for keyword, entries in OPENCODELISTS_INDEX.items():
        if keyword in diag_text or keyword in med_text or keyword in obs_text:
            for entry in entries:
                if entry["url"] in seen_urls:
                    continue
                seen_urls.add(entry["url"])
                
                try:
                    members = load_codelist_from_url(entry["url"])
                    if members:
                        codelists.append({
                            "codelist_id":     f"opencodelists/{entry['org']}/{keyword}",
                            "name":            entry["name"],
                            "organisation":    entry["org"],
                            "intent":          entry.get("intent", "Epidemiology"),
                            "category":        entry.get("category", "Diagnosis"),
                            "members":         members
                        })
                        print(f"[validator:API] Loaded '{entry['name']}': {len(members)} codes")
                except Exception as e:
                    print(f"[validator:API] ⚠️ Skipping URL: {entry['url']}")

    return codelists

# ===================================================================
# CODE-LEVEL VALIDATION (Maps to Legacy State)
# ===================================================================
async def _validate_single_code(
    candidate: dict,
    all_codelists: list[dict],
    primary_condition: str,
    expected_course: str,
    category_exclusions: list[str],
    target_vec: list[float],     # NEW
    candidate_vec: list[float]   # NEW
) -> tuple[dict | None, str | None]:

    snomed_id      = candidate.get("snomed_id", "")
    preferred_term = candidate.get("preferred_term", "")
    category       = candidate.get("category", "Diagnosis")
    score          = 0.0
    semantic_score = 0.0

    # 1. Filter out exact exclusions for this category
    if any(excl.lower() in preferred_term.lower() for excl in category_exclusions if excl.strip()):
        return None, None

    found_in_names = []
    unique_intents = set()
    unique_origins = set() # For deduplicated found_count
    highest_intent_weight = 0.0

    is_qof = False
    is_nhsd = False
    res_ocl = None

    # 2. Check all fetched codelists
    for codelist in all_codelists:
        if snomed_id in codelist.get("members", set()):
            found_in_names.append(codelist["name"])
            intent = codelist["intent"]
            org = codelist["organisation"]
            
            unique_intents.add(intent)
            unique_origins.add(f"{org}_{intent}") # Deduplicates mirrored lists
            
            if "QOF" in intent:
                is_qof = True
            elif org == "nhsd-primary-care-domain-refsets":
                is_nhsd = True
            else:
                res_ocl = intent

            # Determine highest base weight
            if intent == "QOF_Register":
                highest_intent_weight = max(highest_intent_weight, CONFIDENCE_WEIGHTS["intent_qof_register"])
            elif intent == "NHSD_Curated":
                highest_intent_weight = max(highest_intent_weight, CONFIDENCE_WEIGHTS["intent_nhsd_curated"])
            elif intent == "Safety_Audit":
                highest_intent_weight = max(highest_intent_weight, CONFIDENCE_WEIGHTS["intent_safety_audit"])
            elif intent == "Epidemiology":
                highest_intent_weight = max(highest_intent_weight, CONFIDENCE_WEIGHTS["intent_epidemiology"])

    # Base score is the strongest organizational signal we found
    score += highest_intent_weight

    # Consensus Bonus: Multiple independent clinical origins agree
    found_count = len(unique_origins)
    if found_count >= 2:
        score += 0.20

    # ── 3. BRANCHING SCORING LOGIC BASED ON CATEGORY ──

    # Calculate Semantic Score using Vector Math!
    semantic_score = calculate_cosine_similarity(candidate_vec, target_vec)

    if category == "Diagnosis":
        # Semantic overlap check
        if semantic_score >= 0.8: score += 0.20
        elif semantic_score >= 0.5: score += 0.10
        
        # Clinical course check (acute vs chronic)
        if expected_course != "either":
            term_lower = preferred_term.lower()
            actual_course = "chronic" if any(w in term_lower for w in ["chronic", "permanent", "persistent", "paroxysmal", "controlled", "stable"]) else "acute" if any(w in term_lower for w in ["acute", "decompensated", "emergency", "crisis"]) else None
            if actual_course:
                if actual_course == expected_course: score += CONFIDENCE_WEIGHTS["clinical_course_matches"]
                else: score += CONFIDENCE_WEIGHTS["clinical_course_mismatch"]

    elif category in ["Medication", "Observation"]:
        # Semantic boost for medications and observations
        if semantic_score >= 0.80: score += 0.20
        elif semantic_score >= 0.60: score += 0.10
        
        if len(found_in_names) == 0:
            score += 0.30
        else:
            score += 0.50

    confidence = min(max(round(score, 2), 0.0), 1.0)

    if confidence < TIER_THRESHOLDS["exclude"]:
        return None, snomed_id

    # Strictly map back to the ValidatedCode TypedDict structure
    validated = {
        "snomed_id":           snomed_id,
        "preferred_term":      preferred_term,
        "confidence_score":    confidence,
        "opencodelists_match": res_ocl,  # Translates array existence to boolean
        "qof_match":           is_qof,                   # Translated from intents
        "semantic_score":      semantic_score,           # Translated from overlap logic
        "found_in_codelists":  found_in_names,
        "is_nhsd_refset":      is_nhsd,                  # Translated from organization field
        "found_count":         found_count,              # Deduplicated count
        "category":            category                  # Passed along for internal node printing
    }

    return validated, None

# ===================================================================
# MAIN NODE FUNCTION
# ===================================================================
def _infer_expected_course(research_question: str) -> str:
    q = research_question.lower()
    if any(s in q for s in ["chronic", "long-term", "stable", "eligible", "register"]): return "chronic"
    if any(s in q for s in ["acute", "emergency", "admission", "exacerbation"]): return "acute"
    return "either"

async def validator_node(state: NICEState) -> dict:
    candidate_codes         = state.get("candidate_codes", [])
    primary_condition       = state.get("primary_condition", "")
    research_question       = state.get("research_question", "")
    search_terms            = state.get("search_terms", [])
    iteration_count         = state.get("iteration_count", 0)
    
    excluded_diagnoses      = state.get("excluded_diagnoses", [])
    excluded_medications    = state.get("excluded_medications", [])
    excluded_observations   = state.get("excluded_observations", [])
    relevant_medications    = state.get("relevant_medications", [])
    relevant_observations   = state.get("relevant_observations", [])
    
    expected_course         = _infer_expected_course(research_question)

    validated_codes = []
    low_confidence_ids = []

    print(f"\n[validator] ── Starting validation ──")
    print(f"[validator] Candidates : {len(candidate_codes)}")

    # 1. Fetch Lists (Only OpenCodelists now)
    all_codelists = _fetch_opencodelists(primary_condition, search_terms, relevant_medications, relevant_observations)

    # ── NEW: BATCH EMBEDDING FOR COSINE SIMILARITY ──
    print(f"[validator] Generating semantic vector embeddings...")
    
    # We create target text strings for each category to compare against
    target_texts = [
        primary_condition,                           # Target for Diagnoses
        " ".join(relevant_medications),              # Target for Medications
        " ".join(relevant_observations)              # Target for Observations
    ]
    
    # We grab all candidate terms
    candidate_terms = [c.get("preferred_term", "") for c in candidate_codes]
    
    # Batch embed everything in two API calls (fast!)
    target_embeddings = await embedding_model.aembed_documents(target_texts)
    candidate_embeddings = await embedding_model.aembed_documents(candidate_terms)
    
    target_diag_vec = target_embeddings[0]
    target_med_vec = target_embeddings[1]
    target_obs_vec = target_embeddings[2]

    # 2. Score Candidates
    for i, candidate in enumerate(candidate_codes):
        category = candidate.get("category", "Diagnosis")
        cat_exclusions = excluded_medications if category == "Medication" else (excluded_observations if category == "Observation" else excluded_diagnoses)

        # Select the correct target vector based on category
        target_vec = target_med_vec if category == "Medication" else (target_obs_vec if category == "Observation" else target_diag_vec)
        candidate_vec = candidate_embeddings[i]

        validated, low_conf_id = await _validate_single_code(
            candidate=candidate,
            all_codelists=all_codelists,
            primary_condition=primary_condition,
            expected_course=expected_course,
            category_exclusions=cat_exclusions,
            target_vec=target_vec,          
            candidate_vec=candidate_vec     
        )

        if validated: validated_codes.append(validated)
        elif low_conf_id: low_confidence_ids.append(low_conf_id)

    # 3. Print Output
    print("\n=================================================================")
    print("  FINAL CATEGORIZED CODELIST")
    print("=================================================================\n")
    
    diag_codes = [v for v in validated_codes if v.get("category") == "Diagnosis"]
    med_codes = [v for v in validated_codes if v.get("category") == "Medication"]
    obs_codes = [v for v in validated_codes if v.get("category") == "Observation"]

    for cat_name, codes in [("DIAGNOSES", diag_codes), ("MEDICATIONS", med_codes), ("OBSERVATIONS", obs_codes)]:
        if codes:
            print(f"  ── {cat_name} [{len(codes)} codes] ──")
            for v in sorted(codes, key=lambda x: x["confidence_score"], reverse=True):
                print(f"  {v['confidence_score']:.2f}  {v['snomed_id']:<18} {v['preferred_term'][:60]}")
            print("")

    #routing = "loop_back" if low_confidence_ids and iteration_count < 3 else "proceed"
    routing = "proceed"

    return {
        "validated_codes": validated_codes,
        "low_confidence_codes": low_confidence_ids,
        "iteration_count": iteration_count + 1,
        "routing_decision": routing,
    }