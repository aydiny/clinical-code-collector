"""
Node 1 + Node 1b: Query Understanding + Synonym Enrichment + Advanced RAG (INTEGRATED)

Node 1:  GPT-4o parses ANY patient cohort description into a structured state.
         It infers the condition type, SNOMED hierarchy, relevant guidelines, 
         explicit exclusions, target demographic, and QOF domain prefix.

Node 1b: NHS Terminology Server enriches search_terms with official synonyms.

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

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.vectorstores import Chroma
#from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from src.state import NICEState
from src.utils.fhir_client import _get_headers, CONCEPT_TYPE_ROOTS, FHIR_BASE

CHROMA_DB_DIR = "data/vectorstore/methodology_db_openai"

# -------------------------------------------------------------------
# INITIALIZE MODELS & VECTOR DATABASE
# -------------------------------------------------------------------
print("[*] Initializing local models & connecting to ChromaDB...")
#embeddings = OllamaEmbeddings(model="nomic-embed-text")
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
#vector_db = Chroma(persist_directory="vector_db/methodology_db", embedding_function=embeddings)

vector_db = Chroma(
                persist_directory=CHROMA_DB_DIR, 
                embedding_function=OpenAIEmbeddings(model="text-embedding-3-small")
            )
            
# Initialize GPT-4o for reasoning
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1000)

# --- FILE MAPPING DICTIONARY ---
# This acts as our "Fast Track" exact mapping to prevent irrelevant searches.
CONDITION_TO_FILE = {
    "Type 2 Diabetes Mellitus": "NG28_type_2_diabetes.pdf",
    "Obesity": "NG246_obesity.pdf",
    "Hypertension": "NG136_hypertension.pdf"
}
QOF_FILE = "qof_combined.pdf"

# -------------------------------------------------------------------
# ADVANCED RAG UTILITIES
# -------------------------------------------------------------------

def clean_boilerplate_text(text: str) -> str:
    """
    Cleans up repetitive boilerplate texts, headers, and footers from NICE guidelines
    so they don't distract the LLM during the synthesis phase.
    """
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
    
    # Remove stray "Page X of Y" lines
    lines = [line for line in cleaned_text.split('\n') if not line.strip().startswith("Page ") and "of 1" not in line]
    return " ".join(lines).strip()

def get_relevant_pdf(condition_name: str, pdf_folder: str = "pdf_docs") -> str:
    """
    SMART DOCUMENT ROUTER:
    First checks the exact dictionary mapping. If not found, it dynamically scans 
    the pdf_docs directory to find a matching filename, preventing future bottlenecks.
    """
    if not condition_name:
        return None
        
    # 1. Fast Track: Exact Match in Dictionary
    if condition_name in CONDITION_TO_FILE:
        return CONDITION_TO_FILE[condition_name]
        
    # 2. Dynamic Fallback: Scan the folder for filenames containing the condition words
    print(f"[*] '{condition_name}' not found in dictionary. Scanning '{pdf_folder}' dynamically...")
    if not os.path.exists(pdf_folder):
        return None
        
    search_terms = condition_name.lower().replace("-", " ").split()
    
    for filename in os.listdir(pdf_folder):
        if filename.endswith(".pdf") and filename != QOF_FILE:
            name_lower = filename.lower().replace("_", " ")
            if any(term in name_lower for term in search_terms if len(term) > 4):
                print(f"[*] Auto-mapped '{condition_name}' to '{filename}' based on filename match.")
                return filename
                
    return None

def advanced_retrieval(extracted_info: dict, vector_db: Chroma) -> list:
    """
    Takes the structured output from Node 1 (GPT-4o) and performs a highly filtered, 
    MMR-based search on ChromaDB, applying Demographic, QOF, and Exclusion shields.
    """
    print("\n--- [PHASE 2] ADVANCED RAG RETRIEVAL STARTED ---")
    
    primary = extracted_info.get('primary_condition', '')
    related_conditions = extracted_info.get('related_conditions', [])
    qof_prefix = extracted_info.get('qof_domain_prefix', '')
    target_demographic = extracted_info.get('target_demographic', 'adult').lower()
    
    # Combine all explicit exclusions for the Exclusion Shield
    exclusions = (
        extracted_info.get('excluded_diagnoses', []) + 
        extracted_info.get('excluded_medications', []) + 
        extracted_info.get('excluded_observations', [])
    )
        
    # Build allowed files list for clinical searches using the SMART ROUTER
    clinical_allowed_files = []
    primary_pdf = get_relevant_pdf(primary)
    
    if primary_pdf:
        clinical_allowed_files.append(f"pdf_docs/{primary_pdf}")
        
    for related in related_conditions:
        related_pdf = get_relevant_pdf(related)
        if related_pdf and f"pdf_docs/{related_pdf}" not in clinical_allowed_files:
            clinical_allowed_files.append(f"pdf_docs/{related_pdf}")
            
    print(f"[*] Target Demographic identified as: {target_demographic.upper()}")
    print(f"[*] Applying strict clinical metadata filter. Allowed files: {clinical_allowed_files}")
    
    clinical_search_filter = {"source": {"$in": clinical_allowed_files}} if clinical_allowed_files else None
    
    all_retrieved_documents = []
    demo_prefix = "Pediatric" if target_demographic == "pediatric" else "Adult"
    
    # --- QUERY 1: QOF Specific Query (Primary Condition Only) ---
    if primary:
        qof_query = f"QOF indicator business rules register {qof_prefix} {primary}"
        print(f"    -> Querying Vector DB: '{qof_query}' (Strict QOF File Filter - Similarity Only)")
        docs = vector_db.similarity_search(
            qof_query,
            k=3,
            filter={"source": f"pdf_docs/{QOF_FILE}"} 
        )
        all_retrieved_documents.extend(docs)
        
        # --- QUERY 2: Clinical Definitions & Management (Primary) ---
        clin_query = f"{demo_prefix} Definitions, diagnostic criteria, clinical management rules, pharmacological treatment {primary}"
        print(f"    -> Querying Vector DB: '{clin_query}' (Clinical Filter)")
        docs = vector_db.max_marginal_relevance_search(
            clin_query,
            k=3,
            fetch_k=15,
            lambda_mult=0.5,
            filter=clinical_search_filter
        )
        all_retrieved_documents.extend(docs)
    
    # --- QUERY 3: Related Conditions Context ---
    for related in related_conditions:
        rel_query = f"{demo_prefix} Diagnostic criteria clinical management {related}"
        print(f"    -> Querying Vector DB: '{rel_query}' (Clinical Filter)")
        docs = vector_db.max_marginal_relevance_search(
            rel_query,
            k=3,
            fetch_k=15,
            lambda_mult=0.5,
            filter=clinical_search_filter
        )
        all_retrieved_documents.extend(docs)
        
    # --- DEDUPLICATION AND DYNAMIC SHIELDING ---
    print("[*] Deduplicating, cleaning, and applying dynamic demographic/exclusion shields...")
    unique_chunks = {}
    
    for doc in all_retrieved_documents:
        content_lower = doc.page_content.lower()
        source_file = doc.metadata.get('source', '')
        
        # 1. QOF DOMAIN SHIELD: Prevent unrelated diseases from leaking through QOF rules
        if "qof_combined" in source_file and qof_prefix:
            if qof_prefix.lower() not in content_lower:
                continue 

        # 2. DYNAMIC DEMOGRAPHIC SHIELD: Prevent adult/pediatric guidelines from mixing
        has_pediatric_terms = any(term in content_lower for term in ["children", "young person", "paediatric", "pediatric", "child", "infant"])
        has_adult_terms = "adult" in content_lower

        if target_demographic == "pediatric":
            # If the patient is a child, block pure adult chunks
            if has_adult_terms and not has_pediatric_terms:
                continue
        else:
            # If the patient is an adult, block pure pediatric chunks
            if has_pediatric_terms and not has_adult_terms:
                continue 

        # 3. EXCLUSION SHIELD: Discard chunks that explicitly mention excluded terms
        should_exclude = False
        if exclusions:
            for exc in exclusions:
                if exc.strip() and exc.strip().lower() in content_lower:
                    should_exclude = True
                    break
                    
        if should_exclude:
            print("    [!] Shield activated: Chunk discarded due to an explicit exclusion rule.")
            continue
            
        doc_snippet = doc.page_content[:100]
        if doc_snippet not in unique_chunks:
            doc.page_content = clean_boilerplate_text(doc.page_content)
            unique_chunks[doc_snippet] = doc
            
    final_documents = list(unique_chunks.values())
    print(f"--- [PHASE 2 COMPLETE]: Retrieved {len(final_documents)} highly relevant, {target_demographic}-focused chunks ---")
    return final_documents

# -------------------------------------------------------------------
# LLM SYSTEM PROMPT & PARSING
# -------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a clinical informatics expert specialising in SNOMED CT and UK primary care coding. 
A user will describe a patient cohort in plain English. Your job is to parse this into structured components.

Return a VALID JSON object with EXACTLY these keys:

{
  "primary_condition": "string",
  "concept_type": "string",
  "snomed_top_hierarchy": "string",
  "related_conditions": ["list of strings"],
  "excluded_diagnoses": ["list of strings"],
  "excluded_medications": ["list of strings"],
  "excluded_observations": ["list of strings"],
  "relevant_medications": ["list of strings"],
  "relevant_observations": ["list of strings"],
  "relevant_guidelines": ["list of strings"],
  "suggested_validation_sources": ["list of strings"],
  "search_terms": ["list of strings"],
  "ambiguity_notes": "string",
  "target_demographic": "adult | pediatric",
  "qof_domain_prefix": "string"
}

CRITICAL RULES:
1. excluded_diagnoses: MUST include conditions to filter out (e.g., 'Type 1 diabetes' if searching for Type 2).
2. target_demographic: Detect from query. If the patient is a child/infant, output 'pediatric'. If unspecified or adult, output 'adult'.
3. qof_domain_prefix: Extract the official UK QOF abbreviation (e.g., 'DM' for Diabetes, 'HYP' for Hypertension, 'OB' for Obesity). If unknown, leave empty.
"""

def _parse_llm_response(content: str) -> dict:
    """Safely extracts and parses JSON from the LLM response."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Use regex to clean markdown tags safely without breaking code blocks
        # e.g., matching ```json or ``` alone using the hex code for backtick (\x60)
        cleaned = re.sub(r"\x60{3}(?:json)?\s*", "", content).replace("\x60"*3, "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: Find just the JSON part between curly braces
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
    return {}

# -------------------------------------------------------------------
# NHS FHIR SYNONYM ENRICHMENT
# -------------------------------------------------------------------

async def _enrich_with_nhs_synonyms(initial_search_terms: list, primary_condition: str, explicit_exclusions: list, concept_type: str = "diagnosis") -> list:
    """Uses the NHS Terminology Server to find official SNOMED CT synonyms."""
    enriched = list(initial_search_terms)
    try:
        headers  = _get_headers()
        root_id  = CONCEPT_TYPE_ROOTS.get(concept_type, "404684003") # Default to Clinical Finding
        
        async with httpx.AsyncClient(base_url=FHIR_BASE, timeout=15.0) as client:
            resp = await client.get(
                "/ValueSet/$expand", 
                headers=headers, 
                params={"url": f"http://snomed.info/sct?fhir_vs=isa/{root_id}", "filter": primary_condition, "count": 3}
            )
            hits = resp.json().get("expansion", {}).get("contains", [])
            
            for hit in hits:
                concept_id = hit.get("code")
                if not concept_id: continue
                
                syn_resp = await client.get(
                    "/CodeSystem/$lookup", 
                    headers=headers, 
                    params={"system": "http://snomed.info/sct", "code": concept_id, "property": "designation"}
                )
                
                for param in syn_resp.json().get("parameter", []):
                    if param.get("name") == "designation":
                        parts = {p["name"]: p for p in param.get("part", [])}
                        term  = parts.get("value", {}).get("valueString", "").strip()
                        
                        # Add term if it's unique and does not violate any exclusion rules
                        if term and not any(t.lower() == term.lower() for t in enriched):
                            if not any(e.lower() in term.lower() for e in explicit_exclusions):
                                enriched.append(term)
                                
    except Exception as e:
        print(f"    [!] Synonym API enrichment failed (falling back to LLM terms): {e}")
        
    return enriched

# -------------------------------------------------------------------
# MAIN NODE FUNCTION
# -------------------------------------------------------------------

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

    # Validate required demographic and QOF variables, falling back to "adult" if missing
    target_demographic = parsed.get("target_demographic", "adult").lower()
    qof_domain_prefix = parsed.get("qof_domain_prefix", "")

    # 2. ADVANCED RAG RETRIEVAL (Your custom logic)
    final_docs = advanced_retrieval(parsed, vector_db)

    # Build the context payload for the synthesis node
    rag_payload = ""
    found_guidelines = set(parsed.get("relevant_guidelines", []))
    
    for doc in final_docs:
        source = os.path.basename(doc.metadata.get('source', 'Unknown'))
        filename = source.replace('.pdf', '')
        found_guidelines.add(filename)
        rag_payload += f"--- Source: {filename} ---\n{doc.page_content}\n\n"

    # 3. NHS SYNONYM ENRICHMENT (Teammate's logic)
    print("\n--- [PHASE 3] ENRICHING SEARCH TERMS WITH NHS API ---")
    all_exclusions = (
        parsed.get("excluded_diagnoses", []) + 
        parsed.get("excluded_medications", []) + 
        parsed.get("excluded_observations", [])
    )
    
    enriched_terms = await _enrich_with_nhs_synonyms(
        initial_search_terms=parsed.get("search_terms", [parsed.get("primary_condition", "")]),
        primary_condition=parsed.get("primary_condition", ""),
        explicit_exclusions=all_exclusions,
        concept_type=parsed.get("concept_type", "diagnosis")
    )

    print("--- [NODE 1 COMPLETE] Data successfully prepared for Node 2 ---")
    
    # Return the enriched state dictionary matching the NICEState TypedDict
    return {
        "primary_condition":             parsed.get("primary_condition", ""),
        "concept_type":                  parsed.get("concept_type", "diagnosis"),
        "snomed_top_hierarchy":          parsed.get("snomed_top_hierarchy", "Clinical Finding"),
        "related_conditions":            parsed.get("related_conditions", []),
        "excluded_diagnoses":            parsed.get("excluded_diagnoses", []),
        "excluded_medications":          parsed.get("excluded_medications", []),
        "excluded_observations":         parsed.get("excluded_observations", []),
        "relevant_medications":          parsed.get("relevant_medications", []),
        "relevant_observations":         parsed.get("relevant_observations", []),
        "suggested_validation_sources":  parsed.get("suggested_validation_sources", []),
        "ambiguity_notes":               parsed.get("ambiguity_notes", ""),
        
        # Enriched fields
        "search_terms":                  enriched_terms,
        #"relevant_guidelines":           list(found_guidelines),
        "relevant_guidelines":           list(set([os.path.basename(d.metadata.get("source", "")) for d in found_guidelines])),
        
        # New Advanced RAG fields
        "qof_domain_prefix":             qof_domain_prefix,
        "target_demographic":            target_demographic,
        "rag_context":                   rag_payload.strip(),
        #"rag_sources":                   list(found_guidelines),
        "rag_sources": list(set([os.path.basename(d.metadata.get("source", "")) for d in found_guidelines])),
        
        # Pipeline control fields
        "iteration_count":               0,
        "human_review_flag":             False,
        "human_feedback":                None,
        "final_output":                  None
    }