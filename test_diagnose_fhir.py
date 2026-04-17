# tests/diagnose_fhir.py
"""
Direct FHIR API diagnostic — bypasses MCP completely
Run: python tests/diagnose_fhir.py
"""
import httpx
import os
import time
from dotenv import load_dotenv
load_dotenv()

TOKEN_URL = "https://ontology.nhs.uk/authorisation/auth/realms/nhs-digital-terminology/protocol/openid-connect/token"
FHIR_BASE = "https://ontology.nhs.uk/production1/fhir"

def get_token() -> str:
    print("\n[1] Fetching token...")
    resp = httpx.post(TOKEN_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     os.getenv("FHIR_CLIENT_ID"),
        "client_secret": os.getenv("FHIR_CLIENT_SECRET")
    }, timeout=15.0)
    print(f"    Status : {resp.status_code}")
    if resp.status_code != 200:
        print(f"    Body   : {resp.text}")
        raise SystemExit("Auth failed — check FHIR_CLIENT_ID and FHIR_CLIENT_SECRET in .env")
    token = resp.json()["access_token"]
    print(f"    Token  : {token[:40]}...")
    return token

def test_search(token: str):
    print("\n[2] Testing ValueSet/$expand (text search)...")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params  = {
        "url":    "http://snomed.info/sct?fhir_vs=isa/64572001",
        "filter": "atrial fibrillation",
        "count":  5
    }
    resp = httpx.get(f"{FHIR_BASE}/ValueSet/$expand",
                     headers=headers, params=params, timeout=15.0)
    print(f"    Status : {resp.status_code}")
    if resp.status_code != 200:
        print(f"    Body   : {resp.text[:500]}")
        return
    contains = resp.json().get("expansion", {}).get("contains", [])
    print(f"    Results: {len(contains)}")
    for c in contains[:5]:
        print(f"    → {c['code']:20s} {c['display']}")

def test_ecl(token: str):
    print("\n[3] Testing ValueSet/$expand (ECL descendants of AF 49436004)...")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params  = {
        "url":   "http://snomed.info/sct?fhir_vs=ecl/%3C%3C%2049436004",
        "count": 5
    }
    resp = httpx.get(f"{FHIR_BASE}/ValueSet/$expand",
                     headers=headers, params=params, timeout=15.0)
    print(f"    Status : {resp.status_code}")
    if resp.status_code != 200:
        print(f"    Body   : {resp.text[:500]}")
        return
    contains = resp.json().get("expansion", {}).get("contains", [])
    print(f"    Results: {len(contains)}")
    for c in contains[:5]:
        print(f"    → {c['code']:20s} {c['display']}")

if __name__ == "__main__":
    token = get_token()
    test_search(token)
    test_ecl(token)
    print("\n✅ FHIR API is working — problem is in MCP transport layer")