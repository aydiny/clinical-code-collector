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

# -------------------------------------------------------------------
# UNIVERSAL Confidence Weights — condition-agnostic
# -------------------------------------------------------------------
CONFIDENCE_WEIGHTS = {
    "found_in_nhsd_refset":         +0.50,
    "found_in_qof_register":        +0.45,   # QOF-specific signal
    "found_in_trud_refset":         +0.40,  # slightly lower — local copy may lag
    "found_in_multiple_codelists":  +0.55,
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
async def _layer1_opencodelists(
    client,
    suggested_sources: list[str],
    primary_condition: str
) -> list[dict]:
    """
    Layer 1: Search OpenCodelists API dynamically.
    Uses suggested_validation_sources from Node 1 as search queries.
    """
    tools = client.get_tools()
    search_tool = next(
        (t for t in tools if t.name == "search_codelists"), None
    )
    if not search_tool:
        print("[validator:L1] search_codelists tool unavailable")
        return []

    queries = list(dict.fromkeys(
        (suggested_sources or []) + [primary_condition]
    ))[:5]

    tasks = [search_tool.ainvoke({"condition": q}) for q in queries]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    seen, codelists = set(), []
    for results in results_list:
        if isinstance(results, Exception):
            continue
        for cl in (results or []):
            cid = cl.get("codelist_id")
            if cid and cid not in seen:
                codelists.append({**cl, "discovery_layer": "opencodelists"})
                seen.add(cid)

    print(f"[validator:L1] Found {len(codelists)} codelists via OpenCodelists API")
    return codelists


# ===================================================================
# LAYER 2: TRUD Local Refset Index
# ===================================================================
async def _layer2_trud(
    client,
    primary_condition: str,
    search_terms: list[str]
) -> list[dict]:
    """
    Layer 2: Match against TRUD refset index using fuzzy keyword matching.
    Loads matched refsets from local TRUD data via trud_mcp.py tool.
    """
    tools = client.get_tools()
    trud_tool = next(
        (t for t in tools if t.name == "get_refset_by_id"), None
    )
    if not trud_tool:
        print("[validator:L2] get_refset_by_id tool unavailable — "
              "is trud_mcp.py running?")
        return []

    # Match condition + all search terms against TRUD index
    all_text = " ".join([primary_condition] + search_terms)
    matches = fuzzy_match_trud(all_text)

    if not matches:
        print(f"[validator:L2] No TRUD refset match for '{primary_condition}'")
        return []

    print(f"[validator:L2] TRUD matches: "
          f"{[(kw, rid) for kw, rid in matches]}")

    # Load each matched refset
    trud_codelists = []
    for keyword, refset_id in matches:
        refset_members = await trud_tool.ainvoke({"refset_id": refset_id})
        if refset_members and "error" not in refset_members[0]:
            trud_codelists.append({
                "codelist_id":    f"trud/{refset_id}",
                "name":           f"TRUD Refset {refset_id} ({keyword})",
                "organisation":   "NHS Digital (TRUD)",
                "refset_id":      refset_id,
                "members":        {r["snomed_id"] for r in refset_members},
                "discovery_layer": "trud"
            })
            print(f"[validator:L2] Loaded TRUD refset {refset_id}: "
                  f"{len(refset_members)} members")

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
    client,
    candidate: dict,
    all_codelists: list[dict],
    primary_condition: str,
    expected_course: str,
    concept_type: str,
    explicit_exclusions: list[str]
) -> tuple[dict | None, str | None]:
    """
    Validate a single candidate code against all discovered codelists.
    Returns: (ValidatedCode, None) OR (None, snomed_id_for_low_confidence)
    """
    snomed_id      = candidate.get("snomed_id", "")
    preferred_term = candidate.get("preferred_term", "")
    source         = candidate.get("source", "snomed_search")
    score          = 0.0

    # --- Hard exclusion check ---
    if any(excl.lower() in preferred_term.lower()
           for excl in explicit_exclusions):
        print(f"[validator] EXCLUDED: {snomed_id} '{preferred_term}'")
        return None, None   # None, None = excluded entirely, not low-confidence

    # --- Structural penalty ---
    if concept_type == "diagnosis" and source.startswith("relationship_"):
        score += CONFIDENCE_WEIGHTS["finding_not_disorder"]

    # --- Check each codelist ---
    found_in_names = []
    is_nhsd = False
    is_trud = False
    is_qof = False

    tools = client.get_tools()
    lookup_tool = next(
        (t for t in tools if t.name == "lookup_code_in_codelists"), None
    )

    for codelist in all_codelists:
        layer = codelist.get("discovery_layer", "opencodelists")

        if layer == "trud":
            # TRUD: check local member set directly — no API call needed
            members = codelist.get("members", set())
            if snomed_id in members:
                found_in_names.append(codelist["name"])
                is_trud = True
                org = codelist.get("organisation", "").lower()
                if "nhs digital" in org:
                    is_nhsd = True

        elif layer == "opencodelists" and lookup_tool:
            result = await lookup_tool.ainvoke({
                "snomed_id": snomed_id,
                "condition": codelist.get("name", primary_condition)
            })
            if result.get("found"):
                found_in_names.append(codelist["name"])
                
                org  = codelist.get("organisation", "").lower()
                name = codelist.get("name", "").lower()

                # Check: is this an NHS Digital curated refset?
                if any(t in org for t in ["nhsd", "nhs digital", "primary care domain"]):
                    is_nhsd = True

                # ← NEW: Check if this is a QOF Business Rules codelist
                if any(t in name for t in ["qof", "quality and outcomes",
                                            "business rules", "register"]):
                    is_qof = True   # ← needs to be declared at top of function


    # --- Apply codelist scores ---
    found_count = len(found_in_names)

    if is_nhsd:
        score += CONFIDENCE_WEIGHTS["found_in_nhsd_refset"]
    elif is_qof:                                              # ← ADD THIS BLOCK
        score += CONFIDENCE_WEIGHTS["found_in_qof_register"]
    elif is_trud:
        score += CONFIDENCE_WEIGHTS["found_in_trud_refset"]
    elif found_count >= 2:
        score += CONFIDENCE_WEIGHTS["found_in_multiple_codelists"]
    elif found_count == 1:
        score += CONFIDENCE_WEIGHTS["found_in_one_codelist"]

    # --- Clinical course check ---
    if expected_course != "either":
        tools = client.get_tools()
        relations_tool = next(
            (t for t in tools if t.name == "get_relationships"), None
        )
        if relations_tool:
            try:
                course_result = await relations_tool.ainvoke({
                    "concept_id": snomed_id,
                    "relationship_type": "clinical_course"
                })
                for rel in course_result:
                    target = rel.get("target_term", "").lower()
                    if "chronic" in target:
                        actual = "chronic"
                    elif "acute" in target:
                        actual = "acute"
                    else:
                        continue
                    if actual == expected_course:
                        score += CONFIDENCE_WEIGHTS["clinical_course_matches"]
                    else:
                        score += CONFIDENCE_WEIGHTS["clinical_course_mismatch"]
                        print(f"[validator] COURSE MISMATCH: {snomed_id}")
            except Exception:
                pass

    # --- Final score ---
    confidence = min(max(round(score, 2), 0.0), 1.0)

    if confidence < TIER_THRESHOLDS["exclude"]:
        print(f"[validator] LOW CONFIDENCE ({confidence:.2f}): "
              f"{snomed_id} '{preferred_term}'")
        return None, snomed_id  # flag for re-search

    validated = {
        "snomed_id":            snomed_id,
        "preferred_term":       preferred_term,
        "confidence_score":     confidence,
        "opencodelists_match":  found_count > 0,
        "qof_match":            is_nhsd,
        "semantic_score":       0.0,
        "found_in_codelists":   found_in_names,
        "is_nhsd_refset":       is_nhsd,
        "found_count":          found_count
    }

    tier = ("tier_1" if confidence >= 0.70 else
            "tier_2" if confidence >= 0.45 else "tier_3")
    print(f"[validator] {tier.upper()} ({confidence:.2f}): "
          f"{snomed_id} '{preferred_term}' "
          f"[found in {found_count} codelists]")

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
    """
    Node 3: Three-layer dynamic codelist discovery + universal scoring.

    Layer 1: OpenCodelists API     — fully automatic
    Layer 2: TRUD refset index     — semi-automatic (index maintained manually)
    Layer 3: Human review flag     — catches everything else
    """
    candidate_codes     = state.get("candidate_codes", [])
    primary_condition   = state.get("primary_condition", "")
    research_question   = state.get("research_question", "")
    suggested_sources   = state.get("suggested_validation_sources", [])
    explicit_exclusions = state.get("explicit_exclusions", [])
    concept_type        = state.get("concept_type", "diagnosis")
    search_terms        = state.get("search_terms", [])
    iteration_count     = state.get("iteration_count", 0)

    expected_course = _infer_expected_course(research_question)
    extra_state_updates = {}

    validated_codes:    list[ValidatedCode] = []
    low_confidence_ids: list[str]           = []

    print(f"\n[validator] ── Starting validation ──")
    print(f"[validator] Condition  : {primary_condition}")
    print(f"[validator] Candidates : {len(candidate_codes)}")
    print(f"[validator] Exp. course: {expected_course}")
    print(f"[validator] Iteration  : {iteration_count}")

    try:
        async with MultiServerMCPClient({
            "opencodelists": {
                "command": "python",
                "args": ["tools/opencodelists_mcp.py"],
                "transport": "stdio"
            },
            "snomed": {
                "command": "python",
                "args": ["tools/snomed_mcp.py"],
                "transport": "stdio"
            },
            "trud": {
                "command": "python",
                "args": ["tools/trud_mcp.py"],
                "transport": "stdio"
            }
        }) as client:

            # ── Layer 1: OpenCodelists ──────────────────────────────
            l1_codelists = await _layer1_opencodelists(
                client, suggested_sources, primary_condition
            )

            # ── Layer 2: TRUD ───────────────────────────────────────
            l2_codelists = await _layer2_trud(
                client, primary_condition, search_terms
            )

            all_codelists = l1_codelists + l2_codelists

            # ── Layer 3: Flag if nothing found ─────────────────────
            extra_state_updates = _layer3_flag_if_empty(
                all_codelists, primary_condition
            )

            # ── Validate each candidate ────────────────────────────
            for candidate in candidate_codes:
                validated, low_conf_id = await _validate_single_code(
                    client=client,
                    candidate=candidate,
                    all_codelists=all_codelists,
                    primary_condition=primary_condition,
                    expected_course=expected_course,
                    concept_type=concept_type,
                    explicit_exclusions=explicit_exclusions
                )
                if validated:
                    validated_codes.append(validated)
                elif low_conf_id:
                    low_confidence_ids.append(low_conf_id)
                # None, None = hard excluded — silently dropped

    except Exception as e:
        print(f"[validator] MCP client error: {e}")
        validated_codes = [
            {
                "snomed_id":           c.get("snomed_id", ""),
                "preferred_term":      c.get("preferred_term", ""),
                "confidence_score":    0.0,
                "opencodelists_match": False,
                "qof_match":           False,
                "semantic_score":      0.0,
                "found_in_codelists":  [],
                "is_nhsd_refset":      False,
                "found_count":         0
            }
            for c in candidate_codes
        ]

    # ── Routing ────────────────────────────────────────────────────
    if low_confidence_ids and iteration_count < 3:
        routing = "loop_back"
    else:
        routing = "proceed"

    t1 = sum(1 for v in validated_codes if v["confidence_score"] >= 0.70)
    t2 = sum(1 for v in validated_codes if 0.45 <= v["confidence_score"] < 0.70)
    t3 = sum(1 for v in validated_codes if v["confidence_score"] < 0.45)

    print(f"\n[validator] ── Complete ──")
    print(f"[validator] Routing : {routing}")
    print(f"[validator] Tiers   : T1={t1}  T2={t2}  T3={t3}  "
          f"Low/excl={len(low_confidence_ids)}")

    return {
        "validated_codes":      validated_codes,
        "low_confidence_codes": low_confidence_ids,
        "iteration_count":      iteration_count + 1,
        "routing_decision":     routing,
        **extra_state_updates   # merges human_review_flag if Layer 3 fired
    }
