from src.state import NICEState, CandidateCode, ValidatedCode, Justification

DUMMY_STATE: NICEState = {
    "research_question": "Obesity with type 2 diabetes and hypertension",

    "primary_condition": "Type 2 diabetes mellitus with obesity and hypertension",
    "concept_type": "diagnosis",
    "snomed_top_hierarchy": "Clinical Finding",
    "related_conditions": [
        "Metabolic syndrome",
        "Insulin resistance",
        "Obese type 2 diabetic",
        "Hypertensive disorder"
    ],
    "explicit_exclusions": [
        "Type 1 diabetes mellitus",
        "Secondary hypertension",
        "Gestational diabetes",
        "Morbid obesity with alveolar hypoventilation"
    ],
    "relevant_guidelines": [
        "NICE NG28 - Type 2 diabetes in adults",
        "NICE NG136 - Hypertension in adults",
        "NICE NG246 - Obesity: identification, assessment and management",
        "QOF Business Rules 2025/26 - DM and HYP rulesets"
    ],
    "suggested_validation_sources": [
        "type 2 diabetes obesity",
        "hypertension diabetes primary care register",
        "obese diabetic QOF",
        "T2DM hypertension codelist"
    ],
    "search_terms": [
        "Type 2 diabetes mellitus",
        "T2DM",
        "Non-insulin dependent diabetes",
        "Obesity",
        "Obese",
        "BMI 30+",
        "Hypertension",
        "High blood pressure",
        "Essential hypertension",
        "Diabetic with hypertension"
    ],
    "ambiguity_notes": "Cohort description does not specify BMI threshold for obesity. Recommend clarifying whether BMI 30 or 35 is required.",

    "candidate_codes": [
        {
            "snomed_id": "44054006",
            "preferred_term": "Type 2 diabetes mellitus",
            "synonyms": ["T2DM", "Non-insulin dependent diabetes mellitus", "NIDDM"],
            "hierarchy_path": ["Clinical Finding", "Metabolic disease", "Diabetes mellitus"],
            "source": "SNOMED CT UK Edition"
        },
        {
            "snomed_id": "38341003",
            "preferred_term": "Hypertensive disorder",
            "synonyms": ["Hypertension", "High blood pressure", "HTN"],
            "hierarchy_path": ["Clinical Finding", "Cardiovascular finding", "Hypertensive disorder"],
            "source": "SNOMED CT UK Edition"
        },
        {
            "snomed_id": "414916001",
            "preferred_term": "Obesity",
            "synonyms": ["Obese", "BMI 30+", "Overweight and obese"],
            "hierarchy_path": ["Clinical Finding", "finding of BMI", "Obesity"],
            "source": "SNOMED CT UK Edition"
        },
        {
            "snomed_id": "473893008",
            "preferred_term": "Obese type 2 diabetic",
            "synonyms": ["Obese T2DM", "Diabetes with obesity"],
            "hierarchy_path": ["Clinical Finding", "Metabolic disease", "Diabetes mellitus"],
            "source": "OpenCodelists"
        },
        {
            "snomed_id": "368581000119106",
            "preferred_term": "Hypertension in obese patient",
            "synonyms": ["Obesity-related hypertension"],
            "hierarchy_path": ["Clinical Finding", "Cardiovascular finding", "Hypertensive disorder"],
            "source": "SNOMED CT UK Edition"
        }
    ],

    "validated_codes": [
        {
            "snomed_id": "44054006",
            "preferred_term": "Type 2 diabetes mellitus",
            "confidence_score": 0.97,
            "opencodelists_match": True,
            "qof_match": True,
            "semantic_score": 0.96,
            "found_in_codelists": ["QOF DM ruleset", "NHSD T2DM refset", "OpenCodelists T2DM"],
            "is_nhsd_refset": True,
            "found_count": 12
        },
        {
            "snomed_id": "38341003",
            "preferred_term": "Hypertensive disorder",
            "confidence_score": 0.91,
            "opencodelists_match": True,
            "qof_match": True,
            "semantic_score": 0.89,
            "found_in_codelists": ["QOF HYP ruleset", "NHSD Hypertension refset"],
            "is_nhsd_refset": True,
            "found_count": 9
        },
        {
            "snomed_id": "414916001",
            "preferred_term": "Obesity",
            "confidence_score": 0.85,
            "opencodelists_match": True,
            "qof_match": False,
            "semantic_score": 0.83,
            "found_in_codelists": ["OpenCodelists Obesity", "NHSD Obesity refset"],
            "is_nhsd_refset": True,
            "found_count": 7
        },
        {
            "snomed_id": "473893008",
            "preferred_term": "Obese type 2 diabetic",
            "confidence_score": 0.61,
            "opencodelists_match": True,
            "qof_match": False,
            "semantic_score": 0.58,
            "found_in_codelists": ["OpenCodelists T2DM obesity"],
            "is_nhsd_refset": False,
            "found_count": 3
        },
        {
            "snomed_id": "368581000119106",
            "preferred_term": "Hypertension in obese patient",
            "confidence_score": 0.38,
            "opencodelists_match": False,
            "qof_match": False,
            "semantic_score": 0.35,
            "found_in_codelists": [],
            "is_nhsd_refset": False,
            "found_count": 1
        }
    ],
    "low_confidence_codes": ["368581000119106"],
    "iteration_count": 1,
    "routing_decision": "proceed_to_justification",

    "justifications": [
        {
            "snomed_id": "44054006",
            "preferred_term": "Type 2 diabetes mellitus",
            "justification_text": "This code is the primary identifier for type 2 diabetes mellitus in UK primary care and is the core concept in this cohort definition. It is included in the QOF DM register ruleset and the NHS Digital curated T2DM reference set, confirming its use as the standard identifier across NHS systems. All patients in this cohort must carry this code or a direct descendant to be included [NICE NG28 p.4; QOF DM001].",
            "source_document": "QOF DM ruleset; NHSD T2DM refset; OpenCodelists T2DM [NHS Digital curated refset]",
            "source_chunk": "Retrieved from: NICE NG28 - Type 2 diabetes in adults; QOF Business Rules 2025/26",
            "confidence_score": 0.97,
            "tier": "tier_1",
            "qof_match": True,
            "opencodelists_match": True,
            "found_in_codelists": ["QOF DM ruleset", "NHSD T2DM refset", "OpenCodelists T2DM"],
            "is_nhsd_refset": True
        },
        {
            "snomed_id": "38341003",
            "preferred_term": "Hypertensive disorder",
            "justification_text": "This code captures the hypertension component of the cohort and is the standard term used across UK primary care EHR systems including EMIS and SystmOne. It appears in the QOF HYP register ruleset and the NHS Digital hypertension reference set, confirming broad NHS usage. Patients carrying this code alongside T2DM and obesity codes satisfy the full co-morbidity definition [NICE NG136 p.6; QOF HYP001].",
            "source_document": "QOF HYP ruleset; NHSD Hypertension refset [NHS Digital curated refset]",
            "source_chunk": "Retrieved from: NICE NG136 - Hypertension in adults; QOF Business Rules 2025/26",
            "confidence_score": 0.91,
            "tier": "tier_1",
            "qof_match": True,
            "opencodelists_match": True,
            "found_in_codelists": ["QOF HYP ruleset", "NHSD Hypertension refset"],
            "is_nhsd_refset": True
        },
        {
            "snomed_id": "414916001",
            "preferred_term": "Obesity",
            "justification_text": "This code identifies the obesity component of the cohort and is the preferred SNOMED CT term for BMI-defined obesity in UK primary care. It is included in the NHS Digital obesity reference set and is widely used in OpenCodelists obesity cohort definitions. Note that this code does not encode a specific BMI threshold and additional filtering on BMI observable entity codes may be required depending on the study protocol [NICE NG246 p.8].",
            "source_document": "OpenCodelists Obesity; NHSD Obesity refset [NHS Digital curated refset]",
            "source_chunk": "Retrieved from: NICE NG246 - Obesity: identification, assessment and management",
            "confidence_score": 0.85,
            "tier": "tier_1",
            "qof_match": False,
            "opencodelists_match": True,
            "found_in_codelists": ["OpenCodelists Obesity", "NHSD Obesity refset"],
            "is_nhsd_refset": True
        },
        {
            "snomed_id": "473893008",
            "preferred_term": "Obese type 2 diabetic",
            "justification_text": "This combined concept code captures patients recorded with both obesity and T2DM under a single SNOMED term, which may occur in older EHR records. It is found in OpenCodelists T2DM obesity cohort definitions but is not present in the NHS Digital curated refsets, suggesting it is a supplementary rather than primary identifier. Include as a secondary code to capture legacy records but do not use as the sole identifier for this cohort.",
            "source_document": "OpenCodelists T2DM obesity",
            "source_chunk": "Retrieved from: NICE NG28 - Type 2 diabetes in adults",
            "confidence_score": 0.61,
            "tier": "tier_2",
            "qof_match": False,
            "opencodelists_match": True,
            "found_in_codelists": ["OpenCodelists T2DM obesity"],
            "is_nhsd_refset": False
        },
        {
            "snomed_id": "368581000119106",
            "preferred_term": "Hypertension in obese patient",
            "justification_text": "This code specifically captures hypertension recorded in the context of obesity, but its use in UK primary care EHRs is limited and it does not appear in any NHS Digital curated refset or major OpenCodelists cohort definition. Its inclusion may over-constrain the cohort by excluding patients whose hypertension and obesity were recorded separately. For supplementary use only and should not be used as the sole identifier for this cohort.",
            "source_document": "No reference codelist match found - human review required",
            "source_chunk": "No guideline text retrieved - clinical reasoning only",
            "confidence_score": 0.38,
            "tier": "tier_3",
            "qof_match": False,
            "opencodelists_match": False,
            "found_in_codelists": [],
            "is_nhsd_refset": False
        }
    ],

    "human_review_flag": True,
    "human_review_reason": "Tier 2 and Tier 3 codes require clinical review before inclusion.",
    "human_feedback": None,
    "final_output": None
}
