# tests/test_node2_search.py
"""
Node 2 Test Suite — SNOMED Search (FHIR API)
Tests search_snomed + get_descendants via snomed_mcp.py
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from src.nodes.snomed_search import snomed_search_node

# ── Test Cases ──────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "name": "TC2_T2DM",
        "state": {
            "search_terms":        ['Type 2 diabetes', 'Type II diabetes', 'Type-2 diabetes', 'Diabetes mellitus type 2', 'Non-insulin dependent diabetes mellitus', 'NIDDM', 'Amyotrophy due to type 2 diabetes mellitus', 'Diabetes type 2 with amyotrophy', 'Diabetes type II with amyotrophy', 'Lumbosacral radiculoplexus neuropathy due to type 2 diabetes mellitus', 'Lumbosacral radiculoplexus neuropathy due to type 2 diabetes mellitus (disorder)', 'Lumbosacral radiculoplexus neuropathy with type 2 diabetes mellitus', 'Diabetes type 2 with ketoacidosis', 'Ketoacidosis due to type 2 diabetes mellitus', 'Ketoacidosis due to type 2 diabetes mellitus (disorder)', 'Ketoacidosis in type 2 diabetes mellitus', 'Ketoacidosis in type II diabetes mellitus', 'Type 2 diabetes mellitus with ulcer', 'Type II diabetes mellitus with ulcer', 'Type II diabetes mellitus with ulcer (disorder)']  ,
            "concept_type":        "diagnosis",
            "explicit_exclusions": ["type 1", "gestational"],
        },
        "expect_present":  ["44054006", "445353002"],
        "expect_absent":   ["46635009"],                 # T1DM must NOT appear
        "min_candidates":  5,
    },

]

# ── Runner ───────────────────────────────────────────────────────────────────
async def run_test(tc: dict) -> dict:
    print(f"\n{'='*65}")
    print(f"  {tc['name']}")
    print(f"{'='*65}")

    result   = await snomed_search_node(tc["state"])
    candidates = result.get("candidate_codes", [])
    found_ids  = {c["snomed_id"] for c in candidates}

    # ── Checks ───────────────────────────────────────────────────────────
    passes = []
    failures = []

    # 1. Minimum candidate count
    if len(candidates) >= tc["min_candidates"]:
        passes.append(f"  ✅ Found {len(candidates)} candidates (≥{tc['min_candidates']})")
    else:
        failures.append(f"  ❌ Only {len(candidates)} candidates (need ≥{tc['min_candidates']})")

    # 2. Expected codes present
    for code in tc["expect_present"]:
        term = next((c["preferred_term"] for c in candidates if c["snomed_id"] == code), "?")
        if code in found_ids:
            passes.append(f"  ✅ PRESENT   {code:20s} {term}")
        else:
            failures.append(f"  ❌ MISSING   {code:20s} (expected in results)")

    # 3. Excluded codes absent
    for code in tc["expect_absent"]:
        term = next((c["preferred_term"] for c in candidates if c["snomed_id"] == code), "?")
        if code not in found_ids:
            passes.append(f"  ✅ ABSENT    {code:20s} (correctly excluded)")
        else:
            failures.append(f"  ⚠️  PRESENT   {code:20s} {term} — should be excluded")

    # ── Print results ─────────────────────────────────────────────────────
    print(f"\n  Candidates : {len(candidates)}")
    print(f"  From search: {sum(1 for c in candidates if c['source'] == 'snomed_search')}")
    print(f"  From hier  : {sum(1 for c in candidates if c['source'] == 'snomed_hierarchy')}")
    print()
    for p in passes:   print(p)
    for f in failures: print(f)

    # ── Sample output ─────────────────────────────────────────────────────
    print(f"\n  Sample candidates:")
    for c in candidates[:8]:
        src = "S" if c["source"] == "snomed_search" else "H"
        print(f"  [{src}] {c['snomed_id']:20s} {c['preferred_term'][:55]}")
    if len(candidates) > 8:
        print(f"  ... and {len(candidates)-8} more")

    passed = len(failures) == 0
    print(f"\n  Result: {'✅ ALL CHECKS PASSED' if passed else f'❌ {len(failures)} check(s) failed'}")
    return {"name": tc["name"], "passed": passed,
            "candidates": len(candidates), "failures": failures}


async def main():
    print("\n" + "="*65)
    print("  NODE 2 TEST SUITE — SNOMED Search")
    print("="*65)

    summary = []
    for tc in TEST_CASES:
        r = await run_test(tc)
        summary.append(r)

    print(f"\n{'='*65}")
    print("  OVERALL SUMMARY")
    print(f"{'='*65}")
    for r in summary:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  {status}  {r['name']:15s}  {r['candidates']} candidates")
        for f in r["failures"]:
            print(f"         {f.strip()}")

    total  = len(summary)
    passed = sum(1 for r in summary if r["passed"])
    print(f"\n  Total: {passed}/{total} test cases passed")


if __name__ == "__main__":
    asyncio.run(main())