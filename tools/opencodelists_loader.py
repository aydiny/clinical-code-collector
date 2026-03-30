# tools/opencodelists_loader.py
import requests, csv, io

# Map known non-standard column names → standard
COLUMN_ALIASES = {
    "code":       ["code", "id", "snomed_id", "conceptId", "concept_id"],
    "term":       ["term", "name", "preferred_term", "description"],
}

def _extract_code(row: dict) -> str:
    for col in COLUMN_ALIASES["code"]:
        val = row.get(col, "").strip()
        if val.isdigit() and 6 <= len(val) <= 18:
            return val
    return ""

def load_codelist_from_url(url: str) -> set[str]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        codes = set()
        for row in reader:
            code = _extract_code(row)
            if code:
                codes.add(code)
        return codes
    except Exception as e:
        print(f"[L1] Failed to load {url}: {e}")
        return set()