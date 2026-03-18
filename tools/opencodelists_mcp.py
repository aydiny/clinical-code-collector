"""
MCP Tool Server — OpenCodelists REST API
Run standalone: python tools/opencodelists_mcp.py
"""
from mcp.server.fastmcp import FastMCP
import httpx

mcp = FastMCP("opencodelists-tool-server")

BASE_URL = "https://www.opencodelists.org/api/v1"

@mcp.tool()
def search_codelists(condition: str) -> list[dict]:
    """
    Search OpenCodelists for codelists matching a condition name.
    Returns: list of {codelist_id, name, organisation, coding_system, url}
    """
    url = f"{BASE_URL}/codelist/"
    params = {"q": condition}
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "codelist_id": item.get("slug"),
                "name": item.get("name"),
                "organisation": item.get("organisation", {}).get("name"),
                "coding_system": item.get("coding_system_id"),
                "url": item.get("url")
            })
        return results
    except Exception as e:
        return [{"error": str(e), "condition": condition}]


@mcp.tool()
def lookup_code_in_codelists(snomed_id: str, condition: str) -> dict:
    """
    Check whether a SNOMED code appears in any OpenCodelists codelist
    for a given condition. Used by Validator Agent for confidence scoring.
    Returns: {snomed_id, found, codelist_name, organisation}
    """
    # Search for relevant codelists first, then check membership
    codelists = search_codelists(condition)
    for codelist in codelists:
        if "error" in codelist:
            continue
        codelist_id = codelist.get("codelist_id", "")
        if not codelist_id:
            continue
        # GET /codelist/{org}/{codelist_id}/
        try:
            url = f"{BASE_URL}/codelist/{codelist_id}/"
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            codes = response.json().get("codes", [])
            code_ids = [c.get("code") for c in codes]
            if snomed_id in code_ids:
                return {
                    "snomed_id": snomed_id,
                    "found": True,
                    "codelist_name": codelist.get("name"),
                    "organisation": codelist.get("organisation")
                }
        except Exception:
            continue
    return {"snomed_id": snomed_id, "found": False, "codelist_name": None}


if __name__ == "__main__":
    mcp.run(transport="stdio")
