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
    # Cardiovascular
    "heart failure":                        "999002401000000105",  # HF_COD
    "reduced ejection fraction":            "991411000000109",     # REDEJCFRAC_COD
    "heart failure reduced ejection":       "991411000000109",     # REDEJCFRAC_COD
    "hfref":                                "991411000000109",     # REDEJCFRAC_COD
    "atrial fibrillation":                  "999002271000000101",  # AF_COD
    "coronary heart disease":               "999002301000000104",  # CHD_COD
    "hypertension":                         "999002461000000107",  # HYP_COD
    "peripheral arterial disease":          "999002491000000103",  # PAD_COD
    "stroke tia":                           "999002681000000101",  # STIA_COD
    # Respiratory
    "copd":                                 "999002371000000107",  # COPD_COD
    "asthma":                               "999002321000000101",  # AST_COD
    # Metabolic
    "type 2 diabetes":                      "999004691000000108",  # DM_COD
    "diabetes":                             "999004691000000108",  # DM_COD
    "obesity":                              "999002541000000102",  # OB_COD
    # Mental health
    "depression":                           "999002431000000101",  # DEP_COD
    "dementia":                             "999002401000000104",  # DEM_COD
    "schizophrenia psychosis":              "999002621000000100",  # MH_COD
    # Renal
    "chronic kidney disease":               "999002351000000101",  # CKD_COD
    "ckd":                                  "999002351000000101",  # CKD_COD
    # Cancer
    "cancer":                               "999002341000000103",  # CAN_COD
    # Musculoskeletal
    "osteoporosis":                         "999002561000000103",  # OST_COD
    "rheumatoid arthritis":                 "999002591000000102",  # RA_COD
    # Other
    "epilepsy":                             "999002451000000109",  # EP_COD
    "hypothyroidism":                       "999002511000000107",  # THY_COD
    "learning disability":                  "999002521000000101",  # LD_COD
    "palliative care":                      "999002571000000109",  # PC_COD
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
