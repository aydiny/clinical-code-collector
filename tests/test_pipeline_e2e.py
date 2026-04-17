# tests/test_pipeline_e2e.py
"""
End-to-End Pipeline Test — Nodes 1 → 2 → 3
Runs a real research question through all three nodes
and prints a scored codelist at the end.
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from src.nodes.query_understanding import query_understanding_node
from src.nodes.snomed_search       import snomed_search_node
from src.nodes.validator           import validator_node

from dotenv import load_dotenv

# ── Research question — change this to test different conditions ──
RESEARCH_QUESTION = (
    "Identify all patients with heart failure with reduced ejection fraction "
    "(HFrEF) suitable for SGLT2 inhibitor therapy review in primary care"
)

async def main():
    print("\n" + "="*65)
    print("  END-TO-END PIPELINE TEST — Nodes 1 → 2 → 3")
    print("="*65)
    print(f"\n  Research question:\n  {RESEARCH_QUESTION}\n")

    # ── Initial state ─────────────────────────────────────────────
    state = {"research_question": RESEARCH_QUESTION}

    # ════════════════════════════════════════════════════════════════
    # NODE 1 — Query Understanding
    # ════════════════════════════════════════════════════════════════
    print("\n" + "─"*65)
    print("  NODE 1 — Query Understanding + Synonym Enrichment")
    print("─"*65)

    node1_out = await query_understanding_node(state)
    state.update(node1_out)

    print(f"\n  ✅ Node 1 complete")
    print(f"  Primary condition : {state['primary_condition']}")
    print(f"  Concept type      : {state['concept_type']}")
    print(f"  Exclusions - diagnosis        : {state['excluded_diagnoses']}")
    print(f"  Exclusions - medications        : {state['excluded_medications']}")
    print(f"  Exclusions - observations        : {state['excluded_observations']}")
    print(f"  Guidelines        : {state.get('relevant_guidelines', [])}")
    print(f"  Search terms ({len(state['search_terms'])})  :")
    for t in state["search_terms"]:
        print(f"    • {t}")

    # ════════════════════════════════════════════════════════════════
    # NODE 2 — SNOMED Search
    # ════════════════════════════════════════════════════════════════
    print("\n" + "─"*65)
    print("  NODE 2 — SNOMED Candidate Search")
    print("─"*65)

    node2_out = await snomed_search_node(state)
    state.update(node2_out)

    candidates = state.get("candidate_codes", [])
    print(f"\n  ✅ Node 2 complete")
    print(f"  Candidates found  : {len(candidates)}")
    print(f"  From text search  : {sum(1 for c in candidates if c['source'] == 'snomed_search')}")
    print(f"  From hierarchy    : {sum(1 for c in candidates if c['source'] == 'snomed_hierarchy')}")

    # ════════════════════════════════════════════════════════════════
    # NODE 3 — Validation + Scoring
    # ════════════════════════════════════════════════════════════════
    print("\n" + "─"*65)
    print("  NODE 3 — Validation + Scoring")
    print("─"*65)

    node3_out = await validator_node(state)
    state.update(node3_out)

    validated = state.get("validated_codes", [])

    # ── Sort by confidence score descending ──
    t1 = [v for v in validated if v["confidence_score"] >= 0.70]
    t2 = [v for v in validated if 0.45 <= v["confidence_score"] < 0.70]
    t3 = [v for v in validated if v["confidence_score"] < 0.45]

    # ════════════════════════════════════════════════════════════════
    # FINAL SCORED CODELIST
    # ════════════════════════════════════════════════════════════════
    print("\n" + "="*65)
    print("  FINAL SCORED CODELIST")
    print("="*65)

    print(f"\n  ── TIER 1 — High Confidence (≥0.70)  [{len(t1)} codes] ──")
    for v in sorted(t1, key=lambda x: x["confidence_score"], reverse=True):
        flags = _flags(v)
        print(f"  {v['confidence_score']:.2f}  {v['snomed_id']:20s}  "
              f"{v['preferred_term'][:45]:45s}  {flags}")

    print(f"\n  ── TIER 2 — Medium Confidence (0.45–0.69)  [{len(t2)} codes] ──")
    for v in sorted(t2, key=lambda x: x["confidence_score"], reverse=True):
        flags = _flags(v)
        print(f"  {v['confidence_score']:.2f}  {v['snomed_id']:20s}  "
              f"{v['preferred_term'][:45]:45s}  {flags}")

    if t3:
        print(f"\n  ── TIER 3 — Low Confidence (<0.45)  [{len(t3)} codes] ──")
        for v in sorted(t3, key=lambda x: x["confidence_score"], reverse=True):
            print(f"  {v['confidence_score']:.2f}  {v['snomed_id']:20s}  "
                  f"{v['preferred_term'][:45]}")

    print(f"\n  ── Summary ──")
    print(f"  T1 (include)     : {len(t1)}")
    print(f"  T2 (review)      : {len(t2)}")
    print(f"  T3 (exclude)     : {len(t3)}")
    print(f"  Human review flag: {state.get('human_review_flag', False)}")
    print(f"  Routing          : {state.get('routing_decision', '?')}")

    if state.get("ambiguity_notes"):
        print(f"\n  ⚠️  AMBIGUITY NOTE: {state['ambiguity_notes']}")


def _flags(v: dict) -> str:
    flags = []
    if v.get("qof_match"):       flags.append("QOF")
    if v.get("is_nhsd_refset"):  flags.append("NHSD")
    if v.get("found_count", 0) >= 3: flags.append(f"★{v['found_count']}lists")
    return " ".join(flags) if flags else ""


if __name__ == "__main__":
    asyncio.run(main())