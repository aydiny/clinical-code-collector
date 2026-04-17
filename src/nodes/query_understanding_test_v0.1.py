"""
Node 1 + Node 1b: Query Understanding + Synonym Enrichment + Advanced RAG

Phase 1: GPT-4o parses the patient cohort description into structured state, 
         using its own clinical expertise to infer medications, and extracting 
         routing keys (demographics, QOF).
Phase 2: Advanced RAG uses this data to apply dynamic demographic/QOF shields 
         safely in Python before fetching.
Node 1b: NHS Terminology Server enriches search_terms with official synonyms.
"""
import json
import re
import sys
import os
import httpx
from dotenv import load_dotenv
load_dotenv()   

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.vectorstores import Chroma
from src.state import NICEState
from src.utils.fhir_client import _get_headers, CONCEPT_TYPE_ROOTS, FHIR_BASE

CHROMA_DB_DIR = "data/vectorstore/methodology_db_openai"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

# -------------------------------------------------------------------
# LLM — GPT-4o for clinical reasoning quality
# -------------------------------------------------------------------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1000)

# --- FILE MAPPING DICTIONARY (Bihter's Router) ---
CONDITION_TO_FILE = {
    "Type 2 Diabetes": "NG28_type_2_diabetes.pdf",
    "Diabetes": "NG28_type_2_diabetes.pdf",
    "Obesity": "NG246_obesity.pdf",
    "Hypertension": "NG136_hypertension.pdf"
}
QOF_FILE = "qof_combined.pdf"

# -------------------------------------------------------------------
# System Prompt — Fully Restored Original Instructions
# -------------------------------------------------------------------
SNOMED_HIERARCHY_CONTEXT = """
SNOMED CT UK Edition — Top Level Hierarchies (stable reference):
- Clinical Finding:   diagnoses, disorders, symptoms, observations
- Procedure:          operations, therapies, investigations, screenings
- Observable Entity:  measurable parameters, things that can be tested
- Body Structure:     anatomical locations and structures
- Substance:          drugs, chemical compounds, biologics, vaccines
- Situation:          context-dependent findings
- Qualifier Value:    severity, laterality, course modifiers
- Mixed:              use ONLY when cohort genuinely spans two or more
"""

SYSTEM_PROMPT = """
You are a clinical informatics expert specialising in SNOMED CT and 
UK primary care coding. A user will describe a patient cohort in 
plain English. Your job is to parse this into structured components
for an automated SNOMED CT code search pipeline.

You must reason about the clinical domain using your own clinical expertise.
You will encounter diagnoses, observations, procedures, medications, 
lab results, demographic criteria, and combinations of these.

Return a VALID JSON object with EXACTLY these keys:

{
  "primary_condition": "string — the single most important clinical concept to search for",
  "concept_type": "diagnosis | observation | procedure | finding | lab_result | medication | demographic | situation | mixed",
  "snomed_top_hierarchy": "Clinical Finding | Procedure | Observable Entity | Substance | Body Structure | Situation | Mixed",
  "related_conditions": ["list of closely related conditions that may share codes"],

  "excluded_diagnoses": ["list of SUBSTRINGS to filter out false-positive terminology matches (e.g., 'preserved' or 'Type 1'). DO NOT put concepts here if you need their SNOMED codes! Leave empty [] if none."],
  "excluded_medications": ["list of SUBSTRINGS to filter out false-positive medication terminology matches. CRITICAL: DO NOT list contraindicated or 'already treated' drugs here because we need to fetch their codes! Leave empty [] if none."],    
  "excluded_observations": ["list of SUBSTRINGS to filter out false-positive lab terminology matches. Leave empty [] if none."],

  "relevant_medications": ["list of specific, singular generic medication names or active ingredients (e.g., 'Dapagliflozin', 'Bisoprolol'). CRITICAL: Do NOT use plural drug classes (like 'SGLT2 inhibitors') because SNOMED text search will fail to find them. Leave empty [] if none."],
  "relevant_observations": ["list of relevant lab tests, imaging results, or vital signs (e.g., 'LVEF', 'HbA1c', 'Blood pressure'). Leave empty [] if none."],
  
  "relevant_guidelines": ["list of NICE/NHS guidelines likely relevant to this cohort"],
  "suggested_validation_sources": ["list of 3-5 plain English search terms to find relevant codelists on OpenCodelists.org"],
  "search_terms": ["list of 6-10 SNOMED CT search terms (synonyms, legacy terms, acronyms)"],
  "ambiguity_notes": "string — note any ambiguities in the cohort description",

  "target_demographic": "adult | pediatric (infer from query, default to adult)",
  "qof_domain_prefix": "official UK QOF abbreviation (e.g., 'DM' for Diabetes, 'HYP' for Hypertension) or empty string if unknown"
}

IMPORTANT RULES:
1. EXCLUSIONS: think like a clinician. ALWAYS include standard medical acronyms. CRITICAL: NEVER include the primary target condition in this list.
2. relevant_medications: USE YOUR CLINICAL EXPERTISE to suggest standard pharmacological treatments for the primary condition.
3. search_terms: STRICTLY CLINICAL DIAGNOSES and finding SYNONYMS. CRITICAL: NEVER include medication names, lab test names, or generic metadata in this list. 
4. target_demographic: If the patient is a child/infant, output 'pediatric'. If unspecified, default to 'adult'.
"""


def _parse_llm_response(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    print("[query_understanding] WARNING: Could not parse LLM JSON response")
    return {}

def _validate_parsed_output(parsed: dict, research_question: str) -> dict:
    """Ensure all expected keys exist even if the LLM hallucinates."""
    primary = parsed.get("primary_condition", "")
    if not primary:
        primary = research_question[:50].strip()

    return {
        "primary_condition":             primary,
        "concept_type":                  parsed.get("concept_type", "diagnosis"),
        "snomed_top_hierarchy":          parsed.get("snomed_top_hierarchy", "Clinical Finding"),
        "related_conditions":            parsed.get("related_conditions", []),
        "relevant_observations":         parsed.get("relevant_observations", []),
        "relevant_medications":          parsed.get("relevant_medications", []),
        "excluded_diagnoses":            parsed.get("excluded_diagnoses", []),
        "excluded_medications":          parsed.get("excluded_medications", []),
        "excluded_observations":         parsed.get("excluded_observations", []),
        "relevant_guidelines":           parsed.get("relevant_guidelines", []),
        "suggested_validation_sources":  parsed.get("suggested_validation_sources", [primary]),
        "search_terms":                  parsed.get("search_terms", [primary]),
        "ambiguity_notes":               parsed.get("ambiguity_notes", ""),
        "target_demographic":            parsed.get("target_demographic", "adult").lower(),
        "qof_domain_prefix":             parsed.get("qof_domain_prefix", "")
    }

# -------------------------------------------------------------------
# ADVANCED RAG UTILITIES (Bihter's Method - Upgraded for Path Safety)
# -------------------------------------------------------------------
def clean_boilerplate_text(text: str) -> str:
    noise = [
        "© NICE 2026. All rights reserved.",
        "Subject to Notice of rights",
        "(https://www.nice.org.uk/terms-and- conditions#notice-of-rights)",
        "(https://www.nice.org.uk/terms-and-conditions#notice-of-rights)",
        "Return to recommendations",
        "Why the committee made the recommendations",
        "How the recommendations might affect practice"
    ]
    cleaned_text = text
    for n in noise:
        cleaned_text = cleaned_text.replace(n, "")
    
    lines = [line for line in cleaned_text.split('\n') if not line.strip().startswith("Page ") and "of 1" not in line]
    return " ".join(lines).strip()

def get_relevant_pdfs(condition_name: str, pdf_folder: str = "pdf_docs") -> list[str]:
    """Returns a list of all matching files (fixes the early-return bug)."""
    if not condition_name:
        return []
        
    matches = set()
    # 1. Check exact dictionary map
    for key, filename in CONDITION_TO_FILE.items():
        if key.lower() in condition_name.lower():
            matches.add(filename)
            
    # 2. Dynamic Scan
    print(f"[*] Scanning '{pdf_folder}' dynamically for '{condition_name}'...")
    search_terms = condition_name.lower().replace("-", " ").split()
    
    if os.path.exists(pdf_folder):
        for filename in os.listdir(pdf_folder):
            if filename.endswith(".pdf") and filename != QOF_FILE:
                name_lower = filename.lower().replace("_", " ")
                # If any major word from the condition is in the filename
                if any(term in name_lower for term in search_terms if len(term) > 4):
                    matches.add(filename)
                    
    return list(matches)

def advanced_retrieval(extracted_info: dict, vector_db: Chroma) -> list:
    print("\n--- [PHASE 2] ADVANCED RAG RETRIEVAL STARTED ---")
    primary = extracted_info.get('primary_condition', '')
    related_conditions = extracted_info.get('related_conditions', [])
    qof_prefix = extracted_info.get('qof_domain_prefix', '')
    target_demographic = extracted_info.get('target_demographic', 'adult').lower()
    
    exclusions = (
        extracted_info.get('excluded_diagnoses', []) + 
        extracted_info.get('excluded_medications', []) + 
        extracted_info.get('excluded_observations', [])
    )
        
    clinical_allowed_files = get_relevant_pdfs(primary)
    for related in related_conditions:
        clinical_allowed_files.extend(get_relevant_pdfs(related))
        
    clinical_allowed_files = list(set(clinical_allowed_files))
    print(f"[*] Allowed clinical source files: {clinical_allowed_files}")
    
    all_retrieved_documents = []
    demo_prefix = "Pediatric" if target_demographic == "pediatric" else "Adult"
    
    # ── PYTHON FILTERING APPROACH (Bulletproof against slashes/paths) ──
    # QUERY 1: QOF Specific Query
    if primary:
        qof_query = f"QOF indicator business rules register {qof_prefix} {primary}"
        raw_qof_docs = vector_db.similarity_search(qof_query, k=5)
        # Filter for QOF safely in Python
        valid_qof = [d for d in raw_qof_docs if QOF_FILE in d.metadata.get("source", "")]
        all_retrieved_documents.extend(valid_qof)
        
        # QUERY 2: Clinical Definitions
        clin_query = f"{demo_prefix} Definitions, diagnostic criteria, clinical management rules {primary}"
        raw_clin_docs = vector_db.max_marginal_relevance_search(clin_query, k=10, fetch_k=25, lambda_mult=0.5)
        
        if clinical_allowed_files:
            valid_clin = [d for d in raw_clin_docs if any(f in d.metadata.get("source", "") for f in clinical_allowed_files)]
            all_retrieved_documents.extend(valid_clin)
        else:
            all_retrieved_documents.extend(raw_clin_docs[:5]) # Fallback
    
    # QUERY 3: Related Conditions
    for related in related_conditions:
        rel_query = f"{demo_prefix} Diagnostic criteria clinical management {related}"
        raw_rel_docs = vector_db.max_marginal_relevance_search(rel_query, k=5, fetch_k=15, lambda_mult=0.5)
        
        if clinical_allowed_files:
            valid_rel = [d for d in raw_rel_docs if any(f in d.metadata.get("source", "") for f in clinical_allowed_files)]
            all_retrieved_documents.extend(valid_rel)
        else:
            all_retrieved_documents.extend(raw_rel_docs[:3])
        
    # SHIELDING & DEDUPLICATION
    unique_chunks = {}
    for doc in all_retrieved_documents:
        content_lower = doc.page_content.lower()
        source_file = doc.metadata.get('source', '')
        
        # QOF Shield
        if "qof_combined" in source_file and qof_prefix and qof_prefix.lower() not in content_lower:
            continue 

        # Demographic Shield
        has_pediatric = any(t in content_lower for t in ["children", "young person", "paediatric", "pediatric", "child"])
        has_adult = "adult" in content_lower

        if target_demographic == "pediatric" and has_adult and not has_pediatric: continue
        if target_demographic == "adult" and has_pediatric and not has_adult: continue 

        # Exclusion Shield
        should_exclude = any(exc.strip().lower() in content_lower for exc in exclusions if exc.strip())
        if should_exclude: continue
            
        doc_snippet = doc.page_content[:100]
        if doc_snippet not in unique_chunks:
            doc.page_content = clean_boilerplate_text(doc.page_content)
            unique_chunks[doc_snippet] = doc
            
    print(f"[*] Post-shielding chunks retained: {len(unique_chunks)}")
    return list(unique_chunks.values())

# -------------------------------------------------------------------
# NHS FHIR SYNONYM ENRICHMENT
# -------------------------------------------------------------------
async def _enrich_with_nhs_synonyms(initial_search_terms: list[str], primary_condition: str, explicit_exclusions: list[str], concept_type: str = "diagnosis") -> list[str]:
    enriched = list(initial_search_terms)
    try:
        headers  = _get_headers()
        root_id  = CONCEPT_TYPE_ROOTS.get(concept_type, "404684003")

        async with httpx.AsyncClient(base_url=FHIR_BASE, timeout=15.0) as client:
            resp = await client.get("/ValueSet/$expand", headers=headers, params={"url": f"http://snomed.info/sct?fhir_vs=isa/{root_id}", "filter": primary_condition, "count": 3})
            hits = resp.json().get("expansion", {}).get("contains", [])

            for hit in hits:
                concept_id = hit.get("code")
                if not concept_id: continue

                syn_resp = await client.get("/CodeSystem/$lookup", headers=headers, params={"system": "http://snomed.info/sct", "code": concept_id, "property": "designation"})
                for param in syn_resp.json().get("parameter", []):
                    if param.get("name") == "designation":
                        parts = {p["name"]: p for p in param.get("part", [])}
                        term  = parts.get("value", {}).get("valueString", "").strip()
                        if term and not any(t.lower() == term.lower() for t in enriched) and not any(e.lower() in term.lower() for e in explicit_exclusions):
                            enriched.append(term)
    except Exception as e:
        print(f"[query_understanding:1b] Synonym enrichment failed: {e}")
    return enriched

# -------------------------------------------------------------------
# MAIN NODE EXECUTION
# -------------------------------------------------------------------
async def query_understanding_node(state: NICEState) -> dict:
    research_question = state["research_question"]
    print(f"\n--- [PHASE 1] QUERY UNDERSTANDING STARTED ---")

    # 1. LLM REASONING & DECOMPOSITION
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Patient cohort description:\n{research_question}")
    ]
    
    print("[query_understanding] Calling GPT-4o for clinical extraction...")
    response = await llm.ainvoke(messages)
    parsed = _parse_llm_response(response.content)
    cleaned = _validate_parsed_output(parsed, research_question)
    
    if cleaned["ambiguity_notes"]:
        print(f"[query_understanding] ⚠️  AMBIGUITY: {cleaned['ambiguity_notes']}")

    # 2. ADVANCED RAG RETRIEVAL
    guideline_context = "No relevant guidelines retrieved."
    guideline_docs = []
    
    try:
        db = Chroma(
            persist_directory=CHROMA_DB_DIR, 
            embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME)
        )
        
        guideline_docs = advanced_retrieval(cleaned, db)
        
        # Format chunks into XML style for Node 4
        if guideline_docs:
            structured_context = ""
            for i, doc in enumerate(guideline_docs):
                page_num = doc.metadata.get("page", "Unknown Page")
                source_file = os.path.basename(str(doc.metadata.get("source", "Unknown Source")))
                
                structured_context += f"\n<CHUNK id='{i}' source='{source_file}' page='{page_num}'>\n"
                structured_context += doc.page_content
                structured_context += f"\n</CHUNK>\n"
            
            guideline_context = structured_context
            
    except Exception as e:
        print(f"[query_understanding] Advanced RAG retrieval failed: {e}")

    # 3. NHS SYNONYM ENRICHMENT
    print("\n--- [PHASE 3] ENRICHING SEARCH TERMS WITH NHS API ---")
    all_exclusions = cleaned["excluded_diagnoses"] + cleaned["excluded_medications"] + cleaned["excluded_observations"]

    enriched_terms = await _enrich_with_nhs_synonyms(
        initial_search_terms=cleaned["search_terms"],
        primary_condition=cleaned["primary_condition"],
        explicit_exclusions=all_exclusions,
        concept_type=cleaned["concept_type"]
    )

    print(f"\n[query_understanding] ── Complete ──")

    return {
        "primary_condition":             cleaned["primary_condition"],
        "concept_type":                  cleaned["concept_type"],
        "snomed_top_hierarchy":          cleaned["snomed_top_hierarchy"],
        "related_conditions":            cleaned["related_conditions"],
        "excluded_diagnoses":            cleaned["excluded_diagnoses"],
        "excluded_medications":          cleaned["excluded_medications"],
        "excluded_observations":         cleaned["excluded_observations"],
        
        # Restored properly!
        "relevant_medications":          cleaned["relevant_medications"],
        "relevant_observations":         cleaned["relevant_observations"],
        
        "relevant_guidelines":           cleaned["relevant_guidelines"],
        "suggested_validation_sources":  cleaned["suggested_validation_sources"],
        "ambiguity_notes":               cleaned["ambiguity_notes"],
        "search_terms":                  enriched_terms,
        
        # New RAG Context for Node 4
        "rag_context":                   guideline_context,  
        "rag_sources":                   list(set([os.path.basename(d.metadata.get("source", "")) for d in guideline_docs])),
        
        "iteration_count":               0,
        "human_review_flag":             False,
        "human_feedback":                None,
        "final_output":                  None
    }