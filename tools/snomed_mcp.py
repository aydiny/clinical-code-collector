"""
MCP Tool Server — NHS Terminology Server (FHIR API)
Run standalone: python tools/snomed_mcp.py
"""
from mcp.server.fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("snomed-tool-server")

BASE_URL = "https://ontology.nhs.uk/production1/fhir"
HEADERS = {
    "apiKey": os.getenv("NHS_TERMINOLOGY_API_KEY", ""),
    "Accept": "application/json"
}

CONCEPT_TYPE_ROOTS = {
    # Node 1 concept_type  →  Official SNOMED top-level ID
    "diagnosis":    "64572001",    # Disease (disorder) — chronic conditions, QOF registers
    "finding":      "404684003",   # Clinical finding — observations, signs, normal states
    "observation":  "404684003",   # Clinical finding — same hierarchy
    "procedure":    "71388002",    # Procedure — operations, therapies, investigations
    "lab_result":   "363787002",   # Observable entity — HbA1c, eGFR, LVEF, BP
    "medication":   "373873005",   # Pharmaceutical/biologic product
    "demographic":  "48176007",    # Social context — age, ethnicity, deprivation
    "situation":    "243796009",   # Situation with explicit context — family history
    "mixed":        "404684003",   # Broad fallback — Clinical finding
}


@mcp.tool()
def search_snomed(term: str, concept_type: str = "chronic_condition", max_results: int = 20) -> list[dict]:
    """
    Search SNOMED CT for concepts matching a term, scoped to the appropriate
    concept hierarchy based on concept_type.
    Returns: list of {snomed_id, preferred_term, synonyms, hierarchy_path, source}
    synonyms: enriched post-validation via get_synonyms()
    hierarchy_path: reserved for future use
    """
    url = f"{BASE_URL}/ValueSet/$expand"
    root_id = CONCEPT_TYPE_ROOTS.get(concept_type, "404684003")
    params = {
        "filter": term,
        "count": max_results,
        "url": f"http://snomed.info/sct?fhir_vs=isa/{root_id}"
    }
    try:
        response = httpx.get(url, headers=HEADERS, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        results = []
        for entry in data.get("expansion", {}).get("contains", []):
            results.append({
                "snomed_id": entry.get("code"),
                "preferred_term": entry.get("display"),
                "synonyms": [],       # enriched post-validation via get_synonyms()
                "hierarchy_path": [], # reserved for future use
                "source": "snomed_search"
            })
        return results
    except Exception as e:
        return [{"error": str(e), "term": term}]


@mcp.tool()
def get_synonyms(concept_id: str) -> dict:
    """
 Get all synonyms and designations for a single SNOMED concept.
    Uses CodeSystem/$lookup — different endpoint from ValueSet/$expand.
    Returns: {concept_id, synonyms: [{term, type}]}
    where type is 'preferredTerm' or 'synonym'

    Called TWICE in the pipeline:
    1. Node 1 — on top 3 search hits to expand synonym list for broader recall
    2. Node 4 — on confirmed codes to enrich justification text
    """
    url = f"{BASE_URL}/CodeSystem/$lookup"
    params = {
        "system": "http://snomed.info/sct",
        "code": concept_id,
        "property": "designation"
    }
    try:
        response = httpx.get(url, headers=HEADERS, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        synonyms = []
        for param in data.get("parameter", []):
            if param.get("name") == "designation":
                parts = {p["name"]: p for p in param.get("part", [])}
                term = parts.get("value", {}).get("valueString")
                use  = parts.get("use", {}).get("valueCoding", {}).get("display", "synonym")
                if term:
                    synonyms.append({
                        "term": term,
                        "type": "preferredTerm" if "preferred" in use.lower() else "synonym"
                    })
        return {"concept_id": concept_id, "synonyms": synonyms}
    except Exception as e:
        return {"error": str(e), "concept_id": concept_id}


@mcp.tool()
def get_descendants(concept_id: str, max_results: int = 50) -> list[dict]:
    """
    Get all IS-A descendant concepts for a SNOMED concept ID.
    Critical for hierarchy traversal — e.g. all subtypes of Heart Failure.
    Does NOT return synonyms — use get_synonyms() separately on confirmed codes.
    Returns: list of {snomed_id, preferred_term, parent_id, source}
    """
    url = f"{BASE_URL}/ValueSet/$expand"
    params = {
        "url": f"http://snomed.info/sct?fhir_vs=isa/{concept_id}",
        "count": max_results
    }
    try:
        response = httpx.get(url, headers=HEADERS, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        results = []
        for entry in data.get("expansion", {}).get("contains", []):
            results.append({
                "snomed_id": entry.get("code"),
                "preferred_term": entry.get("display"),
                "parent_id": concept_id,
                "source": "snomed_hierarchy"  # distinguishes from text search hits
            })
        return results
    except Exception as e:
        return [{"error": str(e), "concept_id": concept_id}]


if __name__ == "__main__":
    mcp.run(transport="stdio")
