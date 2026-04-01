"""
Node 3: Validator / Critic Agent — DYNAMIC + THREE-LAYER DISCOVERY
Layer 1: OpenCodelists API         (fully automatic)
Layer 2: TRUD local refset index   (semi-automatic — index maintained manually)
Layer 3: Human review flag         (catches anything layers 1+2 miss)
"""
import asyncio
import sys
import os
import requests
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.state import NICEState, ValidatedCode
from config.trud_refset_index import fuzzy_match_trud
from tools.trud_data import get_members, refset_exists, get_refset_name
from config.opencodelists_index import OPENCODELISTS_INDEX
from tools.opencodelists_loader import load_codelist_from_url

# -------------------------------------------------------------------
# UNIVERSAL Confidence Weights — condition-agnostic
# -------------------------------------------------------------------
CONFIDENCE_WEIGHTS = {
    "found_in_nhsd_refset":         +0.50,
    "found_in_qof_register":        +0.45,
    "found_in_trud_refset":         +0.40,
    "found_in_one_codelist":        +0.35,
    "clinical_course_matches":      +0.10,
    "finding_site_matches":         +0.05,
    "umbrella_code_only":           -0.30,
    "finding_not_disorder":         -0.20,
    "clinical_course_mismatch":     -0.50,
}

TIER_THRESHOLDS = {
    "tier_1": 0.70,
    "tier_2": 0.45,
    "tier_3": 0.25,
    "exclude": 0.25
}

# ===================================================================
# LAYER 1: OpenCodelists Discovery
# ===================================================================
def _layer1_opencodelists(
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
                            "members":         members,
                            "discovery_layer": "opencodelists"
                        })
                        print(f"[validator:L1] Loaded '{entry['name']}': {len(members)} codes")
                except Exception as e:
                    print(f"[validator:L1] ⚠️ Skipping URL (likely expired/404): {entry['url']}")

    print(f"[validator:L1] Found {len(codelists)} codelists")
    return codelists

# ===================================================================
# LAYER 2: TRUD Local Refset Index
# ===================================================================
def _layer2_trud(primary_condition: str, search_terms: list[str]) -> list[dict]:
    all_text = " ".join([primary_condition] + search_terms)
    matches = fuzzy_match_trud(all_text)

    if not matches:
        return []

    trud_codelists = []
    for keyword, refset_id in matches:
        if not refset_exists(refset_id):
            continue

        members = get_members(refset_id)
        if members:
            trud_codelists.append({
                "codelist_id":     f"trud/{refset_id}",
                "name":            f"TRUD Refset {refset_id} ({keyword})",
                "organisation":    "NHS Digital (TRUD)",
                "refset_id":       refset_id,
                "members":         members,
                "discovery_layer": "trud"
            })
            print(f"[validator:L2] Loaded {refset_id}: {len(members)} members")

    return trud_codelists

# ===================================================================
# CODE-LEVEL VALIDATION
# ===================================================================
async def _validate_single_code(
    candidate: dict,
    all_codelists: list[dict],
    primary_condition: str,
    expected_course: str,
    category_exclusions: list[str]
) -> tuple[dict | None, str | None]:

    snomed_id      = candidate.get("snomed_id", "")
    preferred_term = candidate.get("preferred_term", "")
    source         = candidate.get("source", "snomed_search")
    category       = candidate.get("category", "Diagnosis")  # <-- THE CRITICAL LINE!
    score          = 0.0

    # 1. Filter out exact exclusions for this category
    if any(excl.lower() in preferred_term.lower() for excl in category_exclusions if excl.strip()):
        return None, None

    found_in_names = []
    is_nhsd = is_trud = is_qof = False

    # 2. Check all codelists
    for codelist in all_codelists:
        members = codelist.get("members", set())
        if snomed_id in members:
            found_in_names.append(codelist["name"])
            layer = codelist.get("discovery_layer")
            
            if layer == "trud":
                is_trud = True
                if "nhs digital" in codelist.get("organisation", "").lower(): is_nhsd = True
            elif layer == "opencodelists":
                org = codelist.get("organisation", "").lower()
                name = codelist.get("name", "").lower()
                if any(t in org for t in ["nhsd", "nhs digital", "primary care domain"]): is_nhsd = True
                if any(t in name for t in ["qof", "quality and outcomes", "business rules", "register"]): is_qof = True

    found_count = len(found_in_names)

    # ── 3. BRANCHING SCORING LOGIC BASED ON CATEGORY ──
    if category == "Diagnosis":
        # Strict disease grading
        if source.startswith("relationship_"): score += CONFIDENCE_WEIGHTS["finding_not_disorder"]
        if is_qof: score += CONFIDENCE_WEIGHTS["found_in_qof_register"]
        elif is_nhsd: score += CONFIDENCE_WEIGHTS["found_in_nhsd_refset"]
        elif is_trud: score += CONFIDENCE_WEIGHTS["found_in_trud_refset"]
        elif found_count >= 1: score += CONFIDENCE_WEIGHTS["found_in_one_codelist"]

        if found_count >= 3: score += 0.20
        elif found_count == 2: score += 0.10

        term_words = set(preferred_term.lower().split())
        condition_words = set(primary_condition.lower().split())
        overlap = len(term_words & condition_words) / max(len(condition_words), 1)
        if overlap >= 0.8: score += 0.20
        elif overlap >= 0.5: score += 0.10
        
        if expected_course != "either":
            term_lower = preferred_term.lower()
            actual_course = "chronic" if any(w in term_lower for w in ["chronic", "permanent", "persistent", "paroxysmal", "controlled", "stable"]) else "acute" if any(w in term_lower for w in ["acute", "decompensated", "emergency", "crisis"]) else None
            if actual_course:
                if actual_course == expected_course: score += CONFIDENCE_WEIGHTS["clinical_course_matches"]
                else: score += CONFIDENCE_WEIGHTS["clinical_course_mismatch"]

    elif category == "Medication" or category == "Observation":
        # Fast-track supplementary codes! If it hits an OpenCodelist, it gets a near-perfect score.
        score = 0.90 + (0.05 if found_count > 0 else 0.0)

    confidence = min(max(round(score, 2), 0.0), 1.0)

    if confidence < TIER_THRESHOLDS["exclude"]:
        return None, snomed_id

    validated = {
        "snomed_id":           snomed_id,
        "preferred_term":      preferred_term,
        "confidence_score":    confidence,
        "opencodelists_match": found_count > 0,
        "qof_match":           is_qof,
        "semantic_score":      0.0,
        "found_in_codelists":  found_in_names,
        "is_nhsd_refset":      is_nhsd,
        "found_count":         found_count,
        "category":            category
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

    # 1. Fetch Lists
    l1_codelists = _layer1_opencodelists(primary_condition, search_terms, relevant_medications, relevant_observations)
    l2_codelists = _layer2_trud(primary_condition, search_terms)
    all_codelists = l1_codelists + l2_codelists

    # 2. Score Candidates
    for candidate in candidate_codes:
        category = candidate.get("category", "Diagnosis")
        
        # Route to correct exclusions
        cat_exclusions = excluded_medications if category == "Medication" else (excluded_observations if category == "Observation" else excluded_diagnoses)

        validated, low_conf_id = await _validate_single_code(
            candidate=candidate,
            all_codelists=all_codelists,
            primary_condition=primary_condition,
            expected_course=expected_course,
            category_exclusions=cat_exclusions
        )
        if validated: validated_codes.append(validated)
        elif low_conf_id: low_confidence_ids.append(low_conf_id)

    # 3. Print Output
    print("\n=================================================================")
    print("  FINAL CATEGORIZED CODELIST")
    print("=================================================================\n")
    
    diag_codes = [v for v in validated_codes if v.get("category", "Diagnosis") == "Diagnosis"]
    med_codes = [v for v in validated_codes if v.get("category") == "Medication"]
    obs_codes = [v for v in validated_codes if v.get("category") == "Observation"]

    print(f"  ── CORE DIAGNOSES [{len(diag_codes)} codes] ──")
    for v in sorted(diag_codes, key=lambda x: x["confidence_score"], reverse=True):
        print(f"  {v['confidence_score']:.2f}  {v['snomed_id']:<18} {v['preferred_term'][:60]}")

    if med_codes:
        print(f"\n  ── SUPPLEMENTARY MEDICATIONS [{len(med_codes)} codes] ──")
        for v in sorted(med_codes, key=lambda x: x["confidence_score"], reverse=True):
            print(f"  {v['confidence_score']:.2f}  {v['snomed_id']:<18} {v['preferred_term'][:60]}")

    if obs_codes:
        print(f"\n  ── SUPPLEMENTARY OBSERVATIONS [{len(obs_codes)} codes] ──")
        for v in sorted(obs_codes, key=lambda x: x["confidence_score"], reverse=True):
            print(f"  {v['confidence_score']:.2f}  {v['snomed_id']:<18} {v['preferred_term'][:60]}")

    routing = "loop_back" if low_confidence_ids and iteration_count < 3 else "proceed"
    return {
        "validated_codes": validated_codes,
        "low_confidence_codes": low_confidence_ids,
        "iteration_count": iteration_count + 1,
        "routing_decision": routing,
    }