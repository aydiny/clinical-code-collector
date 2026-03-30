# config/opencodelists_index.py
# All entries verified as SNOMED CT, independent of NHS Digital TRUD (L2)

OPENCODELISTS_INDEX = {

    # ── Heart Failure (generic) ──────────────────────────────────────────────
    "heart failure": [
        {
            "name": "PINCER Heart Failure (SNOMED)",
            "org":  "pincer",
            "url":  "https://www.opencodelists.org/codelist/pincer/hf/v1.8/download.csv",
        },
        {
            "name": "REDUCEHF Heart Failure Broad (SNOMED)",
            "org":  "reducehf",
            "url":  "https://www.opencodelists.org/codelist/reducehf/heart-failure-broad-for-excluding-people/17bd3b08/download.csv",
        },
        {
            "name": "REDUCEHF Heart Failure A&E (SNOMED)",
            "org":  "reducehf",
            "url":  "https://www.opencodelists.org/codelist/reducehf/heart-failure-ae/5ad354c5/download.csv",
        },
    ],

    # ── HFrEF ────────────────────────────────────────────────────────────────
    # Note: no independent SNOMED HFrEF codelist exists outside NHSD
    # L2 TRUD covers this — no L1 entry needed

    # ── Atrial Fibrillation ──────────────────────────────────────────────────
    "atrial fibrillation": [
        {
            "name": "QCovid Atrial Fibrillation (SNOMED)",
            "org":  "qcovid",
            "url":  "https://www.opencodelists.org/codelist/qcovid/has_atrial_fibrillation/2a4910da/download.csv",
        },
    ],

    # ── Diabetes ─────────────────────────────────────────────────────────────
    "diabetes mellitus": [
        {
            "name": "OpenSAFELY Diabetes (SNOMED)",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/diabetes-snomed/2020-04-15/download.csv",
        },
    ],
    "type 2 diabetes": [
        {
            "name": "OpenSAFELY Diabetes (SNOMED)",
            "org":  "opensafely",
            "url":  "https://www.opencodelists.org/codelist/opensafely/diabetes-snomed/2020-04-15/download.csv",
        },
    ],
}