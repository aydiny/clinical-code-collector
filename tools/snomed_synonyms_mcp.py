@mcp.tool()
def get_synonyms(concept_id: str) -> list[dict]:
    """
    Retrieve all NHS-official synonym descriptions for a SNOMED concept ID.
    Uses NHS Terminology Server /CodeSystem/$lookup endpoint.
    Returns: list of {description_id, term, type}
    where type is 'preferredTerm' or 'synonym'
    """
    url = f"{BASE_URL}/CodeSystem/$lookup"
    params = {
        "system": "http://snomed.info/sct",
        "code": concept_id,
        "property": "designation"
    }
    response = httpx.get(url, headers=HEADERS, params=params, timeout=10.0)
    data = response.json()

    synonyms = []
    for param in data.get("parameter", []):
        if param.get("name") == "designation":
            synonyms.append({
                "term": param.get("valueString"),
                "type": "synonym"
            })
    return synonyms
