# NICE RAG — AI-Assisted Clinical Code Recommendation System

## Overview
This project builds an AI-assisted pipeline to support NICE analysts in generating
clinical code lists for defined conditions. It uses LangGraph to orchestrate a
multi-node pipeline integrating RAG, deterministic validation, and explainable AI.

## Folder Structure
```
NICE_RAG/
│
├── data/
│   ├── raw/
│   │   ├── snomed/            # Raw SNOMED source files (CSVs, JSONs)
│   │   └── nice_guidelines/   # Raw NICE PDF files (NG28, NG106, NG196)
│   └── processed/
│       ├── snomed/            # Cleaned, parsed SNOMED data
│       └── nice_guidelines/   # Extracted text from PDFs
│
├── vectorstores/
│   ├── snomed_codes/          # ChromaDB Store A - SNOMED code embeddings
│   └── nice_guidelines/       # ChromaDB Store B - NICE guideline embeddings
│
├── src/
│   ├── ingestion/             # Scripts to parse and embed source data
│   ├── retrieval/             # Retrievers for each vector store
│   ├── nodes/                 # LangGraph node implementations
│   ├── graph/                 # LangGraph state and graph definition
│   └── utils/                 # Shared utility functions
│
├── tests/                     # Unit tests for each component
├── notebooks/                 # Exploration and experimentation
├── app.py                     # Streamlit UI entry point
├── requirements.txt           # Python dependencies
├── .env                       # API keys (never push to GitHub)
└── .gitignore                 # Excludes sensitive and large files
```

## Setup
1. Clone the repo
2. Create a virtual environment: python -m venv venv
3. Activate it: source venv/bin/activate
4. Install dependencies: pip install -r requirements.txt
5. Add your API keys to .env
6. Run ingestion scripts to build vector stores
7. Launch the app: streamlit run app.py

## Team
- Project Management: Farah
- Data Preparation: Bihter
- System Architecture: Aydin
- RAG Development: Mohan
- Confidence Scoring: Lemmy
- Evaluation & Explainability: Angelo

## Status
- [ ] Vector Store A (SNOMED) — in progress
- [ ] Vector Store B (NICE guidelines) — in progress
- [ ] Node 1: Query Understanding
- [ ] Node 2: SNOMED Search
- [ ] Node 3: Validation
- [ ] Node 4: Justification
- [ ] Human Review Checkpoint
- [ ] Streamlit UI
