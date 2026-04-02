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

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import NICEState, Justification, ValidatedCode

# -------------------------------------------------------------------
# LLM
# -------------------------------------------------------------------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1000)

# -------------------------------------------------------------------
# System prompt
# -------------------------------------------------------------------
SYSTEM_PROMPT = """
You are a Clinical Auditor for NICE. You are justifying SNOMED CT codes for a research cohort.

GROUNDING RULES:
1. You will be provided with RETRIEVED CHUNKS from NICE guidelines wrapped in <CHUNK> tags.
2. For each SNOMED code, you MUST find the specific CHUNK that mentions the condition or medication.
3. Carefully check if the retrieved chunk actually justifies the inclusion of the SNOMED code. If it does not, write "No direct guideline evidence found."
4. If the chunk justifies the inclusion of the SNOMED code, your justification must begin with a DIRECT QUOTE from that chunk.
5. If no chunk mentions the specific concept, write "No direct guideline evidence found."
6. Format your response EXACTLY as a JSON object with the keys: 'justification', 'quote', 'page'.
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

def _build_source_document(code: ValidatedCode) -> str:
    found_in = code.get("found_in_codelists", [])
    is_nhsd  = code.get("is_nhsd_refset", False)
    count    = code.get("found_count", 0)

    if not found_in: return "No reference codelist match found — clinical reasoning required"

    sources = "; ".join(found_in[:3])
    if count > 3: sources += f" (+ {count - 3} more)"
    if is_nhsd: sources += " [NHS Digital curated refset]"
    return sources

def _build_justification_prompt(code, research_question, rag_context):
    return f"""
COHORT: {research_question}
CODE: {code['snomed_id']} ({code['preferred_term']})

RETRIEVED GUIDELINE TEXT:
{rag_context}

TASK:
Identify the specific guideline text that justifies including '{code['preferred_term']}'. 
Return ONLY a valid JSON object with 'justification', 'quote', and 'page'.
"""

async def justification_node(state: NICEState) -> dict:
    validated_codes     = state.get("validated_codes", [])
    research_question   = state.get("research_question", "")
    primary_condition   = state.get("primary_condition", "")
    relevant_guidelines = state.get("relevant_guidelines", [])

    if not validated_codes:
        print("[justification] No validated codes — skipping")
        return {"justifications": [], "human_review_flag": True}

    rag_context = state.get("rag_context", "[RAG retrieval unavailable]")
    rag_sources = state.get("rag_sources", [])

    justifications: list[Justification] = []

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

        prompt = _build_justification_prompt(
            code=code,
            research_question=research_question,
            rag_context=rag_context,
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
            
        except json.JSONDecodeError as e:
            # Fallback if the LLM disobeys and writes plain text instead of JSON
            justification_text = f"[Format Error] Raw text: {response.content}"
            evidence_quote = "N/A"
            page_info = "N/A"
        except Exception as e:
            justification_text = f"[Justification generation failed: {e}]"
            evidence_quote = "N/A"
            page_info = "N/A"

        # 3. Update the source chunk to point to the specific page
        source_chunk = f"Ref: {page_info}" if page_info != "N/A" else "⚠️ Clinical reasoning only"

        # 4. Append to the list (now including evidence_quote)
        justifications.append({
            "snomed_id":           snomed_id,
            "preferred_term":      preferred_term,
            "category":            category,
            "justification_text":  justification_text,
            "evidence_quote":      evidence_quote,   # <--- THE NEW FIELD
            "source_document":     _build_source_document(code),
            "source_chunk":        source_chunk,     # <--- UPDATED FIELD
            "confidence_score":    confidence,
            "tier":                tier,
            "qof_match":           is_qof,
            "opencodelists_match": found_count > 0,
            "found_in_codelists":  found_in_names,
            "is_nhsd_refset":      is_nhsd,
            "found_count":         found_count,
        })

        icon = "💊" if category == "Medication" else "🔬" if category == "Observation" else "🩺"
        print(f"[justification] {icon} {tier.upper()} | {snomed_id} | {preferred_term[:35]}... | RAG={'✅' if rag_sources else '⚠️'}")

    return {
        "justifications": justifications,
        "human_review_flag": any(j.get("tier") in ("tier_2", "tier_3") for j in justifications)
    }


