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

@mcp.tool()
def search_snomed(term: str, max_results: int = 20) -> list[dict]:
    """
    Search SNOMED CT for concepts matching a term.
    Returns: list of {snomed_id, preferred_term, synonyms, hierarchy_path}
    """
    # FHIR call: GET /ValueSet/$expand?filter={term}&count={max_results}
    url = f"{BASE_URL}/ValueSet/$expand"
    params = {
        "filter": term,
        "count": max_results,
        "url": "http://snomed.info/sct?fhir_vs=isa/404684003"  # Clinical Finding root
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
                "synonyms": [],           # populated in get_descendants
                "hierarchy_path": [],     # populated in get_descendants
                "source": "snomed_search"
            })
        return results
    except Exception as e:
        return [{"error": str(e), "term": term}]


@mcp.tool()
def get_descendants(concept_id: str, max_results: int = 50) -> list[dict]:
    """
    Get all descendant concepts (children, grandchildren) for a SNOMED concept ID.
    Critical for hierarchy traversal — e.g. all subtypes of Heart Failure.
    Returns: list of {snomed_id, preferred_term, parent_id}
    """
    # FHIR call: GET /ValueSet/$expand?url=http://snomed.info/sct?fhir_vs=isa/{concept_id}
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
                "source": "snomed_search"
            })
        return results
    except Exception as e:
        return [{"error": str(e), "concept_id": concept_id}]


if __name__ == "__main__":
    mcp.run(transport="stdio")
