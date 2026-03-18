"""
Node 1 + Node 1b: Query Understanding + Synonym Enrichment — DYNAMIC VERSION

Node 1:  GPT-4o parses ANY patient cohort description into structured state
         No condition-specific knowledge hardcoded
         Infers: concept_type, snomed_hierarchy, relevant_guidelines,
                 suggested_validation_sources, explicit_exclusions

Node 1b: NHS Terminology Server enriches search_terms with official synonyms
         No LLM — pure MCP tool call — authoritative NHS synonyms only
         Non-fatal — falls back to LLM terms if API unavailable
"""
import json
import re
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.rag.retriever import get_retriever
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from src.state import NICEState

# -------------------------------------------------------------------
# LLM — GPT-4o for clinical reasoning quality
# -------------------------------------------------------------------
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# -------------------------------------------------------------------
# System Prompt — fully generic, no condition-specific knowledge
# -------------------------------------------------------------------
SNOMED_HIERARCHY_CONTEXT = """
SNOMED CT UK Edition — Top Level Hierarchies (stable reference):
- Clinical Finding:   diagnoses, disorders, symptoms, observations
                      e.g. heart failure, type 2 diabetes, depression
- Procedure:          operations, therapies, investigations, screenings
                      e.g. echocardiogram, CABG, medication review
- Observable Entity:  measurable parameters, things that can be tested
                      e.g. HbA1c, eGFR, LVEF, blood pressure
- Body Structure:     anatomical locations and structures
                      e.g. left ventricle, coronary artery
- Substance:          drugs, chemical compounds, biologics, vaccines
                      e.g. dapagliflozin, insulin, metformin
- Situation:          context-dependent findings
                      e.g. family history of MI, carer for patient
- Qualifier Value:    severity, laterality, course modifiers
                      e.g. chronic, acute, bilateral, severe
- Mixed:              use ONLY when cohort genuinely spans two or more
                      of the above — e.g. diagnosis + lab result threshold
"""

SYSTEM_PROMPT = """
You are a clinical informatics expert specialising in SNOMED CT and 
UK primary care coding. A user will describe a patient cohort in 
plain English. Your job is to parse this into structured components
for an automated SNOMED CT code search pipeline.

You must reason about the clinical domain WITHOUT assuming any 
specific condition. You will encounter diagnoses, observations, 
procedures, medications, lab results, demographic criteria, 
and combinations of these.

── SNOMED CT REFERENCE ─────────────────────────────────────────────
""" + SNOMED_HIERARCHY_CONTEXT + """
When assigning snomed_top_hierarchy, you MUST use exactly one value
from the list above. Never invent a value outside this list.
────────────────────────────────────────────────────────────────────

Return a VALID JSON object with EXACTLY these keys:

{
  "primary_condition": 
      "string — the single most important clinical concept to search for",

  "concept_type": 
      "one of: diagnosis | observation | procedure | finding | 
       lab_result | medication | demographic | mixed",

  "snomed_top_hierarchy": 
      "one of: Clinical Finding | Procedure | Observable Entity | 
       Substance | Body Structure | Situation | Mixed",

  "related_conditions": 
      ["list of closely related conditions that may share codes"],

  "explicit_exclusions": 
      ["list of conditions/concepts that must NOT appear in the codelist,
        each as a plain English phrase — e.g. 'acute heart failure',
        'type 1 diabetes', 'HFpEF - preserved ejection fraction'"],

  "relevant_guidelines": 
      ["list of NICE/NHS guidelines likely relevant to this cohort,
        format: 'NICE NG106 - Chronic Heart Failure' — 
        only include if you are confident they exist,
        leave empty list [] if uncertain"],

  "suggested_validation_sources": 
      ["list of 3-5 plain English search terms to find relevant 
        codelists on OpenCodelists.org — 
        e.g. 'heart failure reduced ejection fraction',
             'HFrEF primary care register',
             'heart failure QOF' — 
        these will be passed directly to search_codelists() API"],

  "search_terms": 
      ["list of 6-10 SNOMED CT search terms including:
        - primary condition exact phrase
        - all clinical synonyms
        - pre-2013 legacy UK EHR terms (EMIS/SystmOne conventions)
        - acronyms and abbreviations
        - mechanistic equivalents
        - do NOT include exclusion terms"],

  "ambiguity_notes": 
      "string — note any ambiguities in the cohort description that 
       a clinician should clarify, or empty string if none"
}

IMPORTANT RULES:
1. relevant_guidelines: only include guidelines you are highly confident 
   exist. Never hallucinate a NICE guideline number. If uncertain, 
   return [].
2. explicit_exclusions: think like a clinician — what similar-sounding 
   conditions would be wrongly captured by this search?
3. search_terms: ALWAYS include pre-2013 legacy terms for UK EHR 
   compatibility. UK EHRs (EMIS, SystmOne) have records coded under 
   older terminology that predates current SNOMED standards.
4. concept_type: if the cohort mixes diagnoses and observations 
   (e.g. "patients with diabetes and HbA1c > 58"), use "mixed"
5. ambiguity_notes: flag if the cohort description is clinically 
   ambiguous — e.g. "heart failure" without specifying type, 
   "elderly patients" without age threshold
6. snomed_top_hierarchy: use ONLY values from the SNOMED CT Reference
   block above — never invent a value outside that list
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

    return {
        "primary_condition":             primary,
        "concept_type":                  parsed.get("concept_type", "diagnosis"),
        "snomed_top_hierarchy":          parsed.get("snomed_top_hierarchy",
                                                    "Clinical Finding"),
        "related_conditions":            parsed.get("related_conditions", []),
        "explicit_exclusions":           parsed.get("explicit_exclusions", []),
        "relevant_guidelines":           parsed.get("relevant_guidelines", []),
        "suggested_validation_sources":  parsed.get("suggested_validation_sources",
                                                    [primary]),
        "search_terms":                  parsed.get("search_terms", [primary]),
        "ambiguity_notes":               parsed.get("ambiguity_notes", "")
    }


async def _enrich_with_nhs_synonyms(
    initial_search_terms: list[str],
    primary_condition: str,
    explicit_exclusions: list[str]
) -> list[str]:
    """
    Node 1b: Enrich search_terms with official NHS SNOMED synonyms.

    Strategy:
      1. Search SNOMED for the primary condition
      2. For each top result, retrieve all official NHS synonym descriptions
      3. Add synonyms not already in search_terms and not in exclusions

    Non-fatal: returns initial_search_terms unchanged if API unavailable.
    No LLM involved — pure NHS Terminology Server API calls.
    """
    enriched = list(initial_search_terms)

    try:
        async with MultiServerMCPClient({
            "snomed": {
                "command": "python",
                "args": ["tools/snomed_mcp.py"],
                "transport": "stdio"
            }
        }) as client:

            tools = client.get_tools()
            search_tool   = next(
                (t for t in tools if t.name == "search_snomed"), None
            )
            synonyms_tool = next(
                (t for t in tools if t.name == "get_synonyms"), None
            )

            if not search_tool or not synonyms_tool:
                print("[query_understanding:1b] Required tools not available")
                return enriched

            # Step 1: Find concept IDs for primary condition
            initial_results = await search_tool.ainvoke({
                "term": primary_condition,
                "max_results": 5
            })

            if not initial_results or "error" in initial_results[0]:
                print(f"[query_understanding:1b] No SNOMED results for "
                      f"'{primary_condition}'")
                return enriched

            # Step 2: Get all NHS-official synonyms for top 3 concepts
            added_count = 0
            for result in initial_results[:3]:
                concept_id = result.get("snomed_id")
                if not concept_id:
                    continue

                synonyms = await synonyms_tool.ainvoke(
                    {"concept_id": concept_id}
                )

                for syn in synonyms:
                    term = syn.get("term", "").strip()
                    if not term:
                        continue

                    # Skip if already present (case-insensitive)
                    already_present = any(
                        t.lower() == term.lower() for t in enriched
                    )
                    if already_present:
                        continue

                    # Skip if matches an exclusion term
                    is_exclusion = any(
                        excl.lower() in term.lower()
                        for excl in explicit_exclusions
                    )
                    if is_exclusion:
                        continue

                    enriched.append(term)
                    added_count += 1

            print(f"[query_understanding:1b] Added {added_count} NHS synonyms. "
                  f"Total search terms: {len(enriched)}")

    except Exception as e:
        # Non-fatal — log and return LLM-generated terms only
        print(f"[query_understanding:1b] Synonym enrichment failed: {e}")
        print("[query_understanding:1b] Falling back to LLM-generated terms")

    return enriched


async def query_understanding_node(state: NICEState) -> dict:
    """
    Node 1 + 1b: Parse any patient cohort description into structured state.

    Node 1:  GPT-4o clinical reasoning — condition-agnostic
    Node 1b: NHS Terminology Server synonym enrichment — no LLM

    Input:  state["research_question"] — plain English cohort description
    Output: all fields needed by downstream nodes, fully populated
    """
    research_question = state["research_question"]

   # ── RAG: retrieve relevant NICE guideline chunks ──────────────
    retriever       = get_retriever(k=4)
    guideline_docs  = retriever.get_relevant_documents(research_question)

    # Build grounded context with citable source references
    guideline_context = "\n\n".join([
        f"[Source: {doc.metadata.get('display_name', 'Unknown')} "
        f"p.{doc.metadata.get('page', '?')}]\n{doc.page_content}"
        for doc in guideline_docs
    ]) if guideline_docs else "No relevant guidelines retrieved."

    retrieved_sources = list(dict.fromkeys([
        doc.metadata.get("display_name", "Unknown")
        for doc in guideline_docs
    ]))
    print(f"[query_understanding] RAG retrieved from: {retrieved_sources}")

    # ── LLM Call — grounded ───────────────────────────────────────
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"""
Patient cohort description:
{research_question}

Retrieved NICE / NHS guidance (use as primary reference):
──────────────────────────────────────────────────────────
{guideline_context}
──────────────────────────────────────────────────────────

INSTRUCTIONS FOR GROUNDED FIELDS:
- relevant_guidelines: populate ONLY from the retrieved sources above.
  Use the exact source name shown in brackets e.g. "NICE NG106 — Chronic Heart Failure"
  If nothing relevant was retrieved, return [].
- explicit_exclusions: derive from the retrieved guidance above where possible.
  If retrieved text does not cover exclusions, use clinical reasoning
  but mark each exclusion with "(clinical reasoning)" suffix.

All other fields: use your clinical expertise as normal.
        """)
    ]

    print("[query_understanding] Calling GPT-4o...")
    response = await llm.ainvoke(messages)

    parsed  = _parse_llm_response(response.content)
    cleaned = _validate_parsed_output(parsed, research_question)

    # Log key outputs for debugging
    print(f"[query_understanding] Primary condition  : "
          f"{cleaned['primary_condition']}")
    print(f"[query_understanding] Concept type       : "
          f"{cleaned['concept_type']}")
    print(f"[query_understanding] SNOMED hierarchy   : "
          f"{cleaned['snomed_top_hierarchy']}")
    print(f"[query_understanding] Guidelines found   : "
          f"{cleaned['relevant_guidelines'] or 'None'}")
    print(f"[query_understanding] Exclusions         : "
          f"{cleaned['explicit_exclusions']}")
    print(f"[query_understanding] Validation sources : "
          f"{cleaned['suggested_validation_sources']}")
    print(f"[query_understanding] Search terms (LLM) : "
          f"{cleaned['search_terms']}")

    if cleaned["ambiguity_notes"]:
        print(f"[query_understanding] ⚠️  AMBIGUITY: "
              f"{cleaned['ambiguity_notes']}")

    # ------------------------------------------------------------------
    # NODE 1b: NHS Synonym Enrichment
    # ------------------------------------------------------------------
    print("[query_understanding:1b] Enriching with NHS synonyms...")
    enriched_terms = await _enrich_with_nhs_synonyms(
        initial_search_terms=cleaned["search_terms"],
        primary_condition=cleaned["primary_condition"],
        explicit_exclusions=cleaned["explicit_exclusions"]
    )

    print(f"\n[query_understanding] ── Complete ──")
    print(f"[query_understanding] Final search terms : {len(enriched_terms)}")

    return {
        # Core clinical reasoning outputs
        "primary_condition":             cleaned["primary_condition"],
        "concept_type":                  cleaned["concept_type"],
        "snomed_top_hierarchy":          cleaned["snomed_top_hierarchy"],
        "related_conditions":            cleaned["related_conditions"],
        "explicit_exclusions":           cleaned["explicit_exclusions"],
        "relevant_guidelines":           cleaned["relevant_guidelines"],
        "suggested_validation_sources":  cleaned["suggested_validation_sources"],
        "ambiguity_notes":               cleaned["ambiguity_notes"],

        # Enriched search terms — NHS-official synonyms added
        "search_terms":                  enriched_terms,

        # Initialise pipeline control fields
        "iteration_count":               0,
        "human_review_flag":             False,
        "human_feedback":                None,
        "final_output":                  None,
    }
