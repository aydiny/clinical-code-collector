# src/nodes/snomed_search.py
import os
import httpx
import time
from dotenv import load_dotenv
from src.state import NICEState
from src.utils.fhir_client import CONCEPT_TYPE_ROOTS, FHIR_BASE, MAX_RESULTS_PER_TERM, MAX_DESCENDANTS, _get_headers

load_dotenv()

async def snomed_search_node(state: NICEState) -> dict:
    search_terms        = state.get("search_terms", [])
    concept_type        = state.get("concept_type", "diagnosis")
    explicit_exclusions = state.get("explicit_exclusions", [])

    if not search_terms:
        print("[snomed_search] WARNING: No search_terms — skipping")
        return {"candidate_codes": []}

    print(f"[snomed_search] Searching {len(search_terms)} terms | concept_type: {concept_type}")

    root_id        = CONCEPT_TYPE_ROOTS.get(concept_type, "404684003")
    all_candidates = {}

    async with httpx.AsyncClient(base_url=FHIR_BASE, timeout=15.0) as client:
        for term in search_terms:
            print(f"[snomed_search] Searching: '{term}'")

            # ── Step 1: Text search ───────────────────────────────────
            try:
                resp = await client.get("/ValueSet/$expand", headers=_get_headers(), params={
                    "url":    f"http://snomed.info/sct?fhir_vs=isa/{root_id}",
                    "filter": term,
                    "count":  MAX_RESULTS_PER_TERM
                })
                resp.raise_for_status()
                hits = resp.json().get("expansion", {}).get("contains", [])
            except Exception as e:
                print(f"[snomed_search] Search error for '{term}': {e}")
                continue

            for hit in hits:
                concept_id     = hit.get("code")
                preferred_term = hit.get("display", "")

                if not concept_id or _matches_exclusion(preferred_term, explicit_exclusions):
                    continue

                if concept_id not in all_candidates:
                    all_candidates[concept_id] = {
                        "snomed_id":      concept_id,
                        "preferred_term": preferred_term,
                        "parent_id":      None,
                        "source":         "snomed_search"
                    }

                # ── Step 2: ECL expansion ─────────────────────────────
                try:
                    ecl_resp = await client.get("/ValueSet/$expand", headers=_get_headers(), params={
                        "url":   f"http://snomed.info/sct?fhir_vs=ecl/%3C%3C%20{concept_id}",
                        "count": MAX_DESCENDANTS
                    })
                    ecl_resp.raise_for_status()
                    descendants = ecl_resp.json().get("expansion", {}).get("contains", [])
                except Exception as e:
                    print(f"[snomed_search] ECL error for {concept_id}: {e}")
                    continue

                for desc in descendants:
                    desc_id   = desc.get("code")
                    desc_term = desc.get("display", "")
                    if desc_id and desc_id not in all_candidates \
                       and not _matches_exclusion(desc_term, explicit_exclusions):
                        all_candidates[desc_id] = {
                            "snomed_id":      desc_id,
                            "preferred_term": desc_term,
                            "parent_id":      concept_id,
                            "source":         "snomed_hierarchy"
                        }

    candidate_list = list(all_candidates.values())
    print(f"[snomed_search] ── Complete ──")
    print(f"[snomed_search] Candidate codes found : {len(candidate_list)}")
    print(f"[snomed_search] From text search      : "
          f"{sum(1 for c in candidate_list if c['source'] == 'snomed_search')}")
    print(f"[snomed_search] From hierarchy        : "
          f"{sum(1 for c in candidate_list if c['source'] == 'snomed_hierarchy')}")
    return {"candidate_codes": candidate_list}


def _matches_exclusion(term: str, exclusions: list[str]) -> bool:
    term_lower = term.lower()
    return any(excl.lower() in term_lower for excl in exclusions if excl)