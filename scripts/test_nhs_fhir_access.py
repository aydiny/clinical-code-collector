# scripts/test_nhs_fhir_access.py

import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://ontology.nhs.uk/production1/fhir"
API_KEY  = os.getenv("NHS_ONTOLOGY_API_KEY", "")


def test_access():

    # ── Test 1: Unauthenticated ping ─────────────────────────────
    print("\n── Test 1: Unauthenticated ping ──")
    try:
        r = httpx.get(f"{BASE_URL}/metadata", timeout=10)
        print(f"  Status : {r.status_code}")
        print(f"  Server : {r.headers.get('server', 'unknown')}")
    except Exception as e:
        print(f"  FAILED : {e}")

    # ── Test 2: API key check ─────────────────────────────────────
    print("\n── Test 2: API key loaded ──")
    print(f"  NHS_ONTOLOGY_API_KEY set : {bool(API_KEY)}")
    print(f"  Key length               : {len(API_KEY)} chars")

    if not API_KEY:
        print("\n  ❌ STOPPED — NHS_ONTOLOGY_API_KEY not found in .env")
        print("     Add this to your .env file:")
        print("     NHS_ONTOLOGY_API_KEY=your-key-here")
        return

    # ── Test 3: Authenticated SNOMED search ───────────────────────
    print("\n── Test 3: Authenticated SNOMED search ──")
    headers = {
        "apiKey":       API_KEY,
        "Accept":       "application/fhir+json",
        "Content-Type": "application/fhir+json"
    }
    params = {
        "url":    "http://snomed.info/sct?fhir_vs=isa/404684003",
        "filter": "heart failure",
        "count":  "3"
    }

    try:
        r = httpx.get(
            f"{BASE_URL}/ValueSet/$expand",
            headers=headers,
            params=params,
            timeout=10
        )
        print(f"  Status : {r.status_code}")

        if r.status_code == 200:
            codes = r.json().get("expansion", {}).get("contains", [])
            print(f"  ✅ SUCCESS — {len(codes)} codes returned")
            for c in codes:
                print(f"     {c.get('code')} — {c.get('display')}")

        elif r.status_code == 401:
            print("  ❌ 401 Unauthorised — API key invalid or not yet active")
            print(f"     Response: {r.text[:300]}")

        elif r.status_code == 403:
            print("  ❌ 403 Forbidden — key received but access not yet approved")
            print("     Chase: information.standards@nhs.net")
            print(f"     Response: {r.text[:300]}")

        else:
            print(f"  ⚠️  Unexpected status: {r.status_code}")
            print(f"     Response: {r.text[:300]}")

    except httpx.ConnectError:
        print("  ❌ Cannot reach ontology.nhs.uk — check VPN/network")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # ── Test 4: Synonym lookup ────────────────────────────────────
    print("\n── Test 4: Synonym lookup for 84114007 (Heart failure) ──")
    try:
        r = httpx.get(
            f"{BASE_URL}/CodeSystem/$lookup",
            headers=headers,
            params={
                "system":   "http://snomed.info/sct",
                "code":     "84114007",
                "property": "designation"
            },
            timeout=10
        )
        print(f"  Status : {r.status_code}")

        if r.status_code == 200:
            params_list = r.json().get("parameter", [])
            designations = [
                p for p in params_list
                if p.get("name") == "designation"
            ]
            print(f"  ✅ {len(designations)} designations found")
            for d in designations[:5]:
                parts = {
                    p["name"]: p.get("valueString") or p.get("valueCoding", {})
                    for p in d.get("part", [])
                }
                print(f"     {parts.get('value', '')} "
                      f"({parts.get('use', {}).get('display', '')})")
        else:
            print(f"  Status {r.status_code}: {r.text[:200]}")

    except Exception as e:
        print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    test_access()
