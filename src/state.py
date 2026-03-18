from typing import TypedDict, List, Optional

class CandidateCode(TypedDict):
    snomed_id:      str
    preferred_term: str
    synonyms:       List[str]
    hierarchy_path: List[str]
    source:         str

class ValidatedCode(TypedDict):
    snomed_id:           str
    preferred_term:      str
    confidence_score:    float
    opencodelists_match: bool
    qof_match:           bool
    semantic_score:      float
    found_in_codelists:  List[str]   
    is_nhsd_refset:      bool        
    found_count:         int         

class Justification(TypedDict):
    snomed_id:           str
    preferred_term:      str
    justification_text:  str
    source_document:     str
    source_chunk:        str
    confidence_score:    float
    tier:                str
    qof_match:           bool
    opencodelists_match: bool
    found_in_codelists:  List[str]   
    is_nhsd_refset:      bool        

class NICEState(TypedDict):
    # --- Input ---
    research_question:            str

    # --- Node 1 Output ---
    primary_condition:            str
    concept_type:                 str         
    snomed_top_hierarchy:         str         
    related_conditions:           List[str]
    explicit_exclusions:          List[str]
    relevant_guidelines:          List[str]   
    suggested_validation_sources: List[str]   
    search_terms:                 List[str]
    ambiguity_notes:              str         

    # --- Node 2 Output ---
    candidate_codes:              List[CandidateCode]

    # --- Node 3 Output ---
    validated_codes:              List[ValidatedCode]
    low_confidence_codes:         List[str]
    iteration_count:              int
    routing_decision:             str

    # --- Node 4 Output ---
    justifications:               List[Justification]

    # --- Node 5: Human Review ---
    human_review_flag:            bool
    human_review_reason:          str        
    human_feedback:               Optional[str]

    # --- Final Output ---
    final_output:                 Optional[List[Justification]]
