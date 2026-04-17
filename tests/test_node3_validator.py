# tests/test_node3_validator.py

"""
Node 3 Validation Test — injects seed codes directly, bypasses Node 2.
"""

import asyncio
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

import pandas as pd
from pathlib import Path
from src.nodes.validator import validator_node
from data.test_cases.seed_codes import get_all_codes, get_tc_codes


# ── Test case state templates ────────────────────────────────────────────────
TEST_CASE_STATES = {
    "TC1_HFrEF": {
        "research_question":            "Identify patients with heart failure with reduced ejection fraction (HFrEF) eligible for SGLT2 inhibitor therapy",
        "primary_condition":            "heart failure with reduced ejection fraction",
        "concept_type":                 "diagnosis",
        "search_terms":                 ["heart failure with reduced ejection fraction", "HFrEF", "systolic heart failure", "LVSD", "chronic heart failure"],
        "suggested_validation_sources": ["heart failure reduced ejection fraction", "HFrEF primary care register", "heart failure QOF"],
        "explicit_exclusions":          ["heart failure with preserved ejection fraction", "HFpEF", "acute heart failure"],
        "iteration_count":              0,
        "human_review_flag":            False,
        "human_feedback":               None,
        "final_output":                 None,
    },
    "TC2_T2DM": {
        "research_question":            "Identify patients with type 2 diabetes mellitus for QOF register review",
        "primary_condition":            "type 2 diabetes mellitus",
        "concept_type":                 "diagnosis",
        "search_terms":                 ["type 2 diabetes", "T2DM", "diabetes mellitus type 2", "non-insulin dependent diabetes"],
        "suggested_validation_sources": ["diabetes mellitus type 2", "T2DM QOF register", "diabetes primary care"],
        "explicit_exclusions":          ["type 1 diabetes", "gestational diabetes", "secondary diabetes"],
        "iteration_count":              0,
        "human_review_flag":            False,
        "human_feedback":               None,
        "final_output":                 None,
    },
    "TC3_AF": {
        "research_question":            "Identify patients with atrial fibrillation on the QOF AF register",
        "primary_condition":            "atrial fibrillation",
        "concept_type":                 "diagnosis",
        "search_terms":                 ["atrial fibrillation", "AF", "paroxysmal AF", "chronic AF", "permanent AF"],
        "suggested_validation_sources": ["atrial fibrillation QOF", "AF register", "atrial fibrillation primary care"],
        "explicit_exclusions":          ["atrial flutter", "supraventricular tachycardia"],
        "iteration_count":              0,
        "human_review_flag":            False,
        "human_feedback":               None,
        "final_output":                 None,
    }
}


def build_candidate_codes(tc_seeds: list[dict]) -> list[dict]:
    """Convert seed dicts into candidate_codes format expected by validator."""
    return [
        {
            "snomed_id":      seed["snomed_id"],
            "preferred_term": seed["term"],
            "source":         "seed_injection",
            "tier_hint":      seed["tier"],       # not used by validator — for test analysis only
        }
        for seed in tc_seeds
    ]


async def run_test_case(tc_name: str) -> dict:

    print(f"\n{'='*65}")
    print(f"  {tc_name}")
    print(f"{'='*65}")

    # ── Get seed codes from Python module ──────────────
    tc_seeds   = get_tc_codes(tc_name)           # list[dict]
    candidates = build_candidate_codes(tc_seeds)
    state      = {**TEST_CASE_STATES[tc_name], "candidate_codes": candidates}

    print(f"  Injecting {len(candidates)} seed codes into validator...")

    result    = await validator_node(state)

    # ── Analyse results vs expectations ──────────────────────────
    validated = result.get("validated_codes", [])
    val_ids   = {v["snomed_id"]: v for v in validated}

    passed, failed = 0, 0
    failures = []

    for seed in tc_seeds:
        sid   = seed["snomed_id"]
        tier  = seed["tier"]
        term  = seed["term"]
        val   = val_ids.get(sid)
        score = val["confidence_score"] if val else 0.0

        if tier == "GOLD" and score >= 0.70:
            passed += 1
            status = f"✅ PASS ({score:.2f})"

        elif tier == "EDGE" and score >= 0.25:
            passed += 1
            status = f"✅ PASS ({score:.2f})"

        elif tier == "TRAP" and val is not None:
            passed += 1
            status = f"⚠️  TRAP validated ({score:.2f}) — Node 4 must catch"

        elif val is None and tier in ("EDGE", "TRAP"):
            passed += 1
            status = f"✅ CORRECTLY excluded (score=0.00)"

        else:
            failed += 1
            status = f"❌ FAIL ({score:.2f})"
            failures.append(f"{sid} [{tier}]: {term[:40]}")

        print(f"  {tier:4s}  {sid:20s}  {term[:38]:38s}  {status}")

    print(f"\n  Result: {passed}/{len(tc_seeds)} passed")
    if failures:
        print("  Failures:")
        for f in failures:
            print(f"    • {f}")

    return {
        "test_case":            tc_name,
        "total":                len(tc_seeds),
        "passed":               passed,
        "failed":               failed,
        "routing":              result.get("routing_decision"),
        "t1":                   sum(1 for v in validated if v["confidence_score"] >= 0.70),
        "t2":                   sum(1 for v in validated if 0.45 <= v["confidence_score"] < 0.70),
        "t3":                   sum(1 for v in validated if v["confidence_score"] < 0.45),
        "human_review_flagged": result.get("human_review_flag", False)
    }


async def run_all():

    print("\n" + "="*65)
    print("  NODE 3 TEST SUITE — Validator (Seed Code Injection)")
    print("="*65)

    summary = []
    for tc_name in ["TC1_HFrEF", "TC2_T2DM", "TC3_AF"]:
        result = await run_test_case(tc_name)
        summary.append(result)

    # ── Overall summary ──────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  OVERALL SUMMARY")
    print(f"{'='*65}")

    total_passed = sum(r["passed"] for r in summary)
    total_codes  = sum(r["total"]  for r in summary)

    for r in summary:
        flag = " ⚠️  human review flagged" if r["human_review_flagged"] else ""
        print(f"  {r['test_case']:12s}  {r['passed']}/{r['total']} passed"
              f"  T1={r['t1']} T2={r['t2']} T3={r['t3']}{flag}")

    print(f"\n  Total: {total_passed}/{total_codes} passed")

    out = Path("tests/results/node3_summary.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary).to_csv(out, index=False)
    print(f"  Saved: {out}")


if __name__ == "__main__":
    asyncio.run(run_all())
