"""
Node 4: Justification Agent — DYNAMIC VERSION
- No hardcoded REFERENCE_SOURCES or condition-specific knowledge
- Sources justifications from whatever codelists Validator actually found
- RAG retrieval stubbed — Phase 2 implementation noted clearly
- Assigns final tier labels
- Uses GPT-4o — highest quality clinical text needed here
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.rag.retriever import get_retriever
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import NICEState, Justification, ValidatedCode

# -------------------------------------------------------------------
# LLM — GPT-4o for high-quality, clinically accurate justification
# -------------------------------------------------------------------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1000)

# -------------------------------------------------------------------
# System prompt — fully generic, no condition-specific knowledge
# -------------------------------------------------------------------
SYSTEM_PROMPT = """
You are a clinical informatics expert specialising in SNOMED CT and 
UK primary care coding. Write a concise clinical justification 
(2-3 sentences) for why a SNOMED CT code should be included in a 
codelist for identifying a specific patient cohort.

Your justification must:
1. Explain precisely what clinical concept this SNOMED code represents
2. Explain why it correctly identifies patients in the described cohort
3. Reference the validation sources it was found in (provided to you)
4. Note any caveats — e.g. legacy code, supplementary use only,
   umbrella code requiring additional filters, or low confidence

Rules:
- Do NOT mention NICE NG106 or any specific guideline unless it was
  explicitly provided in the validation sources
- Do NOT hallucinate codelist names or refset IDs
- If confidence is low, explicitly state the uncertainty
- If tier is tier_3, explicitly state "for supplementary use only —
  should not be used as the sole identifier for this cohort"
- Write for a clinical lead reviewer, not a developer
"""

# -------------------------------------------------------------------
# Tier assignment — universal thresholds
# Mirrors validator.py thresholds exactly
# -------------------------------------------------------------------
TIER_THRESHOLDS = {
    "tier_1": 0.70,
    "tier_2": 0.45,
    "tier_3": 0.25,
}

def assign_tier(confidence_score: float) -> str:
    if confidence_score >= TIER_THRESHOLDS["tier_1"]:
        return "tier_1"
    elif confidence_score >= TIER_THRESHOLDS["tier_2"]:
        return "tier_2"
    else:
        return "tier_3"


def _build_source_document(code: ValidatedCode) -> str:
    """
    Build source document string dynamically from what Validator found.
    No hardcoded source names — uses actual codelist names from state.
    """
    found_in = code.get("found_in_codelists", [])
    is_nhsd  = code.get("is_nhsd_refset", False)
    count    = code.get("found_count", 0)

    if not found_in:
        return "No reference codelist match found — human review required"

    # Build readable source string
    sources = "; ".join(found_in[:3])  # cap at 3 for readability
    if count > 3:
        sources += f" (+ {count - 3} more)"
    if is_nhsd:
        sources += " [NHS Digital curated refset]"

    return sources


def _build_justification_prompt(
    code: ValidatedCode,
    research_question: str,
    primary_condition: str,
    relevant_guidelines: list[str],
    rag_context: str,              # ← NEW parameter
    rag_sources: list[str]         # ← NEW parameter
) -> str:
    tier            = assign_tier(code.get("confidence_score", 0.0))
    source_document = _build_source_document(code)
    found_in        = code.get("found_in_codelists", [])
    is_nhsd         = code.get("is_nhsd_refset", False)

    guideline_context = (
        f"Relevant guidelines identified: {', '.join(relevant_guidelines)}"
        if relevant_guidelines
        else "No specific guidelines identified for this cohort."
    )

    # RAG context block — present only if retrieval succeeded
    rag_block = f"""
Retrieved NICE / NHS guidance (use as primary reference for justification):
──────────────────────────────────────────────────────────────────────────
{rag_context}
──────────────────────────────────────────────────────────────────────────
INSTRUCTION: Ground your justification in the retrieved text above where
possible. Quote or paraphrase directly. If the retrieved text does not
cover this specific code, use clinical reasoning but state that explicitly.
""" if rag_context and rag_context != "[RAG retrieval unavailable]" else """
⚠️ No guideline text retrieved for this code.
Justification based on clinical reasoning — reviewer should verify
against source guidelines before approval.
"""

    return f"""
Write a clinical justification for including the following SNOMED CT code
in a codelist for the patient cohort described below.

COHORT DESCRIPTION:
{research_question}

PRIMARY CONDITION: {primary_condition}

CODE DETAILS:
- SNOMED ID     : {code['snomed_id']}
- Preferred term: {code['preferred_term']}
- Confidence    : {code['confidence_score']:.2f} / 1.00
- Assigned tier : {tier.replace('_', ' ').upper()}
- NHS Digital   : {'Yes — found in NHSD curated refset' if is_nhsd else 'No'}
- Found in      : {', '.join(found_in) if found_in else 'No codelist match'}
- Validation src: {source_document}

{guideline_context}

{rag_block}

TIER CONTEXT:
- Tier 1 (≥0.70): Core identifier — unambiguous, high confidence
- Tier 2 (0.45–0.69): Include with caveat — legacy or umbrella code
- Tier 3 (0.25–0.44): Supplementary only — cannot stand alone

Write the justification now (2-3 sentences).
Cite the specific guideline source in brackets where possible
e.g. [NICE NG106 p.12] or [QOF Business Rules 2025/26].
"""


async def justification_node(state: NICEState) -> dict:
    validated_codes     = state.get("validated_codes", [])
    research_question   = state.get("research_question", "")
    primary_condition   = state.get("primary_condition", "")
    relevant_guidelines = state.get("relevant_guidelines", [])

    if not validated_codes:
        print("[justification] No validated codes — skipping")
        return {
            "justifications":    [],
            "human_review_flag": True,
            "human_review_reason": "No validated codes reached justification node."
        }

    # ── RAG: retrieve guideline context ONCE for all codes ─────────
    # Same retriever as Node 1 — loaded from singleton, no rebuild cost
    rag_context  = "[RAG retrieval unavailable]"
    rag_sources  = []

    try:
        retriever     = get_retriever(k=5)   # slightly more chunks for justification
        guideline_docs = retriever.get_relevant_documents(
            f"{primary_condition} {research_question}"
        )
        if guideline_docs:
            rag_context = "\n\n".join([
                f"[Source: {doc.metadata.get('display_name', 'Unknown')} "
                f"p.{doc.metadata.get('page', '?')}]\n{doc.page_content}"
                for doc in guideline_docs
            ])
            rag_sources = list(dict.fromkeys([
                doc.metadata.get("display_name", "Unknown")
                for doc in guideline_docs
            ]))
            print(f"[justification] RAG retrieved from: {rag_sources}")
    except Exception as e:
        print(f"[justification] RAG retrieval failed: {e} — "
              f"falling back to LLM-only justification")

    justifications: list[Justification] = []

    print(f"\n[justification] ── Generating justifications ──")
    print(f"[justification] Codes    : {len(validated_codes)}")
    print(f"[justification] RAG srcs : {rag_sources or 'None — LLM fallback'}")

    for code in validated_codes:
        snomed_id      = code.get("snomed_id", "")
        preferred_term = code.get("preferred_term", "")
        confidence     = code.get("confidence_score", 0.0)
        tier           = assign_tier(confidence)
        source_document = _build_source_document(code)

        # Build grounded prompt — RAG context injected per-run
        prompt = _build_justification_prompt(
            code=code,
            research_question=research_question,
            primary_condition=primary_condition,
            relevant_guidelines=relevant_guidelines,
            rag_context=rag_context,      # ← grounded
            rag_sources=rag_sources       # ← citable
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        try:
            response = await llm.ainvoke(messages)
            justification_text = response.content.strip()
        except Exception as e:
            justification_text = (
                f"[Justification generation failed: {e}. "
                f"Manual review required for {snomed_id}.]"
            )

        # Build citable source_chunk from RAG metadata
        source_chunk = (
            f"Retrieved from: {'; '.join(rag_sources)}"
            if rag_sources
            else "⚠️ No guideline text retrieved — clinical reasoning only"
        )

        justifications.append({
            "snomed_id":           snomed_id,
            "preferred_term":      preferred_term,
            "justification_text":  justification_text,
            "source_document":     source_document,
            "source_chunk":        source_chunk,       # ← now citable
            "confidence_score":    confidence,
            "tier":                tier,
            "qof_match":           code.get("qof_match", False),
            "opencodelists_match": code.get("opencodelists_match", False),
            "found_in_codelists":  code.get("found_in_codelists", []),
            "is_nhsd_refset":      code.get("is_nhsd_refset", False)
        })

        print(f"[justification] {tier.upper()} | {snomed_id} | "
              f"{preferred_term[:45]} | score={confidence:.2f} | "
              f"RAG={'✅' if rag_sources else '⚠️'}")

    # Sort: Tier 1 → 2 → 3, then by score descending within tier
    tier_order = {"tier_1": 0, "tier_2": 1, "tier_3": 2}
    justifications.sort(key=lambda x: (
        tier_order.get(x.get("tier", "tier_3"), 2),
        -x.get("confidence_score", 0.0)
    ))

    t1 = sum(1 for j in justifications if j["tier"] == "tier_1")
    t2 = sum(1 for j in justifications if j["tier"] == "tier_2")
    t3 = sum(1 for j in justifications if j["tier"] == "tier_3")

    print(f"\n[justification] ── Complete ──")
    print(f"[justification] T1={t1}  T2={t2}  T3={t3}  "
          f"Total={len(justifications)}")

    needs_review = any(
        j.get("tier") in ("tier_2", "tier_3") for j in justifications
    )

    return {
        "justifications":    justifications,
        "human_review_flag": needs_review
    }