"""
Node 1 + Node 1b: Query Understanding + Synonym Enrichment — DYNAMIC VERSION

Node 1:  GPT-4o parses ANY patient cohort description into structured state
         No condition-specific knowledge hardcoded
         Infers: concept_type, snomed_hierarchy, relevant_guidelines,
                 suggested_validation_sources, explicit_exclusions

Node 1b: NHS Terminology Server enriches search_terms with official synonyms
         No LLM  — authoritative NHS synonyms only
         Non-fatal — falls back to LLM terms if API unavailable

Phase 2: Advanced RAG Retrieval uses the structured data to apply dynamic demographic, 
         QOF, and exclusion shields before fetching context from ChromaDB.
"""
import json
import re
import sys
import os
import httpx
from dotenv import load_dotenv

load_dotenv()   

# --- DYNAMIC PATHING ---
# Dynamically locate the project root directory so the script works on any machine
# regardless of where the terminal is opened.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
sys.path.append(PROJECT_ROOT)

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.vectorstores import Chroma
from src.state import NICEState
from src.utils.fhir_client import _get_headers, CONCEPT_TYPE_ROOTS, FHIR_BASE
from src.rag.retriever import advanced_retrieval

# --- DYNAMIC DATABASE PATH ---
# Points exactly to the GitHub folder structure: data/vectorstore/methodology_db_openai
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "data", "vectorstore", "methodology_db_openai")
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

# INITIALIZE MODELS & VECTOR DATABASE
print("[*] Initializing OpenAI models & connecting to ChromaDB...")

# We MUST use the exact same embedding model used during Colab ingestion
embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME)
vector_db = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embeddings)

# Initialize GPT-4o for clinical reasoning
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1000)

# LLM SYSTEM PROMPT & PARSING

SYSTEM_PROMPT = """
# ROLE
You are a clinical informatics expert specializing in SNOMED CT and UK primary care coding. 
Your task is to parse a plain English patient cohort description into a structured JSON object for an automated SNOMED CT search pipeline.

# CLINICAL REASONING INSTRUCTIONS
Use your medical expertise to infer standard pharmacological treatments, relevant lab results, and related co-morbidities, even if the user does not explicitly state them. 

# FIELD DEFINITIONS & RULES

## 1. Core Classification
* primary_condition: The single most important clinical concept (string).
* concept_type: EXACTLY ONE OF: [diagnosis, observation, procedure, finding, lab_result, medication, demographic, situation, mixed]. Default to "diagnosis" for diseases.
* snomed_top_hierarchy: EXACTLY ONE OF: [Clinical Finding, Procedure, Observable Entity, Substance, Body Structure, Situation, Mixed].
* target_demographic: "adult" or "pediatric" (default "adult").
* qof_domain_prefix: Official UK QOF abbreviation (e.g., "DM", "HYP"). Empty string if unknown.

## 2. Inclusions (What to Search For)
* search_terms: Array of 6-10 SNOMED CT terms for the primary condition. Include exact phrases, synonyms, pre-2013 legacy UK EHR terms, and acronyms. STRICTLY clinical diagnoses/findings. DO NOT put medications or lab tests here.
* related_conditions: Array of closely related co-morbidities.
* relevant_medications: Array of specific, singular generic active ingredients (e.g., "Dapagliflozin"). NO plural drug classes (e.g., avoid "Beta-blockers"). Empty if none.
* relevant_observations: Array of related lab tests, imaging, or vital signs (e.g., "HbA1c"). Empty if none.

## 3. Exclusions (What to Filter Out)
* excluded_diagnoses: Array of substrings to reject (e.g., "Type 1", "preserved"). CRITICAL: Must NOT include the primary condition.
* excluded_medications: Array of substrings to reject false-positive drug matches. Do NOT put indicated treatments here.
* excluded_observations: Array of substrings to reject false-positive lab matches.

## 4. Metadata & Validation
* relevant_guidelines: Array of highly confident NICE/NHS guidelines (e.g., "NICE NG106"). Empty [] if unsure. Do not hallucinate.
* suggested_validation_sources: Array of 3-5 plain English search terms for OpenCodelists.org (e.g., "heart failure QOF").
* ambiguity_notes: Note any clinical ambiguity in the user's description (e.g., missing age threshold). Empty string if none.

# OUTPUT FORMAT
Return ONLY a valid JSON object containing exactly the 14 keys defined above.
"""

def _parse_llm_response(content: str) -> dict:
    """
    Parse LLM response to JSON.
    Handles cases where LLM wraps JSON in prose or markdown code blocks.
    """
    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strip markdown code blocks if present
    # e.g. ```json { ... } ```
    cleaned = re.sub(r"```(?:json)?\s*", "", content)
    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: extract first { ... } block
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Complete failure — return safe defaults
    print("[query_understanding] WARNING: Could not parse LLM JSON response")
    return {}

VALID_CONCEPT_TYPES = {
    "diagnosis", "observation", "procedure", "finding",
    "lab_result", "medication", "demographic", "situation", "mixed"
}

VALID_SNOMED_HIERARCHIES = {
    "Clinical Finding", "Procedure", "Observable Entity",
    "Substance", "Body Structure", "Situation", "Mixed"
}


def _validate_parsed_output(parsed: dict, research_question: str) -> dict:
    """
    Validate and fill defaults for parsed LLM output.
    Ensures all required state fields are present even if LLM omits them.
    """
    primary = parsed.get("primary_condition", "")
    if not primary:
        # Fallback: use first 50 chars of research question
        primary = research_question[:50].strip()
        print(f"[query_understanding] WARNING: No primary_condition from LLM, "
              f"using fallback: '{primary}'")

    # Validate concept_type — fall back to "diagnosis" if LLM hallucinates a value
    concept_type = parsed.get("concept_type", "diagnosis")
    if concept_type not in VALID_CONCEPT_TYPES:
        print(f"[query_understanding] WARNING: Invalid concept_type '{concept_type}', "
              f"falling back to 'diagnosis'")
        concept_type = "diagnosis"

    # Validate snomed_top_hierarchy — fall back if LLM invents a value
    snomed_hierarchy = parsed.get("snomed_top_hierarchy", "Clinical Finding")
    if snomed_hierarchy not in VALID_SNOMED_HIERARCHIES:
        print(f"[query_understanding] WARNING: Invalid snomed_top_hierarchy "
              f"'{snomed_hierarchy}', falling back to 'Clinical Finding'")
        snomed_hierarchy = "Clinical Finding"

    return {
        "primary_condition":             primary,
        "concept_type":                  parsed.get("concept_type", "diagnosis"),
        "snomed_top_hierarchy":          parsed.get("snomed_top_hierarchy",
                                                    "Clinical Finding"),
        "related_conditions":            parsed.get("related_conditions", []),
        "relevant_observations":         parsed.get("relevant_observations"),
        "relevant_medications":          parsed.get("relevant_medications"),
        "excluded_diagnoses":            parsed.get("excluded_diagnoses", []),
        "excluded_medications":          parsed.get("excluded_medications", []),
        "excluded_observations":         parsed.get("excluded_observations", []),
        "relevant_guidelines":           parsed.get("relevant_guidelines", []),
        "suggested_validation_sources":  parsed.get("suggested_validation_sources",
                                                    [primary]),
        "search_terms":                  parsed.get("search_terms", [primary]),
        "ambiguity_notes":               parsed.get("ambiguity_notes", "")
        
    }


async def _enrich_with_nhs_synonyms(
    initial_search_terms: list[str],
    primary_condition: str,
    explicit_exclusions: list[str],
    concept_type: str = "diagnosis"
) -> list[str]:
    enriched = list(initial_search_terms)
    try:
        headers  = _get_headers()   # reuse from snomed_search_node or inline
        root_id  = CONCEPT_TYPE_ROOTS.get(concept_type, "404684003")

        async with httpx.AsyncClient(base_url=FHIR_BASE, timeout=15.0) as client:
            # Step 1: find top 3 concept IDs
            resp = await client.get("/ValueSet/$expand", headers=headers, params={
                "url":    f"http://snomed.info/sct?fhir_vs=isa/{root_id}",
                "filter": primary_condition,
                "count":  3
            })
            hits = resp.json().get("expansion", {}).get("contains", [])

            added = 0
            for hit in hits:
                concept_id = hit.get("code")
                if not concept_id:
                    continue

                # Step 2: get synonyms via CodeSystem/$lookup
                syn_resp = await client.get("/CodeSystem/$lookup", headers=headers, params={
                    "system":   "http://snomed.info/sct",
                    "code":     concept_id,
                    "property": "designation"
                })
                for param in syn_resp.json().get("parameter", []):
                    if param.get("name") == "designation":
                        parts = {p["name"]: p for p in param.get("part", [])}
                        term  = parts.get("value", {}).get("valueString", "").strip()
                        if term and not any(t.lower() == term.lower() for t in enriched) \
                               and not any(e.lower() in term.lower() for e in explicit_exclusions):
                            enriched.append(term)
                            added += 1

        print(f"[query_understanding:1b] Added {added} NHS synonyms. Total diagnosis terms: {len(enriched)}")
    except Exception as e:
        print(f"[query_understanding:1b] Synonym enrichment failed: {e} — using LLM terms")
    return enriched

async def query_understanding_node(state: NICEState) -> dict:
    """
    The main entry point for Node 1 in the LangGraph pipeline.
    Executes reasoning, advanced RAG retrieval, and synonym enrichment.
    """
    research_question = state["research_question"]
    print(f"\n--- [PHASE 1] QUERY UNDERSTANDING STARTED ---")
    print(f"[*] Processing Query: '{research_question}'")

    # 1. LLM REASONING & DECOMPOSITION
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=research_question)]
    response = await llm.ainvoke(messages)
    parsed = _parse_llm_response(response.content)
    cleaned_data = _validate_parsed_output(parsed, research_question)

    # Validate required demographic and QOF variables, falling back to "adult" if missing
    target_demographic = cleaned_data.get("target_demographic", "adult").lower()
    qof_domain_prefix = cleaned_data.get("qof_domain_prefix", "")

    # 2. ADVANCED RAG RETRIEVAL
    # Fetch targeted context chunks using the refined retriever module
    final_docs = advanced_retrieval(cleaned_data, vector_db)

    # Build the context payload for the synthesis node
    rag_payload = ""
    found_guidelines = set(cleaned_data.get("relevant_guidelines", []))
    
    for doc in final_docs:
        # Strip the absolute Colab Drive path to obtain a clean filename
        source = os.path.basename(doc.metadata.get('source', 'Unknown'))
        filename = source.replace('.pdf', '')
        found_guidelines.add(filename)
        
        # Format the chunk clearly for the LLM
        rag_payload += f"--- Source: {filename} ---\n{doc.page_content}\n\n"

    # 3. NHS SYNONYM ENRICHMENT
    print("\n--- [PHASE 3] ENRICHING SEARCH TERMS WITH NHS API ---")
    all_exclusions = (
        cleaned_data["excluded_diagnoses"] + 
        cleaned_data["excluded_medications"] + 
        cleaned_data["excluded_observations"]
    )
    
    enriched_terms = await _enrich_with_nhs_synonyms(
        initial_search_terms=cleaned_data["search_terms"],
        primary_condition=cleaned_data["primary_condition"],
        explicit_exclusions=all_exclusions,
        concept_type=cleaned_data["concept_type"]
    )

    print("--- [NODE 1 COMPLETE] Data successfully prepared for Node 2 ---")
    print(f"[query_understanding] Final search terms : {len(enriched_terms + cleaned_data['relevant_medications'] + cleaned_data['relevant_observations'])}")
         
    # Return the enriched state dictionary matching the NICEState TypedDict
    return {
        "primary_condition":             cleaned_data["primary_condition"],
        "concept_type":                  cleaned_data["concept_type"],
        "snomed_top_hierarchy":          cleaned_data["snomed_top_hierarchy"],
        "related_conditions":            cleaned_data["related_conditions"],
        "excluded_diagnoses":            cleaned_data["excluded_diagnoses"],
        "excluded_medications":          cleaned_data["excluded_medications"],
        "excluded_observations":         cleaned_data["excluded_observations"],
        "relevant_medications":          cleaned_data["relevant_medications"],
        "relevant_observations":         cleaned_data["relevant_observations"],
        "suggested_validation_sources":  cleaned_data["suggested_validation_sources"],
        "ambiguity_notes":               cleaned_data["ambiguity_notes"],
        
        # Enriched fields
        "search_terms":                  enriched_terms,
        "relevant_guidelines":           list(found_guidelines),
        
        # Advanced RAG fields
        "qof_domain_prefix":             qof_domain_prefix,
        "target_demographic":            target_demographic,
        "rag_context":                   rag_payload.strip(),
        "rag_sources":                   list(found_guidelines),
        
        # Pipeline control fields
        "iteration_count":               0,
        "human_review_flag":             False,
        "human_feedback":                None,
        "final_output":                  None
    }
