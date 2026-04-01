"""
Node 4: Justification Agent — DYNAMIC VERSION
- Sources justifications from whatever codelists Validator actually found
- RAG retrieval injected from state
- Assigns final tier labels
- Uses GPT-4o-mini
"""
import sys
import os
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
You are a clinical informatics expert specialising in SNOMED CT and UK primary care coding. 
Write a concise clinical justification (2-3 sentences) for why a SNOMED CT code should 
be included in a codelist for identifying a specific patient cohort.

Your justification must:
1. Explain precisely what clinical concept this SNOMED code represents (Disease, Medication, or Observation).
2. Explain why it is relevant to the described cohort.
3. Reference the validation sources it was found in (provided to you).
4. Note any caveats (e.g., low confidence, supplementary use).

Rules:
- Do NOT hallucinate codelist names or refset IDs.
- If confidence is low, explicitly state the uncertainty.
- Write for a clinical lead reviewer, not a developer.
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

def _build_justification_prompt(
    code: ValidatedCode,
    research_question: str,
    primary_condition: str,
    relevant_guidelines: list[str],
    rag_context: str,
    rag_sources: list[str]
) -> str:
    tier = assign_tier(code.get("confidence_score", 0.0))
    source_document = _build_source_document(code)
    found_in = code.get("found_in_codelists", [])
    category = code.get("category", "Diagnosis")

    guideline_context = f"Relevant guidelines: {', '.join(relevant_guidelines)}" if relevant_guidelines else "No specific guidelines identified."
    
    rag_block = f"""
Retrieved Guidelines:
──────────────────────────────────────────────────────────────────────────
{rag_context}
──────────────────────────────────────────────────────────────────────────
INSTRUCTION: Ground your justification in the retrieved text above where possible.
""" if rag_context and rag_context != "[RAG retrieval unavailable]" else "⚠️ No guideline text retrieved."

    return f"""
COHORT DESCRIPTION: {research_question}
PRIMARY CONDITION: {primary_condition}

CODE DETAILS:
- Category      : {category.upper()}
- SNOMED ID     : {code['snomed_id']}
- Preferred term: {code['preferred_term']}
- Confidence    : {code['confidence_score']:.2f}
- Assigned tier : {tier.upper()}
- Validation src: {source_document}

{guideline_context}
{rag_block}

Write the justification now (2-3 sentences).
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

        prompt = _build_justification_prompt(
            code=code,
            research_question=research_question,
            primary_condition=primary_condition,
            relevant_guidelines=relevant_guidelines,
            rag_context=rag_context,
            rag_sources=rag_sources
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        try:
            response = await llm.ainvoke(messages)
            justification_text = response.content.strip()
        except Exception as e:
            justification_text = f"[Justification generation failed: {e}]"

        source_chunk = f"Retrieved from: {'; '.join(rag_sources)}" if rag_sources else "⚠️ Clinical reasoning only"

        justifications.append({
            "snomed_id":           snomed_id,
            "preferred_term":      preferred_term,
            "category":            category,
            "justification_text":  justification_text,
            "source_document":     _build_source_document(code),
            "source_chunk":        source_chunk,
            "confidence_score":    confidence,
            "tier":                tier,
        })

        icon = "💊" if category == "Medication" else "🔬" if category == "Observation" else "🩺"
        print(f"[justification] {icon} {tier.upper()} | {snomed_id} | {preferred_term[:35]}... | RAG={'✅' if rag_sources else '⚠️'}")

    return {
        "justifications": justifications,
        "human_review_flag": any(j.get("tier") in ("tier_2", "tier_3") for j in justifications)
    }