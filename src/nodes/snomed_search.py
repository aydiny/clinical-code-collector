"""
Node 2: SNOMED Concept Search

For each search_term from Node 1:
  1. search_snomed()    — text match within concept_type hierarchy
  2. get_descendants()  — IS-A subtree expansion per hit

Produces a flat, deduplicated candidate_codes[ ] list for Node 3.
No LLM — pure MCP tool calls only.
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from langchain_mcp_adapters.client import MultiServerMCPClient
from src.state import NICEState


# Max candidates to retrieve per search term — keeps Node 3 workload bounded
MAX_RESULTS_PER_TERM = 15
# Max descendants to expand per concept hit
MAX_DESCENDANTS      = 30


async def snomed_search_node(state: NICEState) -> dict:
    """
    Node 2: SNOMED Concept Search.

    Input state fields used:
        search_terms[ ]        — expanded list from Node 1 + Node 1b
        concept_type           — scopes search to correct SNOMED hierarchy
        explicit_exclusions[ ] — filters out wrong codes early

    Output state fields added:
        candidate_codes[ ]     — flat deduplicated list of
                                 {snomed_id, preferred_term, parent_id, source}
    """
    search_terms        = state.get("search_terms", [])
    concept_type        = state.get("concept_type", "diagnosis")
    explicit_exclusions = state.get("explicit_exclusions", [])

    if not search_terms:
        print("[snomed_search] WARNING: No search_terms in state — skipping")
        return {"candidate_codes": []}

    print(f"[snomed_search] Searching {len(search_terms)} terms | "
          f"concept_type: {concept_type}")

    all_candidates = {}   # snomed_id → record — dict for deduplication

    try:
        async with MultiServerMCPClient({
            "snomed": {
                "command": "python",
                "args": ["tools/snomed_mcp.py"],
                "transport": "stdio"
            }
        }) as client:

            tools = client.get_tools()
            search_tool     = next((t for t in tools if t.name == "search_snomed"), None)
            descendants_tool= next((t for t in tools if t.name == "get_descendants"), None)

            if not search_tool or not descendants_tool:
                print("[snomed_search] ERROR: Required MCP tools not found")
                return {"candidate_codes": []}

            for term in search_terms:
                print(f"[snomed_search] Searching: '{term}'")

                # ── Step 1: Text search within concept_type hierarchy ──────
                search_results = await search_tool.ainvoke({
                    "term":         term,
                    "concept_type": concept_type,
                    "max_results":  MAX_RESULTS_PER_TERM
                })

                if not search_results or "error" in search_results[0]:
                    print(f"[snomed_search] No results or error for '{term}' — skipping")
                    continue

                # ── Step 2: Expand each hit with IS-A descendants ──────────
                for hit in search_results:
                    concept_id     = hit.get("snomed_id")
                    preferred_term = hit.get("preferred_term", "")

                    if not concept_id:
                        continue

                    # Filter exclusions at candidate stage
                    if _matches_exclusion(preferred_term, explicit_exclusions):
                        print(f"[snomed_search] Excluded: '{preferred_term}'")
                        continue

                    # Add the direct search hit
                    if concept_id not in all_candidates:
                        all_candidates[concept_id] = {
                            "snomed_id":      concept_id,
                            "preferred_term": preferred_term,
                            "parent_id":      None,
                            "source":         "snomed_search"
                        }

                    # Expand descendants
                    descendants = await descendants_tool.ainvoke({
                        "concept_id":  concept_id,
                        "max_results": MAX_DESCENDANTS
                    })

                    if not descendants or "error" in descendants[0]:
                        continue

                    for desc in descendants:
                        desc_id   = desc.get("snomed_id")
                        desc_term = desc.get("preferred_term", "")

                        if not desc_id:
                            continue

                        if _matches_exclusion(desc_term, explicit_exclusions):
                            print(f"[snomed_search] Excluded descendant: '{desc_term}'")
                            continue

                        # Only add if not already found via another search term
                        if desc_id not in all_candidates:
                            all_candidates[desc_id] = {
                                "snomed_id":      desc_id,
                                "preferred_term": desc_term,
                                "parent_id":      concept_id,
                                "source":         "snomed_hierarchy"
                            }

    except Exception as e:
        print(f"[snomed_search] ERROR: MCP client failed: {e}")
        return {"candidate_codes": []}

    candidate_list = list(all_candidates.values())

    print(f"[snomed_search] ── Complete ──")
    print(f"[snomed_search] Candidate codes found : {len(candidate_list)}")
    print(f"[snomed_search] From text search      : "
          f"{sum(1 for c in candidate_list if c['source'] == 'snomed_search')}")
    print(f"[snomed_search] From hierarchy         : "
          f"{sum(1 for c in candidate_list if c['source'] == 'snomed_hierarchy')}")

    return {"candidate_codes": candidate_list}


def _matches_exclusion(term: str, exclusions: list[str]) -> bool:
    """
    Returns True if term matches any exclusion phrase (case-insensitive substring).
    e.g. "acute heart failure" matches exclusion "acute heart failure"
    """
    term_lower = term.lower()
    return any(excl.lower() in term_lower for excl in exclusions if excl)
