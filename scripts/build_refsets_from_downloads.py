# scripts/build_refsets_from_downloads.py

import pandas as pd
from pathlib import Path
from decimal import Decimal

DOWNLOADS = Path("data/trud/downloads")
OUT       = Path("data/trud/primary_care_refsets.csv")

# filename fragment → (refsetId, refsetName)
# adjust the keys to match your actual filenames
FILE_MAP = {
    "refsets-hf_cod":         ("999002401000000105", "HF_COD"),
    "refsets-redejcfrac":     ("991411000000109",    "REDEJCFRAC_COD"),
    "refsets-dm_cod":         ("999004691000000108", "DM_COD"),
    "refsets-afib_cod":       ("999002271000000101", "AFIB_COD"),
}

def fix_snomed_id(val: str) -> str:
    """Convert scientific notation string to full integer string."""
    val = str(val).strip()
    if "E" in val.upper() and "+" in val:
        try:
            return str(int(Decimal(val)))
        except Exception:
            return val
    return val

all_rows = []

for slug, (refset_id, refset_name) in FILE_MAP.items():
    # find the file containing this slug in its name
    matches = [f for f in DOWNLOADS.glob("*.csv")
               if slug.lower() in f.name.lower()]
    if not matches:
        print(f"❌ No file found for '{slug}' in {DOWNLOADS}")
        print(f"   Files available: {[f.name for f in DOWNLOADS.glob('*.csv')]}")
        continue

    f = matches[0]
    df = pd.read_csv(f, dtype=str)
    print(f"\n{refset_name}: {f.name}")
    print(f"  Columns : {list(df.columns)}")
    print(f"  Rows    : {len(df)}")
    print(f"  Sample  : {df.iloc[0].to_dict()}")

    # detect code + term columns
    code_col = next((c for c in df.columns
                     if c.lower() in ("code", "snomedctconceptid",
                                      "conceptid", "id")), None)
    term_col = next((c for c in df.columns
                     if c.lower() in ("term", "description",
                                      "dmd_name", "label")), None)

    if not code_col:
        print(f"  ❌ Cannot find code column — skipping")
        continue

    for _, row in df.iterrows():
        raw_id     = str(row.get(code_col, "")).strip()
        concept_id = fix_snomed_id(raw_id)
        term       = str(row.get(term_col, "")).strip() if term_col else ""

        if concept_id and concept_id != "nan":
            all_rows.append({
                "conceptId":  concept_id,
                "term":       term,
                "refsetId":   refset_id,
                "refsetName": refset_name,
                "active":     "1"
            })

    print(f"  ✅ Added to combined file")

if all_rows:
    out_df = pd.DataFrame(all_rows)
    out_df.to_csv(OUT, index=False, quoting=1)   # QUOTE_ALL prevents float conversion
    print(f"\n{'='*55}")
    print(f"✅ Saved {len(out_df)} rows → {OUT}")
    print("\nCodes per refset:")
    print(out_df.groupby("refsetName").size()
                .sort_values(ascending=False).to_string())

    # Spot check — verify no scientific notation survived
    sci = out_df[out_df["conceptId"].str.contains("E|e", regex=True)]
    if len(sci):
        print(f"\n⚠️  {len(sci)} IDs still in scientific notation:")
        print(sci["conceptId"].tolist())
    else:
        print("\n✅ All SNOMED IDs are clean integers")
else:
    print("\n❌ No rows — check filenames match FILE_MAP keys above")
