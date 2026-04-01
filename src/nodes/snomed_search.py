# src/nodes/snomed_search.py
import os
import httpx
import asyncio
from dotenv import load_dotenv
from src.state import NICEState
from src.utils.fhir_client import CONCEPT_TYPE_ROOTS, FHIR_BASE, MAX_RESULTS_PER_TERM, MAX_DESCENDANTS, _get_headers

load_dotenv()

async def snomed_search_node(state: NICEState) -> dict:
    """
    Node 2: Symmetric SNOMED CT Search.
    Searches Diagnoses, Medications, and Observations in parallel.
    Applies ONLY the exclusions strictly relevant to that category.
    """
    
    # ── THE SYMMETRIC ARCHITECTURE ──
    # We map the inclusion terms to their specific SNOMED hierarchy,
    # and pair them exclusively with their corresponding exclusion bucket.
    search_tasks = [
        {
            "category": "Diagnosis", 
            "root_id": "404684003", # Clinical Finding
            "terms": state.get("search_terms", []),
            "exclusions": state.get("excluded_diagnoses", [])
        },
        {
            "category": "Medication", 
            "root_id": "105590001", # Pharmaceutical / biologic product
            "terms": state.get("relevant_medications", []),
            "exclusions": state.get("excluded_medications", [])
        },
        {
            "category": "Observation", 
            "root_id": "363787002", # Observable Entity
            "terms": state.get("relevant_observations", []),
            "exclusions": state.get("excluded_observations", [])
        }
    ]
    
    all_candidates = {}

    async with httpx.AsyncClient(base_url=FHIR_BASE, timeout=15.0) as client:
        for task in search_tasks:
            category = task["category"]
            root_id = task["root_id"]
            exclusions = task["exclusions"] # Grab the specific exclusions for this loop
            
            for term in task["terms"]:
                if not term.strip():
                    continue # Skip empty strings
                    
                print(f"[snomed_search] Searching {category}: '{term}'")
                
                # ── Text Search via NHS Terminology Server ──
                try:
                    resp = await client.get("/ValueSet/$expand", headers=_get_headers(), params={
                        "url": f"http://snomed.info/sct?fhir_vs=isa/{root_id}",
                        "filter": term,
                        "count": MAX_RESULTS_PER_TERM
                    })
                    resp.raise_for_status()
                    hits = resp.json().get("expansion", {}).get("contains", [])
                except Exception as e:
                    print(f"[snomed_search] ⚠️ Search error for '{term}': {e}")
                    continue

                for hit in hits:
                    concept_id = hit.get("code")
                    preferred_term = hit.get("display", "")
                    
                    # ── THE FIX ──
                    # Filter against the local 'exclusions' list for this specific category
                    if not concept_id or _matches_exclusion(preferred_term, exclusions):
                        continue
                        
                    # Add to candidate list if it passes the filter and isn't a duplicate
                    if concept_id not in all_candidates:
                        all_candidates[concept_id] = {
                            "snomed_id": concept_id,
                            "preferred_term": preferred_term,
                            "parent_id": None, # Will be populated by Node 3 if needed
                            "source": "snomed_search",
                            "category": category  # Tag the code with its clinical type
                        }

    candidate_list = list(all_candidates.values())
    
    # --- DEBUG LOGGING ---
    print(f"\n[snomed_search] ── Complete ──")
    print(f"[snomed_search] Total candidate codes found: {len(candidate_list)}")
    # Count how many of each category we found
    cat_counts = {}
    for c in candidate_list:
        cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1
    print(f"[snomed_search] Breakdown: {cat_counts}\n")
    # ---------------------
    
    return {"candidate_codes": candidate_list}

def _matches_exclusion(term: str, exclusions: list[str]) -> bool:
    """Helper to check if a SNOMED term contains any of the excluded strings."""
    if not exclusions:
        return False
        
    term_lower = term.lower()
    return any(excl.lower() in term_lower for excl in exclusions if excl.strip())