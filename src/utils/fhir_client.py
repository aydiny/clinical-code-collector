# src/utils/fhir_client.py
import time
import os
import httpx

FHIR_BASE  = "https://ontology.nhs.uk/production1/fhir"
TOKEN_URL  = "https://ontology.nhs.uk/authorisation/auth/realms/nhs-digital-terminology/protocol/openid-connect/token"
MAX_RESULTS_PER_TERM = 15
MAX_DESCENDANTS      = 50

CONCEPT_TYPE_ROOTS = {
    "diagnosis":   "64572001",
    "finding":     "404684003",
    "observation": "404684003",
    "procedure":   "71388002",
    "lab_result":  "363787002",
    "medication":  "373873005",
    "demographic": "48176007",
    "situation":   "243796009",
    "mixed":       "404684003",
}

_token_cache = {"token": None, "expires_at": 0}

def _get_headers() -> dict:
    now = time.time()
    if not _token_cache["token"] or now >= _token_cache["expires_at"] - 30:
        resp = httpx.post(TOKEN_URL, data={
            "grant_type":    "client_credentials",
            "client_id":     os.getenv("FHIR_CLIENT_ID"),
            "client_secret": os.getenv("FHIR_CLIENT_SECRET")
        }, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"]      = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 300)
    return {
        "Authorization": f"Bearer {_token_cache['token']}",
        "Accept":        "application/json"
    }
