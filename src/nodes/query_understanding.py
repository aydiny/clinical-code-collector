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
import httpx
from dotenv import load_dotenv
load_dotenv()   

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.rag.retriever import get_retriever
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import NICEState
from src.utils.fhir_client import _get_headers, CONCEPT_TYPE_ROOTS, FHIR_BASE

# -------------------------------------------------------------------
# LLM — GPT-4o for clinical reasoning quality
# -------------------------------------------------------------------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1000)

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
       lab_result | medication | demographic | situation | mixed",

  "snomed_top_hierarchy": 
      "one of: Clinical Finding | Procedure | Observable Entity | 
       Substance | Body Structure | Situation | Mixed",

  "related_conditions": 
      ["list of closely related conditions that may share codes"],

   "excluded_diagnoses": 
       ["list of SUBSTRINGS to filter out false-positive terminology matches (e.g., 'preserved' or 'Type 1'). DO NOT put concepts here if you need their SNOMED codes! Leave empty [] if none."],
   
   "excluded_medications": 
       ["list of SUBSTRINGS to filter out false-positive medication terminology matches. CRITICAL: DO NOT list contraindicated or 'already treated' drugs here (like Dapagliflozin) because we need to fetch their codes! Leave empty [] if none."],    

    "excluded_observations": 
       ["list of SUBSTRINGS to filter out false-positive lab terminology matches. Leave empty [] if none."],

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

   "relevant_medications": 
        ["list of specific, singular generic medication names or active ingredients 
         (e.g., 'Dapagliflozin', 'Bisoprolol'). 
         CRITICAL: Do NOT use plural drug classes (like 'SGLT2 inhibitors' or 'Beta-blockers') 
         because SNOMED text search will fail to find them. Leave empty [] if none."],
   
   "relevant_observations": 
        ["list of relevant lab tests, imaging results, or vital signs 
        (e.g., 'LVEF', 'HbA1c', 'Blood pressure'). Leave empty [] if none."],

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
2. EXCLUSIONS: think like a clinician. If the user requires a specific 
   subtype of a disease (e.g., 'Type 2 Diabetes', 'HFrEF'), you MUST explicitly
   exclude the other major subtypes (e.g., 'Type 1 Diabetes', 'HFpEF'). ALWAYS 
   include standard medical acronyms. CRITICAL: NEVER include the primary target condition in this list. 
3. search_terms:
   STRICTLY CLINICAL DIAGNOSES and finding SYNONYMS. CRITICAL: NEVER include medication names (e.g., 'SGLT2 inhibitors'), 
   lab test names (e.g., 'HbA1c'), or generic metadata (e.g., 'UK EHR', 'management') in this list. 
   ALWAYS include pre-2013 legacy terms for UK EHR 
   compatibility. 
4. concept_type: if the cohort is primarily defined by a disease/disorder,
   use "diagnosis". Do NOT use "demographic" just because the prompt uses 
   the word "patients". Use "mixed" if it combines a diagnosis and a lab result.
5. ambiguity_notes: flag if the cohort description is clinically 
   ambiguous — e.g. "heart failure" without specifying type, 
   "elderly patients" without age threshold
6. snomed_top_hierarchy: use ONLY values from the SNOMED CT Reference
   block above — never invent a value outside that list

IMPORTANT RULES:
1. relevant_guidelines: only include guidelines you are highly confident exist. Never hallucinate a NICE guideline number. If uncertain, return [].
2. excluded_diagnoses: think like a clinician — what similar-sounding conditions would be wrongly captured by this search? ALWAYS include standard medical acronyms (e.g., 'HFpEF') for the excluded conditions. CRITICAL: NEVER include the primary target condition or its acronyms (e.g., HFrEF) in this list. This list is STRICTLY for conditions you want to REJECT.
3. search_terms: STRICTLY short clinical diagnoses and finding synonyms. CRITICAL: NEVER include long descriptive phrases (e.g., "Type 2 diabetes with HbA1c > 58"), medication names, lab test names, or generic metadata in this list. Keep terms short (1-4 words) and strictly focused on the core condition. You have dedicated buckets for medications and observations — use them! 
   ALWAYS include pre-2013 legacy terms for UK EHR compatibility.
4. concept_type: if the cohort combines multiple distinct domains (e.g., a diagnosis AND a specific lab result threshold, or a diagnosis AND a medication constraint), you MUST use "mixed". Only use "diagnosis" if the cohort is PURELY defined by a disease/disorder. Do NOT use "demographic" just because the prompt uses the word "patients".
5. ambiguity_notes: flag if the cohort description is clinically ambiguous.
6. snomed_top_hierarchy: use ONLY values from the SNOMED CT Reference block above.

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
        "relevant_observations":          parsed.get("relevant_observations"),
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
    Node 1 + 1b: Parse any patient cohort description into structured state.

    Node 1:  GPT-4o clinical reasoning — condition-agnostic
    Node 1b: NHS Terminology Server synonym enrichment — no LLM

    Input:  state["research_question"] — plain English cohort description
    Output: all fields needed by downstream nodes, fully populated
    """
    research_question = state["research_question"]

   # ── RAG: retrieve relevant NICE guideline chunks ──────────────
    retriever         = get_retriever(k=20)
    guideline_context = "No relevant guidelines retrieved."
    guideline_docs = []
    if retriever:
        try:
            guideline_docs = retriever.invoke(research_question)
            if guideline_docs:
                # 1. Build Structured Context with XML tags and metadata
                structured_context = ""
                for i, doc in enumerate(guideline_docs):
                    # Some loaders use 0-indexed pages, so you might need to +1 depending on your PDF loader
                    page_num = doc.metadata.get("page", "Unknown Page")
                    source_file = os.path.basename(str(doc.metadata.get("source", "Unknown Source")))
                    
                    # Wrap each chunk in an XML tag so the LLM can reference it
                    structured_context += f"\n<CHUNK id='{i}' source='{source_file}' page='{page_num}'>\n"
                    structured_context += doc.page_content
                    structured_context += f"\n</CHUNK>\n"
                
                # Assign the structured text to your context variable
                guideline_context = structured_context
                
                # 2. Safely extract the filename from the metadata for tracking
                sources_set = {os.path.basename(str(d.metadata.get("source", "Unknown"))) for d in guideline_docs}
                
                print(f"\n[DEBUG RAG] 🔍 Retrieved {len(guideline_docs)} chunks.")
                print(f"[DEBUG RAG] 📄 Sources found: {list(sources_set)}")
                print(f"[DEBUG RAG] 📝 Top chunk preview:\n--- START PREVIEW ---\n{guideline_docs[0].page_content[:300]}...\n--- END PREVIEW ---\n")
            # -------------------------------
        except Exception as e:
            print(f"[query_understanding] RAG retrieval failed: {e}")
    else:
        print("[query_understanding] RAG skipped — vector store not built yet")

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
  If the general concept (e.g., "preserved ejection fraction") is mentioned in the text, 
  you do NOT need the clinical reasoning tag. Only append "(clinical reasoning)" 
  if you are inferring the exclusion without any text support.

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
    print(f"[query_understanding] Exclusions - diagnosis          : "
          f"{cleaned['excluded_diagnoses']}")
    print(f"[query_understanding] Exclusions - medications         : "
          f"{cleaned['excluded_medications']}")
    print(f"[query_understanding] Exclusions - observations         : "
          f"{cleaned['excluded_observations']}")
    print(f"[query_understanding] Validation sources : "
          f"{cleaned['suggested_validation_sources']}")
    print(f"[query_understanding] Search terms (LLM) : "
          f"{cleaned['search_terms']}")
    print(f"[query_understanding] relevant medications : "
          f"{cleaned['relevant_medications']}")
    print(f"[query_understanding] relevant observations : "
          f"{cleaned['relevant_observations']}")
    

    if cleaned["ambiguity_notes"]:
        print(f"[query_understanding] ⚠️  AMBIGUITY: "
              f"{cleaned['ambiguity_notes']}")

    # ------------------------------------------------------------------
    # NODE 1b: NHS Synonym Enrichment
    # ------------------------------------------------------------------
    print("[query_understanding:1b] Enriching with NHS synonyms...")

    all_exclusions = (
        cleaned["excluded_diagnoses"] + 
        cleaned["excluded_medications"] + 
        cleaned["excluded_observations"]
    )

    enriched_terms = await _enrich_with_nhs_synonyms(
        initial_search_terms=cleaned["search_terms"],
        primary_condition=cleaned["primary_condition"],
        explicit_exclusions=all_exclusions,
        concept_type=cleaned["concept_type"]
    )

    print(f"\n[query_understanding] ── Complete ──")
    print(f"[query_understanding] Final search terms : {len(enriched_terms +  cleaned["relevant_medications"]+ cleaned["relevant_observations"])}")

    return {
        # Core clinical reasoning outputs
        "primary_condition":             cleaned["primary_condition"],
        "concept_type":                  cleaned["concept_type"],
        "snomed_top_hierarchy":          cleaned["snomed_top_hierarchy"],
        "related_conditions":            cleaned["related_conditions"],
        "excluded_diagnoses":            cleaned["excluded_diagnoses"],
        "excluded_medications":          cleaned["excluded_medications"],
        "excluded_observations":         cleaned["excluded_observations"],
        "relevant_medications":          cleaned["relevant_medications"],
        "relevant_observations":         cleaned["relevant_observations"],
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

        "rag_context": guideline_context,  
        "rag_sources": list(set([os.path.basename(d.metadata.get("source", "")) for d in guideline_docs]))
    }
