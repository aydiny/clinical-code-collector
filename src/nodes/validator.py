"""
Node 3: Validator / Critic Agent — DYNAMIC + THREE-LAYER DISCOVERY
Layer 1: OpenCodelists API         (fully automatic)
Layer 2: TRUD local refset index   (semi-automatic — index maintained manually)
Layer 3: Human review flag         (catches anything layers 1+2 miss)
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from langchain_mcp_adapters.client import MultiServerMCPClient
from src.state import NICEState, ValidatedCode
from config.trud_refset_index import fuzzy_match_trud
#from tools.trud_lookup import load_refset, refset_exists
from tools.trud_data import get_members, refset_exists, get_refset_name

# -------------------------------------------------------------------
# UNIVERSAL Confidence Weights — condition-agnostic
# -------------------------------------------------------------------
CONFIDENCE_WEIGHTS = {
    "found_in_nhsd_refset":         +0.50,
    "found_in_qof_register":        +0.45,   # QOF-specific signal
    "found_in_trud_refset":         +0.40,  # slightly lower — local copy may lag
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
from config.opencodelists_index import OPENCODELISTS_INDEX
from tools.opencodelists_loader import load_codelist_from_url

def _layer1_opencodelists(
    primary_condition: str,
    search_terms: list[str]
) -> list[dict]:
    all_text = " ".join([primary_condition] + search_terms).lower()
    codelists = []
    seen_urls = set()

    for keyword, entries in OPENCODELISTS_INDEX.items():
        if keyword in all_text:
            for entry in entries:
                if entry["url"] in seen_urls:
                    continue
                seen_urls.add(entry["url"])
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

    print(f"[validator:L1] Found {len(codelists)} codelists")
    return codelists

def _extract_snomed_id(member: dict) -> str | None:
    """Extract SNOMED concept ID — explicit keys only, never generic 'id'."""
    for key in ("snomed_id", "concept_id", "conceptId",
                "code", "referencedComponentId"):   # ← "id" REMOVED
        val = member.get(key, "")
        if val and str(val).strip():
            # Validate it looks like a SNOMED ID (6-18 digits, no hyphens)
            cleaned = str(val).strip()
            if cleaned.isdigit() and 6 <= len(cleaned) <= 18:
                return cleaned
    return None

# ===================================================================
# LAYER 2: TRUD Local Refset Index
# ===================================================================
def _layer2_trud(
    primary_condition: str,
    search_terms: list[str]
) -> list[dict]:
    """
    Layer 2: Match against TRUD refset index using fuzzy keyword matching.
    Loads matched refsets from local TRUD CSV files directly.
    """
    all_text = " ".join([primary_condition] + search_terms)
    matches = fuzzy_match_trud(all_text)

    if not matches:
        print(f"[validator:L2] No TRUD refset match for '{primary_condition}'")
        return []

    print(f"[validator:L2] TRUD matches: {[(kw, rid) for kw, rid in matches]}")

    trud_codelists = []
    for keyword, refset_id in matches:
        if not refset_exists(refset_id):
            print(f"[validator:L2] Refset file missing: {refset_id}")
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
# LAYER 3: Human Review Flag
# ===================================================================
def _layer3_flag_if_empty(
    codelists: list[dict],
    primary_condition: str
) -> dict:
    """
    Layer 3: If layers 1+2 found nothing, flag for human review.
    Returns state updates to merge — empty dict if codelists found.
    """
    if codelists:
        return {}

    print(f"[validator:L3] WARNING: No reference codelists found for "
          f"'{primary_condition}' — flagging for human review")
    return {
        "human_review_flag": True,
        "human_review_reason": (
            f"No reference codelist found for '{primary_condition}'. "
            f"Validation proceeded without codelist cross-check. "
            f"Please supply an OpenCodelists URL or TRUD refset ID "
            f"before approving this output."
        )
    }


# ===================================================================
# CODE-LEVEL VALIDATION
# ===================================================================
async def _validate_single_code(
    candidate: dict,
    all_codelists: list[dict],
    primary_condition: str,
    expected_course: str,
    concept_type: str,
    explicit_exclusions: list[str],
    client=None
) -> tuple[dict | None, str | None]:

    snomed_id      = candidate.get("snomed_id", "")
    preferred_term = candidate.get("preferred_term", "")
    source         = candidate.get("source", "snomed_search")
    score          = 0.0

    if any(excl.lower() in preferred_term.lower()
           for excl in explicit_exclusions):
        print(f"[validator] EXCLUDED: {snomed_id} '{preferred_term}'")
        return None, None

    if concept_type == "diagnosis" and source.startswith("relationship_"):
        score += CONFIDENCE_WEIGHTS["finding_not_disorder"]

    found_in_names = []
    is_nhsd = is_trud = is_qof = False

    # only hit MCP if client available
    lookup_tool = relations_tool = None
    if client:
        tools          = await client.get_tools()
        lookup_tool    = next((t for t in tools if t.name == "lookup_code_in_codelists"), None)
        relations_tool = next((t for t in tools if t.name == "get_relationships"), None)

    for codelist in all_codelists:
        layer = codelist.get("discovery_layer", "opencodelists")

        if layer == "trud":
            members = codelist.get("members", set())
            in_members = snomed_id in members
            print(f"[DEBUG] candidate id : '{snomed_id}'")
            print(f"[DEBUG] sample members: {list(members)[:3]}")
            print(f"[DEBUG] in_members: {in_members}")
            if in_members:
                found_in_names.append(codelist["name"])
                is_trud = True
                if "nhs digital" in codelist.get("organisation", "").lower():
                    is_nhsd = True

        elif layer == "opencodelists":
            members = codelist.get("members", set())
            if snomed_id in members:
                found_in_names.append(codelist["name"])
                org  = codelist.get("organisation", "").lower()
                name = codelist.get("name", "").lower()
                if any(t in org for t in ["nhsd", "nhs digital", "primary care domain"]):
                    is_nhsd = True
                if any(t in name for t in ["qof", "quality and outcomes",
                                            "business rules", "register"]):
                    is_qof = True

    found_count = len(found_in_names)

    if is_qof:
        score += CONFIDENCE_WEIGHTS["found_in_qof_register"]
    elif is_nhsd:
        score += CONFIDENCE_WEIGHTS["found_in_nhsd_refset"]
    elif is_trud:
        score += CONFIDENCE_WEIGHTS["found_in_trud_refset"]
    elif found_count >= 1:
        score += CONFIDENCE_WEIGHTS["found_in_one_codelist"]

    # ── Multi-codelist bonus (independent of type) ──
    if found_count >= 3:
        score += 0.20
    elif found_count == 2:
        score += 0.10

    # ── Semantic match to primary_condition ──
    term_words      = set(preferred_term.lower().split())
    condition_words = set(primary_condition.lower().split())
    overlap = len(term_words & condition_words) / max(len(condition_words), 1)
    if overlap >= 0.8:
        score += 0.20
    elif overlap >= 0.5:
        score += 0.10
    
    
    '''
    if expected_course != "either" and relations_tool:
        try:
            course_result = await relations_tool.ainvoke({
                "concept_id":        snomed_id,
                "relationship_type": "clinical_course"
            })
            for rel in course_result:
                target = rel.get("target_term", "").lower()
                actual = ("chronic" if "chronic" in target
                          else "acute" if "acute" in target
                          else None)
                if actual:
                    if actual == expected_course:
                        score += CONFIDENCE_WEIGHTS["clinical_course_matches"]
                    else:
                        score += CONFIDENCE_WEIGHTS["clinical_course_mismatch"]
        except Exception:
            pass
'''
    if expected_course != "either":
        term_lower = preferred_term.lower()
        actual_course = (
            "chronic" if any(w in term_lower for w in
                            ["chronic", "permanent", "persistent",
                            "paroxysmal", "controlled", "stable"])
            else "acute"  if any(w in term_lower for w in
                            ["acute", "decompensated", "emergency", "crisis"])
            else None
        )
        if actual_course:
            if actual_course == expected_course:
                score += CONFIDENCE_WEIGHTS["clinical_course_matches"]
            else:
                score += CONFIDENCE_WEIGHTS["clinical_course_mismatch"]

    confidence = min(max(round(score, 2), 0.0), 1.0)

    if confidence < TIER_THRESHOLDS["exclude"]:
        print(f"[validator] LOW CONFIDENCE ({confidence:.2f}): "
              f"{snomed_id} '{preferred_term}'")
        return None, snomed_id

    validated = {
        "snomed_id":           snomed_id,
        "preferred_term":      preferred_term,
        "confidence_score":    confidence,
        "opencodelists_match": found_count > 0,
        "qof_match":           is_qof,       # ← fixed
        "semantic_score":      0.0,
        "found_in_codelists":  found_in_names,
        "is_nhsd_refset":      is_nhsd,
        "found_count":         found_count
    }

    tier = ("tier_1" if confidence >= 0.70 else
            "tier_2" if confidence >= 0.45 else "tier_3")
    print(f"[validator] {tier.upper()} ({confidence:.2f}): "
          f"{snomed_id} '{preferred_term}' [found in {found_count} codelists]")

    return validated, None

# ===================================================================
# MAIN NODE FUNCTION
# ===================================================================
def _infer_expected_course(research_question: str) -> str:
    q = research_question.lower()
    if any(s in q for s in ["chronic", "long-term", "stable",
                             "eligible", "register", "established"]):
        return "chronic"
    if any(s in q for s in ["acute", "emergency", "admission",
                             "exacerbation", "episode"]):
        return "acute"
    return "either"


async def validator_node(state: NICEState) -> dict:

    candidate_codes     = state.get("candidate_codes", [])
    primary_condition   = state.get("primary_condition", "")
    research_question   = state.get("research_question", "")
    explicit_exclusions = state.get("explicit_exclusions", [])
    concept_type        = state.get("concept_type", "diagnosis")
    search_terms        = state.get("search_terms", [])
    iteration_count     = state.get("iteration_count", 0)
    
    expected_course     = _infer_expected_course(research_question)

    validated_codes:    list[ValidatedCode] = []
    low_confidence_ids: list[str]           = []

    print(f"\n[validator] ── Starting validation ──")
    print(f"[validator] Condition  : {primary_condition}")
    print(f"[validator] Candidates : {len(candidate_codes)}")
    print(f"[validator] Exp. course: {expected_course}")
    print(f"[validator] Iteration  : {iteration_count}")

    # ── Layer 1: OpenCodelists (direct HTTP, no MCP) ────────────────
    l1_codelists = _layer1_opencodelists(primary_condition, search_terms)

    # ── Layer 2: TRUD (local dict, no MCP) ─────────────────────────
    l2_codelists = _layer2_trud(primary_condition, search_terms)

    all_codelists = l1_codelists + l2_codelists

    # ── Layer 3: Flag if nothing found ──────────────────────────────
    extra_state_updates = _layer3_flag_if_empty(all_codelists, primary_condition)

    # ── Validate each candidate ─────────────────────────────────────
    for candidate in candidate_codes:
        validated, low_conf_id = await _validate_single_code(
            candidate=candidate,
            all_codelists=all_codelists,
            primary_condition=primary_condition,
            expected_course=expected_course,
            concept_type=concept_type,
            explicit_exclusions=explicit_exclusions,
            client=None   # SNOMED relations disabled until API key arrives
        )
        if validated:
            validated_codes.append(validated)
        elif low_conf_id:
            low_confidence_ids.append(low_conf_id)

    # ── Routing ─────────────────────────────────────────────────────
    routing = "loop_back" if low_confidence_ids and iteration_count < 3 else "proceed"

    t1 = sum(1 for v in validated_codes if v["confidence_score"] >= 0.70)
    t2 = sum(1 for v in validated_codes if 0.45 <= v["confidence_score"] < 0.70)
    t3 = sum(1 for v in validated_codes if v["confidence_score"] < 0.45)

    print(f"\n[validator] ── Complete ──")
    print(f"[validator] Routing : {routing}")
    print(f"[validator] Tiers   : T1={t1}  T2={t2}  T3={t3}  Low/excl={len(low_confidence_ids)}")

    return {
        "validated_codes":      validated_codes,
        "low_confidence_codes": low_confidence_ids,
        "iteration_count":      iteration_count + 1,
        "routing_decision":     routing,
        **extra_state_updates
    }