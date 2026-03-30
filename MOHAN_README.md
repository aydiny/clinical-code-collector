# NICE RAG Project - UI Module
## Written by Mohan
## Last updated: March 2025

---

## Overview

This module contains the Streamlit-based UI for the NICE AI-Assisted Clinical Code
Recommendation System. It is designed to sit on top of the LangGraph pipeline built
by the rest of the team and provide a clean interface for clinicians to review,
accept, reject, and provide feedback on AI-generated clinical code suggestions.

---

## How to run the UI locally

### Step 1 - Clone the repo
```
git clone https://github.com/LAB-FAM/nice-rag-project.git
cd nice-rag-project
```

### Step 2 - Create a virtual environment
```
python -m venv venv
source venv/bin/activate
```

### Step 3 - Install dependencies
```
pip install -r requirements.txt
```

### Step 4 - Add your API keys
Create a .env file in the root folder and add:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### Step 5 - Add the NHS logo
The NHS logo is not included in the repo for licensing reasons.
Place the NHS logo file named exactly:
```
assets/NHS 10mm - RGB Blue on white.jpg
```
The Cambridge logo is already included in the assets/ folder.

### Step 6 - Run the app
```
streamlit run app.py
```

The app will open automatically in your browser at http://localhost:8501

---

## Current status

The UI is currently running in DUMMY DATA MODE (USE_DUMMY_DATA = True in app.py).
This means it does not connect to the real LangGraph pipeline yet.
It uses hardcoded dummy data from src/utils/dummy_data.py to simulate the pipeline output.

To connect the real pipeline, set USE_DUMMY_DATA = False in app.py and implement
the pipeline call in the section marked with a comment in the main() function.

---

## What the UI expects from the pipeline

The UI is built around the NICEState object defined in src/state.py.
When the real pipeline is connected, it must return a fully populated NICEState object.

Here is what the UI reads from the state and where it is displayed:

### From Node 1 (Query Understanding)
- research_question - shown in the query input bar
- primary_condition - shown in the query summary panel
- concept_type - shown in the query summary panel
- snomed_top_hierarchy - shown in the query summary panel
- related_conditions - shown in the query summary panel
- explicit_exclusions - shown in the query summary panel
- relevant_guidelines - shown in the query summary panel
- search_terms - shown in the query summary panel
- ambiguity_notes - shown as a warning banner if not empty

### From Node 2 (SNOMED Search)
- candidate_codes - used for the candidates found metric only

### From Node 3 (Validation)
- validated_codes - used for the after validation metric only
- low_confidence_codes - not currently displayed but stored in state
- routing_decision - not currently displayed but stored in state

### From Node 4 (Justification)
- justifications - this is the main data driving the code review cards
  Each justification must contain:
  - snomed_id
  - preferred_term
  - justification_text
  - source_document
  - source_chunk
  - confidence_score
  - tier (tier_1, tier_2, or tier_3)
  - qof_match (True or False)
  - opencodelists_match (True or False)
  - found_in_codelists (list of strings)
  - is_nhsd_refset (True or False)

### Human review fields
- human_review_flag - if True the UI shows the review warning banner
- human_review_reason - shown in the review warning banner
- human_feedback - written back to state when clinician submits feedback
- final_output - written back to state after audit submission

---

## Feedback loop - what needs to be built

The UI captures clinician feedback per code and stores it in st.session_state.feedback.
Each feedback entry has this structure:
```
{
    "timestamp":           ISO format datetime string,
    "session_id":          unique UUID per review session,
    "research_question":   the original query string,
    "primary_condition":   primary condition from Node 1,
    "snomed_id":           SNOMED code ID,
    "preferred_term":      SNOMED preferred term,
    "tier":                tier_1, tier_2 or tier_3,
    "confidence_score":    float between 0 and 1,
    "decision":            accepted or rejected,
    "reason":              free text from clinician,
    "rating":              integer 1 to 5,
    "qof_match":           True or False,
    "is_nhsd_refset":      True or False,
    "found_in_codelists":  list of strings,
    "reviewer_id":         string, currently hardcoded as clinician
}
```

For the feedback loop to work end to end, the team needs to build:

1. A feedback ingestion function that takes this dictionary and embeds it
   into Vector Store C (ChromaDB collection: clinician_feedback)

2. A retriever for Vector Store C that Node 1 and Node 4 can call at runtime
   to retrieve relevant past feedback for a given query

3. Node 1 needs to be updated to query Vector Store C and use past feedback
   to shape its search terms - e.g. if clinicians previously rejected a code
   for this condition, Node 1 should avoid generating search terms that would
   surface it again

4. Node 4 needs to be updated to query Vector Store C and reference past
   clinician decisions in its justification text - e.g. note that a code
   was previously flagged as over-constraining the cohort

The feedback is currently saved to session_state only and is lost when the
browser is refreshed. Once the ingestion function is built, the Submit feedback
button in the UI should call it directly.

---

## What is missing or still to do

1. Real pipeline connection - USE_DUMMY_DATA needs to be set to False and the
   graph invocation needs to be implemented in main() in app.py

2. Feedback ingestion to Vector Store C - see feedback loop section above

3. NHS logo - not included in repo for licensing reasons, must be added manually

4. Authentication - there is currently no login or user management. The reviewer_id
   field in feedback is hardcoded as clinician. A real deployment would need
   authentication so feedback can be attributed to specific reviewers.

5. Async pipeline handling - the real LangGraph pipeline runs asynchronously.
   Streamlit does not natively support async. The team will need to decide whether
   to use st.spinner with a synchronous wrapper or move to a FastAPI backend.

6. LLM choice - currently GPT-4o is hardcoded in the node files. If this changes
   the dummy data and UI do not need updating but the node files will.

7. Error handling for pipeline failures - the UI currently handles the case where
   no codes are returned but does not handle pipeline crashes or API timeouts.
   These need to be handled when the real pipeline is connected.

---

## Files added by this module

- app.py - main Streamlit UI entry point
- src/utils/dummy_data.py - dummy NICEState for UI development and testing
- assets/The University logo.png - Cambridge logo for the UI header
- MOHAN_README.md - this document

---

## Contact

For questions about the UI module contact Mohan.
For questions about the pipeline, nodes, or state schema contact Aydin or Bihter.
For questions about data curation or validation contact Farah, Angelo, or Lemmy.
