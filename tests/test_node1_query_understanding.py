"""
Standalone test for Node 1 + Node 1b: Query Understanding + Synonym Enrichment

Runs WITHOUT:
  - Full LangGraph graph
  - Node 2, 3, 4, 5
  - OpenCodelists / TRUD MCP tools

Runs WITH:
  - GPT-4o (real call — needs OPENAI_API_KEY)
  - snomed_mcp.py (real call — needs NHS Terminology Server)
  - RAG retriever (graceful skip if vector store not built yet)

Usage:
  python tests/test_node1_query_understanding.py
"""
import asyncio
import json
import os
import sys
import time
import traceback
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.query_understanding import query_understanding_node

# ── Test Cases ────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": "TC1",
        "label": "HFrEF — SGLT2 eligibility (primary test)",
        "research_question": (
            "Identify patients with heart failure with reduced ejection "
            "fraction (HFrEF) who may be eligible for SGLT2 inhibitor "
            "therapy per NICE NG106"
        ),
        "expect": {
            "primary_condition_contains":       "ejection fraction",
            "concept_type":                     "diagnosis",
            "snomed_top_hierarchy":             "Clinical Finding",
            "exclusions_must_contain":          ["HFpEF", "preserved"],
            "guidelines_must_contain":          ["NG106"],
            "min_search_terms":                 6,
        }
    },
    {
        "id": "TC2",
        "label": "Ambiguous cohort — tests ambiguity_notes",
        "research_question": (
            "Elderly patients with heart failure"
        ),
        "expect": {
            "primary_condition_contains":       "heart failure",
            "concept_type":                     "diagnosis",
            "ambiguity_notes_not_empty":        True,    # should flag "elderly" + HF type
            "min_search_terms":                 4,
        }
    },
    {
        "id": "TC3",
        "label": "Mixed cohort — diagnosis + lab result",
        "research_question": (
            "Patients with type 2 diabetes and HbA1c above 58 mmol/mol "
            "not currently on SGLT2 inhibitor therapy"
        ),
        "expect": {
            "primary_condition_contains":       "diabetes",
            "concept_type":                     "mixed",
            "exclusions_must_contain":          ["type 1"],
            "min_search_terms":                 5,
        }
    }
]


# ── Validation Helpers ────────────────────────────────────────────
def validate_output(result: dict, expect: dict, test_id: str) -> list[str]:
    """
    Check result against expectations.
    Returns list of failure messages (empty = all passed).
    """
    failures = []

    # primary_condition
    if "primary_condition_contains" in expect:
        keyword = expect["primary_condition_contains"]
        if keyword.lower() not in result.get("primary_condition", "").lower():
            failures.append(
                f"primary_condition '{result.get('primary_condition')}' "
                f"does not contain '{keyword}'"
            )

    # concept_type
    if "concept_type" in expect:
        if result.get("concept_type") != expect["concept_type"]:
            failures.append(
                f"concept_type: expected '{expect['concept_type']}', "
                f"got '{result.get('concept_type')}'"
            )

    # snomed_top_hierarchy
    if "snomed_top_hierarchy" in expect:
        if result.get("snomed_top_hierarchy") != expect["snomed_top_hierarchy"]:
            failures.append(
                f"snomed_top_hierarchy: expected '{expect['snomed_top_hierarchy']}', "
                f"got '{result.get('snomed_top_hierarchy')}'"
            )

    # explicit_exclusions
    if "exclusions_must_contain" in expect:
        exclusions_text = " ".join(result.get("explicit_exclusions", [])).lower()
        for keyword in expect["exclusions_must_contain"]:
            if keyword.lower() not in exclusions_text:
                failures.append(
                    f"explicit_exclusions missing keyword '{keyword}'. "
                    f"Got: {result.get('explicit_exclusions')}"
                )

    # relevant_guidelines
    if "guidelines_must_contain" in expect:
        guidelines_text = " ".join(result.get("relevant_guidelines", [])).lower()
        for keyword in expect["guidelines_must_contain"]:
            if keyword.lower() not in guidelines_text:
                failures.append(
                    f"relevant_guidelines missing '{keyword}'. "
                    f"Got: {result.get('relevant_guidelines')}"
                )

    # search_terms count
    if "min_search_terms" in expect:
        count = len(result.get("search_terms", []))
        if count < expect["min_search_terms"]:
            failures.append(
                f"search_terms: expected ≥{expect['min_search_terms']}, "
                f"got {count}"
            )

    # ambiguity_notes
    if expect.get("ambiguity_notes_not_empty"):
        if not result.get("ambiguity_notes", "").strip():
            failures.append("ambiguity_notes: expected non-empty, got empty string")

    return failures


def print_result(result: dict):
    """Print Node 1 output in readable format."""
    print(f"\n  primary_condition   : {result.get('primary_condition')}")
    print(f"  concept_type        : {result.get('concept_type')}")
    print(f"  snomed_top_hierarchy: {result.get('snomed_top_hierarchy')}")
    print(f"  relevant_guidelines : {result.get('relevant_guidelines')}")
    print(f"  explicit_exclusions : {result.get('explicit_exclusions')}")
    print(f"  validation_sources  : {result.get('suggested_validation_sources')}")
    print(f"  search_terms ({len(result.get('search_terms', []))}) : "
          f"{result.get('search_terms')}")
    if result.get("ambiguity_notes"):
        print(f"  ⚠️  ambiguity_notes  : {result.get('ambiguity_notes')}")


# ── Main Test Runner ──────────────────────────────────────────────
async def run_tests():
    print("=" * 65)
    print("  NODE 1 TEST SUITE — Query Understanding + Synonym Enrichment")
    print("=" * 65)

    # #region agent log (debug-1d1a0d)
    _dbg("A", "tests/test_node1_query_understanding.py:run_tests", "runtime context", {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "cwd": os.getcwd(),
        "project_root": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sys_path_head": sys.path[:5],
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "vectorstore_exists": os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "vectorstore", "nice_guidelines")),
    })
    # #endregion

    passed  = 0
    failed  = 0
    skipped = 0
    results = []

    for tc in TEST_CASES:
        print(f"\n{'─' * 65}")
        print(f"[{tc['id']}] {tc['label']}")
        print(f"  Question: {tc['research_question'][:70]}...")
        print()

        try:
            # Build minimal state — only research_question needed for Node 1
            initial_state = {
                "research_question": tc["research_question"]
            }

            # #region agent log (debug-1d1a0d)
            _dbg("B", "tests/test_node1_query_understanding.py:loop", "starting test case", {
                "test_id": tc.get("id"),
                "label": tc.get("label"),
                "question_preview": (tc.get("research_question") or "")[:120],
            })
            # #endregion

            result = await query_understanding_node(initial_state)

            # Print what Node 1 produced
            print_result(result)

            # Validate against expectations
            failures = validate_output(result, tc["expect"], tc["id"])

            if failures:
                print(f"\n  ❌ FAILED — {len(failures)} assertion(s):")
                for f in failures:
                    print(f"     • {f}")
                failed += 1
                results.append({"id": tc["id"], "status": "FAIL",
                                 "failures": failures})
            else:
                print(f"\n  ✅ PASSED")
                passed += 1
                results.append({"id": tc["id"], "status": "PASS"})

        except Exception as e:
            print(f"\n  💥 ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            # #region agent log (debug-1d1a0d)
            _dbg("C", "tests/test_node1_query_understanding.py:except", "test case raised exception", {
                "test_id": tc.get("id"),
                "exc_type": type(e).__name__,
                "exc_message": str(e),
                "traceback": traceback.format_exc()[-2000:],
            })
            # #endregion
            skipped += 1
            results.append({"id": tc["id"], "status": "ERROR", "error": str(e)})

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print(f"  RESULTS: ✅ {passed} passed  ❌ {failed} failed  "
          f"💥 {skipped} errors")
    print(f"{'=' * 65}\n")

    # Save results to file for review
    with open("tests/node1_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("  Results saved to tests/node1_test_results.json")

    return failed + skipped == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
