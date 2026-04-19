# NICE Clinical Code Recommender - App Overview

This document explains how the app is structured, what input it expects, what each pipeline node does, and what output it produces.

The app is deployed on the cloud (on Render) and can be accesses at:

https://nice-rag-project.onrender.com/



---

## 1) High-level App Structure

The system has two layers:

- **Frontend/UI layer**: `app.py` (Streamlit)
- **Pipeline layer**: LangGraph workflow in `src/graph.py`, with shared state in `src/state.py`

Main flow:

1. User enters a free-text clinical cohort question in the Streamlit app.
2. Streamlit calls the LangGraph app (`main.py` exposes the compiled graph).
3. The graph runs nodes in sequence:
   - `query_understanding`
   - `snomed_search`
   - `validator`
   - `justification`
4. Results are shown as clinician-review cards in the UI.
5. Reviewer decisions can be submitted to Supabase and outputs can be downloaded.

---

## 2) Inputs

### Runtime user input

- `research_question` (required): a plain-English query describing the target patient cohort.

Example:
- "Identify adults with Type 2 diabetes suitable for SGLT2 therapy review in primary care."

### Environment/configuration inputs

- `OPENAI_API_KEY` - used for LLM reasoning and embeddings
- `SUPABASE_URL` and `SUPABASE_KEY` - used to store reviewer feedback
- NHS SNOMED FHIR API access - used for terminology search/synonym expansion
- OpenCodelists index and loaders - used in validation scoring

---

## 3) State Contract (How data moves between nodes)

The shared typed state is defined in `src/state.py` as `NICEState`.

It contains:

- input question
- parsed query metadata (condition, exclusions, terms, guidelines)
- candidate SNOMED codes
- validated/scored codes
- generated justifications
- human review flags/feedback
- final output field

This single state object is passed and enriched by each node.

---

## 4) Node-by-Node Explanation

### Node 1: Query Understanding (`src/nodes/query_understanding.py`)

**Purpose:** Convert a natural-language cohort question into structured clinical search instructions.

**How it works:**

- Uses `gpt-4o-mini` with a strict clinical parsing prompt.
- Extracts key fields such as:
  - `primary_condition`
  - `concept_type`
  - `snomed_top_hierarchy`
  - `search_terms`
  - `related_conditions`
  - exclusion lists for diagnosis/medication/observations
  - suggested guideline and validation hints
- Applies validation/defaults so missing or malformed model outputs do not break the pipeline.
- Enriches diagnosis search terms with SNOMED/NHS synonym lookups via FHIR APIs.

**Output to state:** structured intent fields used by downstream search and validation.

---

### Node 2: SNOMED Search (`src/nodes/snomed_search.py`)

**Purpose:** Generate broad candidate SNOMED code sets across diagnosis, medication, and observation categories.

**How it works:**

- Runs SNOMED searches with category-specific roots:
  - Diagnosis (`Clinical Finding`)
  - Medication (`Pharmaceutical/biologic product`)
  - Observation (`Observable Entity`)
- Uses terms from Node 1 and applies exclusion filters to reduce false positives.
- For medications, performs descendant traversal to include specific product-level concepts.
- Deduplicates results into one candidate list.

**Output to state:** `candidate_codes` (raw candidate SNOMED concepts).

---

### Node 3: Validator (`src/nodes/validator.py`)

**Purpose:** Score and filter candidate codes into a clinically prioritized shortlist.

**How it works:**

- Retrieves relevant OpenCodelists using keyword matching over condition, medication, and observation text.
- For each candidate code:
  - checks whether it appears in retrieved codelists
  - uses metadata intent signals (QOF, NHSD curated, safety audit, epidemiology)
  - computes embedding-based semantic similarity
  - applies category-aware scoring and confidence thresholds
- Removes low-confidence entries.
- Produces confidence-rich validated records plus routing metadata.

**Output to state:**

- `validated_codes`
- `low_confidence_codes`
- `iteration_count`
- `routing_decision`

Note: loop-back logic exists in the graph, but current validator output is configured to proceed.

---

### Node 4: Justification (`src/nodes/justification.py`)

**Purpose:** Create evidence-grounded audit justifications for validated codes.

**How it works:**

- Assigns tier labels (`tier_1`, `tier_2`, `tier_3`) from confidence scores.
- For Tier 1/2 codes:
  - retrieves focused evidence chunks per code from vector DB
  - prompts `gpt-4o-mini` to generate structured JSON justification, quote, and source details
- For Tier 3 codes:
  - keeps lightweight placeholder justification (no full evidence generation)
- Sets `human_review_flag` when results include lower-confidence tiers needing closer review.

**Output to state:** `justifications` and review flags.

---

## 5) Human Review and Feedback in Streamlit (`app.py`)

After the pipeline completes:

- The app displays each proposed code with confidence, tier, and justification.
- Reviewer can mark each code as:
  - accepted
  - rejected
  - skipped
- Reviewer can provide reason text and rating.
- On submission, feedback is written to Supabase (`nice_feedback` table).

The app also supports downloads:

- accepted code CSV
- full Excel output
- full JSON output

---

## 6) Final Output

The final output is a structured, clinician-reviewable list of SNOMED recommendations.

Each result typically includes:

- `snomed_id`
- `preferred_term`
- `category`
- `confidence_score`
- `tier`
- `justification_text`
- `evidence_quote`
- `source_document`
- `source_chunk`
- evidence provenance flags (QOF/NHSD/OpenCodelists metadata)

In summary, the app delivers an AI-generated shortlist of clinically relevant SNOMED codes with explainable evidence, then captures human audit decisions for governance and future improvement.

---

## 7) Data Sources

The app combines several data sources, each used for a specific stage of the pipeline:

- **User-entered cohort query (primary input)**  
  Free-text clinical question entered in Streamlit (for example, a condition and target cohort).

- **NHS SNOMED CT FHIR Terminology Server**  
  Used in two places:
  - Node 1 to enrich search terms with official SNOMED synonyms (`CodeSystem/$lookup`, `ValueSet/$expand`)
  - Node 2 to retrieve candidate SNOMED concepts for diagnosis, medication, and observation domains

- **OpenCodelists (external codelist evidence)**  
  Node 3 dynamically loads SNOMED code members from curated codelists listed in `config/opencodelists_index.py`.  
  Includes sources such as NHSD primary care domain refsets, OpenSAFELY lists, QCovid/PINCER/research lists.

- **Local RAG vector stores (ChromaDB)**  
  Local persisted vector indexes under `data/vectorstore/` are used for evidence retrieval:
  - methodology/guideline chunks for retrieval logic
  - short chunk store for code-level justification context

- **Supabase table for human feedback (`nice_feedback`)**  
  Not a retrieval source for candidate generation, but a storage source for reviewer actions (accept/reject/skip, reason, rating) captured in the UI.

---

## 8) Tools and Technologies Used

### Orchestration and app framework

- **Streamlit** (`app.py`) for clinician-facing UI
- **LangGraph** (`src/graph.py`) for stateful node orchestration
- **Typed state contract** (`src/state.py`) for reliable data passing across nodes

### AI/LLM and embeddings

- **OpenAI GPT-4o-mini** via `langchain-openai`
  - query decomposition in Node 1
  - evidence-grounded justification generation in Node 4
- **OpenAI embeddings (`text-embedding-3-small`)**
  - semantic similarity scoring in Node 3
  - vector retrieval support for RAG contexts

### Retrieval and vector tooling

- **ChromaDB** (`langchain-community` Chroma integration)
  - local persistent vector stores for NICE/methodology evidence chunks
- **Custom retrievers**
  - `src/rag/retriever.py` (advanced retrieval logic)
  - `src/rag/retriever_by_code.py` (code-specific evidence retrieval)

### Terminology and external APIs

- **NHS FHIR Terminology API** (`httpx` async calls)
  - SNOMED concept expansion and synonym lookup
- **OpenCodelists CSV endpoints**
  - downloaded and parsed for validator evidence signals

### Data persistence and export

- **Supabase Python client**
  - writes reviewer feedback records to `nice_feedback`
- **Pandas + OpenPyXL**
  - CSV/Excel export of reviewed outputs

### Supporting Python libraries

- `python-dotenv` for environment variable management
- `numpy` for cosine similarity math
- standard async and JSON tooling (`asyncio`, `json`)
