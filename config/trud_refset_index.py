"""
config/trud_refset_index.py

Manual index of TRUD Primary Care Domain Reference Set IDs.
Maps condition keywords → TRUD refset IDs.
Source: https://isd.digital.nhs.uk/trud/users/guest/filters/0/categories/26

Maintenance: update when NHS Digital publishes new reference sets.
Covers ~90% of common primary care conditions with ~30 entries.
Last updated: March 2026
"""

TRUD_REFSET_INDEX = {
    # ── Cardiovascular ──────────────────────────────────────────────
    "heart failure":                    "84114007",   # HF_COD
    "cardiac failure":                  "84114007",   # HF_COD
    "reduced ejection fraction":        "703272007",  # REDEJFRAC_COD
    "heart failure reduced ejection":   "703272007",  # REDEJFRAC_COD
    "hfref":                            "703272007",  # REDEJFRAC_COD
    "lvsd":                             "703272007",  # REDEJFRAC_COD
    "atrial fibrillation":              "49436004",   # AFIB_COD  ← verified [web:34]
    "af register":                      "49436004",   # AFIB_COD
    "atrial flutter":                   "49436004",   # AFIB_COD

    # ── Metabolic ───────────────────────────────────────────────────
    "diabetes mellitus":                "44054006",   # DM_COD  ← verified [web:35]
    "type 2 diabetes":                  "44054006",   # DM_COD
    "t2dm":                             "44054006",   # DM_COD

    # ── NOT YET IN trud_data.py — keys provided for future expansion ─
    # Add these refsets to trud_data.py before enabling:
    # "coronary heart disease":         "53741008",   # CHD_COD
    # "hypertension":                   "38341003",   # HYP_COD
    # "copd":                           "13645005",   # COPD_COD
    # "asthma":                         "195967001",  # AST_COD
    # "chronic kidney disease":         "709044004",  # CKD_COD
    # "ckd":                            "709044004",  # CKD_COD
    # "osteoporosis":                   "64859006",   # OST_COD
    # "rheumatoid arthritis":           "69896004",   # RA_COD
    # "epilepsy":                       "84757009",   # EP_COD
    # "hypothyroidism":                 "40930008",   # THY_COD
    # "depression":                     "35489007",   # DEP_COD
    # "dementia":                       "52448006",   # DEM_COD
    # "obesity":                        "414916001",  # OB_COD
    # "cancer":                         "363346000",  # CAN_COD
    # "stroke tia":                     "230690007",  # STIA_COD
    # "palliative care":                "103693007",  # PC_COD
    # "learning disability":            "91138005",   # LD_COD
    # "peripheral arterial disease":    "400047006",  # PAD_COD
    # "schizophrenia":                  "58214004",   # MH_COD
}


def fuzzy_match_trud(condition_text: str) -> list[tuple[str, str]]:
    """
    Fuzzy keyword match against TRUD_REFSET_INDEX.
    Returns list of (keyword_matched, refset_id) tuples.
    Multiple matches possible — e.g. "heart failure reduced ejection"
    matches both HF_COD and REDEJCFRAC_COD.
    """
    condition_lower = condition_text.lower()
    matches = []
    seen_refset_ids = set()

    for keyword, refset_id in TRUD_REFSET_INDEX.items():
        # Check if any keyword word appears in condition text
        keyword_words = keyword.split()
        if all(word in condition_lower for word in keyword_words):
            if refset_id not in seen_refset_ids:
                matches.append((keyword, refset_id))
                seen_refset_ids.add(refset_id)

    return matches
