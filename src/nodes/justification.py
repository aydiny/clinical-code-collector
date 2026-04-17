"""
Node 4: Justification Agent — DYNAMIC VERSION
- Sources justifications from whatever codelists Validator actually found
- RAG retrieval injected from state
- Assigns final tier labels
- Uses GPT-4o-mini
"""
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.vectorstores import Chroma
from src.state import NICEState, Justification, ValidatedCode
from src.rag.retriever_by_code import retrieve_context_for_code

# --- DYNAMIC PATHING ---
# Dynamically locate the project root directory so the script works on any machine
# regardless of where the terminal is opened.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
sys.path.append(PROJECT_ROOT)

# --- DYNAMIC DATABASE PATH ---
# Points exactly to the GitHub folder structure: data/vectorstore/short_chunks
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "data", "vectorstore", "short_chunks")
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

# INITIALIZE MODELS & VECTOR DATABASE
print("[*] Initializing OpenAI models & connecting to ChromaDB...")


# -------------------------------------------------------------------
# System prompt
# -------------------------------------------------------------------
SYSTEM_PROMPT = """
You are a Clinical Auditor for NICE. You are justifying SNOMED CT codes for a research cohort.

GROUNDING RULES:
1. You must only use the provided <EVIDENCE_CHUNKS>. 
2. If the evidence does not explicitly support the code for the specific cohort, you must state "No direct guideline evidence found."
3. Every justification MUST start with a verbatim quote.
4. Accuracy is critical: do not assume a code is valid just because it is in the list.

"""

TIER_THRESHOLDS = {
    "tier_1": 0.70,
    "tier_2": 0.45,
    "tier_3": 0.25,
}

def assign_tier(confidence_score: float) -> str:
    if confidence_score >= TIER_THRESHOLDS["tier_1"]: return "tier_1"
    elif confidence_score >= TIER_THRESHOLDS["tier_2"]: return "tier_2"
    else: return "tier_3"

def _build_justification_prompt(code, research_question, rag_context):
    return f"""
### RESEARCH COHORT
{research_question}

### CLINICAL TERM TO JUSTIFY
{code['preferred_term']}

### EVIDENCE
<EVIDENCE_CHUNKS>
{rag_context}
</EVIDENCE_CHUNKS>

### INSTRUCTIONS
1. Analyze if the EVIDENCE justifies the CLINICAL TERM for the COHORT.
2. If justified, start the 'justification' with a verbatim quote.
3. If not found, set all fields to "No direct guideline evidence found."

### OUTPUT FORMAT (JSON ONLY)
{{
  "clinical_reasoning": "Step-by-step logic here",
  "justification": "Final audit statement",
  "quote": "Direct quote from text",
  "page": "Page number from attribute",
  "source_file": "Source file from attribute"
}}

Return ONLY the JSON.
"""

async def justification_node(state: NICEState) -> dict:

    print("[*] Initializing OpenAI models & connecting to ChromaDB...")
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME)
    vector_db = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embeddings)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1000)

    validated_codes     = state.get("validated_codes", [])
    research_question   = state.get("research_question", "")
    primary_condition   = state.get("primary_condition", "")
    relevant_guidelines = state.get("relevant_guidelines", [])

    if not validated_codes:
        print("[justification] No validated codes — skipping")
        return {"justifications": [], "human_review_flag": True}

    rag_sources = state.get("rag_sources", [])

    justifications: list[Justification] = []
    primary_condition = state.get("primary_condition", "")
    demographic = state.get("target_demographic", "adult")

    print(f"\n[justification] ── Generating justifications ──")
    print(f"[justification] Codes    : {len(validated_codes)}")
    
    for code in validated_codes:
        snomed_id      = code.get("snomed_id", "")
        preferred_term = code.get("preferred_term", "")
        confidence     = code.get("confidence_score", 0.0)
        tier           = assign_tier(confidence)
        category       = code.get("category", "Diagnosis")
        found_count    = code.get("found_count", 0)
        found_in_names = code.get("found_in_codelists", [])
        is_nhsd        = code.get("is_nhsd_refset", False)
        is_qof         = code.get("qof_match", False)
        ocl_match      = code.get("opencodelists_match", "")
        semantic_score = code.get("semantic_score")

        if tier=="tier_1" or tier=="tier_2":

            # Fetch exact, sniper-focused context for this specific code
            code_context = retrieve_context_for_code(
                snomed_term=code["preferred_term"],
                category=code["category"],
                primary_condition=primary_condition,
                target_demographic=demographic,
                vector_db=vector_db
            )
        
            prompt = _build_justification_prompt(
                code=code,
                research_question=research_question,
                rag_context=code_context,
            )

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]

            try:
                response = await llm.ainvoke(messages)
                
                # 1. Clean the response (LLMs sometimes wrap JSON in markdown blocks like ```json ... ```)
                clean_response = response.content.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:-3].strip()
                elif clean_response.startswith("```"):
                    clean_response = clean_response[3:-3].strip()
                    
                # 2. Parse the JSON
                data = json.loads(clean_response)
                
                justification_text = data.get("justification", "No justification provided.")
                evidence_quote = data.get("quote", "No direct quote found.")
                page_info = data.get("page", "N/A")
                source_file = data.get("source_file", "No direct quote found.")
                
            except json.JSONDecodeError as e:
                # Fallback if the LLM disobeys and writes plain text instead of JSON
                justification_text = f"[Format Error] Raw text: {response.content}"
                evidence_quote = "N/A"
                page_info = "N/A"
                source_file = "N/A"  # <-- ADDED
            except Exception as e:
                justification_text = f"[Justification generation failed: {e}]"
                evidence_quote = "N/A"
                page_info = "N/A"
                source_file = "N/A"  # <-- ADDED

            # 3. Update the source chunk to point to the specific page
            source_chunk = f"Ref: {page_info}" if page_info != "N/A" else "⚠️ Clinical reasoning only"

            # 4. Append to the list (now including evidence_quote)
            justifications.append({
                "snomed_id":           snomed_id,
                "preferred_term":      preferred_term,
                "category":            category,
                "justification_text":  justification_text,
                "evidence_quote":      evidence_quote,   
                "source_document":     source_file,
                "source_chunk":        source_chunk,     
                "confidence_score":    confidence,
                "tier":                tier,
                "qof_match":           is_qof,
                "opencodelists_match": ocl_match,
                "found_in_codelists":  found_in_names,
                "is_nhsd_refset":      is_nhsd,
                "found_count":         found_count,
                "semantic_score":      semantic_score
            })

            icon = "💊" if category == "Medication" else "🔬" if category == "Observation" else "🩺"
            print(f"[justification] {icon} {tier.upper()} | {snomed_id} | {preferred_term[:35]}... | RAG={'✅' if rag_sources else '⚠️'}")
        
        else:
            justifications.append({
                "snomed_id":           snomed_id,
                "preferred_term":      preferred_term,
                "category":            category,
                "justification_text":  "Tier 3 - No justification sought",
                "evidence_quote":      "Tier 3 - No justification sought",
                "source_document":     source_file,
                "source_chunk":        "Tier 3 - No justification sought",
                "confidence_score":    confidence,
                "tier":                tier,
                "qof_match":           is_qof,
                "opencodelists_match": ocl_match,
                "found_in_codelists":  found_in_names,
                "is_nhsd_refset":      is_nhsd,
                "found_count":         found_count,
                "semantic_score":      semantic_score
            })


    return {
        "justifications": justifications,
        "human_review_flag": any(j.get("tier") in ("tier_2", "tier_3") for j in justifications)
    }


