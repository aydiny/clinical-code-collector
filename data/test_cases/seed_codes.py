"""
Seed codes for Node 3 validation testing.
Source: NHS Primary Care Domain Refsets (OpenCodelists / TRUD)
Usage:  from data.test_cases.seed_codes import SEED_CODES
"""

SEED_CODES = {

    # ── TC1: Heart Failure with Reduced Ejection Fraction ─────────────────────
    "TC1_HFrEF": [
        {"snomed_id": "703272007", "term": "Heart failure with reduced ejection fraction",                                 "tier": "GOLD", "qof_refset": "REDEJCFRAC_COD", "l1": True, "l2": True, "l3": True,  "notes": "Primary HFrEF code - target output for TC1 query"},
        {"snomed_id": "703273002", "term": "Heart failure with reduced ejection fraction due to coronary artery disease",  "tier": "GOLD", "qof_refset": "REDEJCFRAC_COD", "l1": True, "l2": True, "l3": True,  "notes": "Ischaemic aetiology subtype"},
        {"snomed_id": "703274008", "term": "Heart failure with reduced ejection fraction due to hypertension",             "tier": "GOLD", "qof_refset": "REDEJCFRAC_COD", "l1": True, "l2": True, "l3": True,  "notes": "Hypertensive aetiology subtype"},
        {"snomed_id": "703275009", "term": "Heart failure with reduced ejection fraction due to cardiomyopathy",           "tier": "GOLD", "qof_refset": "REDEJCFRAC_COD", "l1": True, "l2": True, "l3": True,  "notes": "Cardiomyopathy aetiology subtype"},
        {"snomed_id": "703276005", "term": "Heart failure with reduced ejection fraction due to valvular heart disease",   "tier": "GOLD", "qof_refset": "REDEJCFRAC_COD", "l1": True, "l2": True, "l3": True,  "notes": "Valvular aetiology subtype"},
        {"snomed_id": "84114007",  "term": "Heart failure",                                                                "tier": "EDGE", "qof_refset": "HF_COD",          "l1": True, "l2": True, "l3": True,  "notes": "Generic HF - QOF register hit but non-specific"},
        {"snomed_id": "48447003",  "term": "Chronic heart failure",                                                        "tier": "EDGE", "qof_refset": "HF_COD",          "l1": True, "l2": True, "l3": True,  "notes": "Chronic HF - not ejection-fraction-specific"},
        {"snomed_id": "426263006", "term": "Congestive heart failure",                                                     "tier": "EDGE", "qof_refset": "HF_COD",          "l1": True, "l2": True, "l3": True,  "notes": "Older non-specific term"},
        {"snomed_id": "195111005", "term": "Decompensated cardiac failure",                                                "tier": "EDGE", "qof_refset": "HF_COD",          "l1": True, "l2": True, "l3": True,  "notes": "Acuity descriptor - not a chronic register code"},
        {"snomed_id": "446221000", "term": "Heart failure with normal ejection fraction",                                  "tier": "TRAP", "qof_refset": "HF_COD",          "l1": True, "l2": True, "l3": True,  "notes": "HFpEF - opposite phenotype. Critical Node 4 discriminator"},
        {"snomed_id": "233924009", "term": "Heart failure due to left ventricular systolic dysfunction",                   "tier": "TRAP", "qof_refset": "HF_COD",          "l1": True, "l2": True, "l3": False, "notes": "Not in REDEJCFRAC_COD - tests Layer 3 miss"},
    ],

    # ── TC2: Type 2 Diabetes Mellitus ─────────────────────────────────────────
    "TC2_T2DM": [
        {"snomed_id": "44054006",  "term": "Diabetes mellitus type 2",                                                    "tier": "GOLD", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Root T2DM code - highest frequency in GP records"},
        {"snomed_id": "313436004", "term": "Type II diabetes mellitus without complication",                               "tier": "GOLD", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Uncomplicated T2DM - very common primary care code"},
        {"snomed_id": "443694000", "term": "Uncontrolled type 2 diabetes mellitus",                                       "tier": "GOLD", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Poor glycaemic control subtype"},
        {"snomed_id": "237599002", "term": "Insulin treated type 2 diabetes mellitus",                                    "tier": "GOLD", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Treatment-specific subtype"},
        {"snomed_id": "445353002", "term": "Brittle type 2 diabetes mellitus",                                            "tier": "GOLD", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Difficult-to-control subtype"},
        {"snomed_id": "422014003", "term": "Disorder due to type 2 diabetes mellitus",                                    "tier": "GOLD", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Generic T2DM complication parent code"},
        {"snomed_id": "190388001", "term": "Multiple complications due to type 2 diabetes mellitus",                      "tier": "EDGE", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Valid but over-specific for register query"},
        {"snomed_id": "314902007", "term": "Peripheral angiopathy due to type 2 diabetes mellitus",                       "tier": "EDGE", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Vascular complication - tests Node 4 complication vs register distinction"},
        {"snomed_id": "421631007", "term": "Gangrene due to type 2 diabetes mellitus",                                    "tier": "EDGE", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Severe complication - should not be primary register code"},
        {"snomed_id": "703138006", "term": "Type II diabetes mellitus in remission",                                      "tier": "EDGE", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Remission state - Node 4 should flag as non-active disease"},
        {"snomed_id": "46635009",  "term": "Diabetes mellitus type 1",                                                    "tier": "TRAP", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "WRONG TYPE - T1DM in DM_COD. Node 4 must flag type mismatch"},
        {"snomed_id": "73211009",  "term": "Diabetes mellitus",                                                           "tier": "TRAP", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Non-specific DM root - too broad no type specified"},
        {"snomed_id": "426705001", "term": "Diabetes mellitus co-occurrent and due to cystic fibrosis",                   "tier": "TRAP", "qof_refset": "DM_COD", "l1": True, "l2": True, "l3": True,  "notes": "Secondary DM - wrong aetiology for T2DM query"},
    ],

    # ── TC3: Atrial Fibrillation ───────────────────────────────────────────────
    "TC3_AF": [
        {"snomed_id": "49436004",        "term": "Atrial fibrillation",                                                   "tier": "GOLD", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Root AF code - most recorded in NHS GP systems"},
        {"snomed_id": "426749004",       "term": "Chronic atrial fibrillation",                                           "tier": "GOLD", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Persistent/permanent AF subtype"},
        {"snomed_id": "440028005",       "term": "Permanent atrial fibrillation",                                         "tier": "GOLD", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Rate-control strategy subtype"},
        {"snomed_id": "282825002",       "term": "Paroxysmal atrial fibrillation",                                        "tier": "GOLD", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Intermittent AF - very common subtype"},
        {"snomed_id": "314208002",       "term": "Rapid atrial fibrillation",                                             "tier": "GOLD", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "AF with fast ventricular rate"},
        {"snomed_id": "300996004",       "term": "Controlled atrial fibrillation",                                        "tier": "GOLD", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Rate-controlled AF - common QOF recording"},
        {"snomed_id": "195080001",       "term": "Atrial fibrillation and flutter",                                       "tier": "EDGE", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Combined code - tests Node 4 disambiguation"},
        {"snomed_id": "120041000119109", "term": "Atrial fibrillation with rapid ventricular response",                   "tier": "EDGE", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Haemodynamic descriptor - acute context code (UK edition)"},
        {"snomed_id": "233901000000100", "term": "AF - atrial fibrillation",                                              "tier": "EDGE", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "UK-specific abbreviation code - NHS UK Edition only"},
        {"snomed_id": "5370000",         "term": "Atrial flutter",                                                        "tier": "TRAP", "qof_refset": "AFIB_COD", "l1": True, "l2": True,  "l3": True,  "notes": "Flutter != fibrillation. In AFIB_COD but Node 4 must flag"},
        {"snomed_id": "251208004",       "term": "Atrial tachycardia",                                                    "tier": "TRAP", "qof_refset": "NONE",     "l1": True, "l2": False, "l3": False, "notes": "Clinically adjacent but NOT in AFIB_COD - good Layer 2/3 miss test"},
        {"snomed_id": "233917008",       "term": "Atrioventricular re-entrant tachycardia",                               "tier": "TRAP", "qof_refset": "NONE",     "l1": True, "l2": False, "l3": False, "notes": "Wrong rhythm disorder - should fail Layer 2 and 3"},
    ],
}


def get_all_codes() -> list[dict]:
    """Flat list of all seed codes with test_case field added."""
    all_codes = []
    for tc_name, codes in SEED_CODES.items():
        for code in codes:
            all_codes.append({"test_case": tc_name, **code})
    return all_codes


def get_tc_codes(test_case: str) -> list[dict]:
    """Codes for one test case e.g. get_tc_codes('TC1_HFrEF')."""
    return SEED_CODES.get(test_case, [])
