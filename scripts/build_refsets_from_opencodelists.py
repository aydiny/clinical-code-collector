# scripts/build_refsets_from_opencodelists.py  — FIXED

"""
Downloads NHSD Primary Care Domain refsets from OpenCodelists.
Correct URL pattern: /api/v1/codelist/{org}/{slug}/{version}/codes/
Latest version tag: 20250912
"""

import httpx
import pandas as pd
from pathlib import Path
import time

BASE    = "https://www.opencodelists.org/api/v1"
ORG     = "nhsd-primary-care-domain-refsets"
VERSION = "20250912"   # ← latest release; fallback to 20241205 if 404
OUT     = Path("data/raw/trud/primary_care_refsets.csv")

# slug → (refsetId from TRUD index, refsetName)
CODELISTS = {
    "hf_cod":         ("999002401000000105", "HF_COD"),
    "redejcfrac_cod": ("991411000000109",    "REDEJCFRAC_COD"),
    "dm_cod":         ("999004691000000108", "DM_COD"),
    "afib_cod":       ("999002271000000101", "AFIB_COD"),
    "chd_cod":        ("999002301000000104", "CHD_COD"),
    "hyp_cod":        ("999002461000000107", "HYP_COD"),
    "copd_cod":       ("999002371000000107", "COPD_COD"),
    "ast_cod":        ("999002321000000101", "AST_COD"),
    "ckd_cod":        ("999002351000000101", "CKD_COD"),
    "dep_cod":        ("999002431000000101", "DEP_COD"),
    "ep_cod":         ("999002451000000109", "EP_COD"),
    "ost_cod":        ("999002561000000103", "OST_COD"),
    "ra_cod":         ("999002591000000102", "RA_COD"),
    "thy_cod":        ("999002511000000107", "THY_COD"),
    "stia_cod":       ("999002681000000101", "STIA_COD"),
}

FALLBACK_VERSION = "20241205"

def fetch_codes(slug: str) -> list[dict]:
    for version in [VERSION, FALLBACK_VERSION]:
        url = f"{BASE}/codelist/{ORG}/{slug}/{version}/codes/"
        try:
            r = httpx.get(url, timeout=15, follow_redirects=True)
            if r.status_code == 200:
                data = r.json()
                # Response is list or dict with "codes" key
                codes = data if isinstance(data, list) else data.get("codes", [])
                if codes:
                    print(f"  ✅ {len(codes)} codes (version {version})")
                    return codes
            else:
                print(f"  ⚠️  {r.status_code} for version {version}")
        except Exception as e:
            print(f"  ❌ {e}")
    return []

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_rows = []

    for slug, (refset_id, refset_name) in CODELISTS.items():
        print(f"\nFetching {refset_name} ({slug})...")
        codes = fetch_codes(slug)

        if not codes:
            print(f"  ❌ No codes returned — skipping")
            continue

        for c in codes:
            concept_id = str(c.get("code") or c.get("id", ""))
            term       = c.get("term") or c.get("label", "")
            if concept_id:
                all_rows.append({
                    "conceptId":  concept_id,
                    "term":       term,
                    "refsetId":   refset_id,
                    "refsetName": refset_name,
                    "active":     "1"
                })
        time.sleep(0.3)

    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUT, index=False)
        print(f"\n{'='*50}")
        print(f"✅ Saved {len(df)} rows → {OUT}")
        print("\nCodes per refset:")
        print(df.groupby("refsetName").size().sort_values(ascending=False).to_string())
    else:
        print("\n❌ No data — check internet connection")

if __name__ == "__main__":
    main()
