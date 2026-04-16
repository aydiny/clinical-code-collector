# config/opencodelists_index.py
# All entries verified as SNOMED CT, tagged with explicit clinical intent and category.

OPENCODELISTS_INDEX = {

    # =========================================================================
    # ── 1. HEART FAILURE (HFrEF, LVSD) ───────────────────────────────────────
    # =========================================================================
    "heart failure": [
        {
            "name": "QOF Heart Failure Register (HF_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/hf_cod/20250912/download.csv",
            "intent": "QOF_Register",
            "category": "Diagnosis"
        },
        {
            "name": "PINCER Heart Failure (Safety Audit)",
            "org":  "pincer",
            "url":  "https://www.opencodelists.org/codelist/pincer/hf/v1.8/download.csv",
            "intent": "Safety_Audit",
            "category": "Diagnosis"
        },
        {
            "name": "REDUCEHF Heart Failure Broad",
            "org":  "reducehf",
            "url":  "https://www.opencodelists.org/codelist/reducehf/heart-failure-broad-for-excluding-people/17bd3b08/download.csv",
            "intent": "Epidemiology",
            "category": "Diagnosis"
        }
    ],
    "hfref": [
        {
            "name": "NHSD Reduced Ejection Fraction Codes",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/redejcfrac_cod/20250912/download.csv",
            "intent": "NHSD_Curated",
            "category": "Diagnosis"
        }
    ],
    "left ventricular systolic dysfunction": [
        {
            "name": "QOF LVSD Assessment (LVSD_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/hflvsd_cod/20250912/download.csv",
            "intent": "QOF_Register",
            "category": "Observation"
        }
    ],

    # =========================================================================
    # ── 2. ATRIAL FIBRILLATION ───────────────────────────────────────────────
    # =========================================================================
    "atrial fibrillation": [
        {
            "name": "QOF Atrial Fibrillation Register (AF_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/afib_cod/20250912/download.csv",
            "intent": "QOF_Register",
            "category": "Diagnosis"
        },
        {
            "name": "QOF AF Resolved (AFRES_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/afibres_cod/20250912/download.csv",
            "intent": "QOF_Resolution",
            "category": "Resolution"
        },
        {
            "name": "QCovid Atrial Fibrillation",
            "org":  "qcovid",
            "url":  "https://www.opencodelists.org/codelist/qcovid/has_atrial_fibrillation/2a4910da/download.csv",
            "intent": "Epidemiology",
            "category": "Diagnosis"
        }
    ],

    # =========================================================================
    # ── 3. DIABETES MELLITUS (T2DM) ──────────────────────────────────────────
    # =========================================================================
    "diabetes mellitus": [
        {
            "name": "QOF Diabetes Register (DM_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/dm_cod/20250912/download.csv",
            "intent": "QOF_Register",
            "category": "Diagnosis"
        },
        {
            "name": "QOF Diabetes Resolved (DMRES_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/dmres_cod/20250912/download.csv",
            "intent": "QOF_Resolution",
            "category": "Resolution"
        },
        {
            "name": "OpenSAFELY Diabetes",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/diabetes-snomed/2020-04-15/download.csv",
            "intent": "Epidemiology",
            "category": "Diagnosis"
        }
    ],
    "type 2 diabetes": [
        {
            "name": "NHSD Type 2 Diabetes Codes",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/dmtype2_cod/20250912/download.csv",
            "intent": "NHSD_Curated",
            "category": "Diagnosis"
        }
    ],
    "hba1c": [
        {
            "name": "OpenSAFELY HbA1c Tests",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/glycated-haemoglobin-hba1c-tests/2ab11f20/download.csv",
            "intent": "Epidemiology",
            "category": "Observation"
        }
    ],

    # =========================================================================
    # ── 4. HYPERTENSION ──────────────────────────────────────────────────────
    # =========================================================================
    "hypertension": [
        {
            "name": "QOF Hypertension Register (HYP_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/hyp_cod/20250912/download.csv",
            "intent": "QOF_Register",
            "category": "Diagnosis"
        },
        {
            "name": "QOF Hypertension Resolved (HYPRES_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/hypres_cod/20250912/download.csv",
            "intent": "QOF_Resolution",
            "category": "Resolution"
        },
        {
            "name": "OpenSAFELY Hypertension",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/hypertension-snomed/2020-04-28/download.csv",
            "intent": "Epidemiology",
            "category": "Diagnosis"
        }
    ],
    "blood pressure": [
        {
            "name": "QOF Blood Pressure Reading (BP_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/bp_cod/20250912/download.csv",
            "intent": "QOF_Observation",
            "category": "Observation"
        }
    ],

    # =========================================================================
    # ── 5. OBESITY ───────────────────────────────────────────────────────────
    # =========================================================================
    "obesity": [
        {
            "name": "PRIMIS BMI & Obesity Stages",
            "org":  "primis",
            "url":  "https://www.opencodelists.org/codelist/primis-covid19-vacc-uptake/bmi_stage/v2.5/download.csv",
            "intent": "NHSD_Curated", 
            "category": "Diagnosis"
        }
    ],
    "bmi": [
        {
            "name": "QOF BMI Observation (BMI_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/bmi_cod/20250912/download.csv",
            "intent": "QOF_Observation",
            "category": "Observation"
        }
    ],

    # =========================================================================
    # ── 6. COMPREHENSIVE PHARMACOLOGY (MEDICATIONS) ──────────────────────────
    # =========================================================================
    "sglt2 inhibitors": [
        {
            "name": "OpenSAFELY SGLT2 inhibitors",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/sglt2-inhibitors/2020-04-15/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ],
    "ace inhibitors": [
        {
            "name": "PINCER ACE Inhibitors and ARBs",
            "org":  "pincer",
            "url":  "https://www.opencodelists.org/codelist/pincer/acei_arb/v1.8/download.csv",
            "intent": "Safety_Audit",
            "category": "Medication"
        },
        {
            "name": "OpenSAFELY ACE inhibitors",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/ace-inhibitors/2020-04-15/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ],
    "beta blockers": [
        {
            "name": "OpenSAFELY Beta blockers",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/beta-blockers/2020-04-15/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ],
    "mras": [
        {
            "name": "OpenSAFELY Spironolactone (MRA)",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/spironolactone/2020-05-06/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ],
    "metformin": [
        {
            "name": "OpenSAFELY Antidiabetic Drugs (inc. Metformin)",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/antidiabetic-drugs/2020-07-16/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ],
    "glp1 agonists": [
        {
            "name": "OpenSAFELY GLP-1 receptor agonists",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/glp1s/2020-04-15/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ],
    "doacs": [
        {
            "name": "QOF Direct Oral Anticoagulants (DOAC_COD)",
            "org":  "nhsd-primary-care-domain-refsets",
            "url":  "https://www.opencodelists.org/codelist/nhsd-primary-care-domain-refsets/doac_cod/20250912/download.csv",
            "intent": "QOF_Register",
            "category": "Medication"
        },
        {
            "name": "OpenSAFELY DOACs",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/doacs/2020-04-15/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ],
    "warfarin": [
        {
            "name": "OpenSAFELY Warfarin",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/warfarin/2020-04-15/download.csv",
            "intent": "Epidemiology",
            "category": "Medication"
        }
    ]
}