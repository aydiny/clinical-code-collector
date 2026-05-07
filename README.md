# 3C: Clinical Code Collector 🏥🤖
<img width="1762" height="1213" alt="3C - Clinical_Code_Collector_Workflow_Final" src="https://github.com/user-attachments/assets/0f71f755-c61f-433a-856f-0479c214cc47" />

> An AI-assisted, agentic pipeline for **defensible, explainable, and auditable** SNOMED CT clinical code discovery — built for NICE (National Institute for Health and Care Excellence).

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_Pipeline-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![LangChain](https://img.shields.io/badge/LangChain-RAG_Framework-1C3C3C?logo=langchain&logoColor=white)](https://langchain.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?logo=openai&logoColor=white)](https://openai.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-orange)](https://www.trychroma.com)
[![Deployed](https://img.shields.io/badge/Deployed-Render-46E3B7?logo=render&logoColor=white)](https://render.com)

---

## 📋 The Problem

Defining patient cohorts for healthcare analysis still relies on **highly manual clinical code-list construction** across fragmented sources. Analysts at NICE must navigate QOF rules, NHS Digital reference sets, and SNOMED-based resources to justify code selections — a process that is slow, inconsistent, and difficult to audit, especially for complex multi-morbidity phenotypes like obesity with Type 2 diabetes.

---

## 💡 The Solution

**3C** transforms a plain English clinical research question into a validated, evidence-grounded, and human-reviewable shortlist of SNOMED CT codes using a **hybrid AI + deterministic pipeline** — combining the semantic flexibility of LLMs with the reliability of deterministic NHS API searches.

> *"Not just an LLM generating codes — a defensible, explainable, and fully auditable evidence trail for expert review."*

---

## 🏗️ Architecture

3C is orchestrated as a **stateful 4-node LangGraph pipeline**, blending LLM reasoning with deterministic data retrieval:

```
[Free-text clinical question]
        │
        ▼
┌───────────────────────────────────────────┐
│  Node 1 · Query Understanding             │
│  GPT-4o-mini → 14-field structured JSON   │
│  + NHS FHIR Terminology Server API        │
│  (SNOMED synonym enrichment)              │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│  Node 2 · Deterministic SNOMED Search     │
│  NHS FHIR API · Concept hierarchy         │
│  traversal across diagnosis / meds /      │
│  observations branches (max recall)       │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│  Node 3 · Deterministic Validator         │
│  Scoring: provenance + consensus +        │
│  cosine similarity + course-check         │
│  → Tier 1 / Tier 2 / Tier 3 assignment   │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│  Node 4 · Justification via RAG           │
│  LangChain: ChromaDB + MMR retrieval      │
│  text-embedding-3-small (1536 dims)       │
│  GPT-4o-mini → exact NICE/QOF evidence   │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│  Human Review Interface                   │
│  Code cards · tier badges · provenance   │
│  flags · confidence scores               │
│  Accept / Reject / Skip + feedback loop  │
└───────────────────────────────────────────┘
```

### Architectural Philosophy: Hybrid LLM + Deterministic

| Component | Approach | Why |
|---|---|---|
| Query understanding | LLM (GPT-4o-mini) | Rules-based parsers fail on implicit context and compound phenotypes |
| SNOMED search | Deterministic (NHS FHIR API) | Guarantees auditability; no hallucinated codes |
| Validation | Deterministic (scoring model) | Patient safety requires reproducible, traceable decisions |
| Justification | RAG (LangChain + Chroma) | Grounds every output in official NICE/QOF guideline text |
| Orchestration | LangGraph (stateful graph) | Full state traceability across nodes; deterministic routing |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Agentic Orchestration** | LangGraph (stateful 4-node pipeline) |
| **RAG Framework** | LangChain (ChromaDB, MMR retrieval, PyMuPDFLoader, RecursiveCharacterTextSplitter) |
| **LLM** | OpenAI GPT-4o-mini |
| **Embeddings** | OpenAI text-embedding-3-small (1536 dimensions) |
| **Vector Store** | ChromaDB |
| **Clinical APIs** | NHS FHIR Terminology Server, QOF rules, NHS Digital Reference Sets, OpenCodelists |
| **Document Parsing** | PyMuPDFLoader + RecursiveCharacterTextSplitter (chunk size: 800) |
| **Retrieval Strategy** | Maximal Marginal Relevance (MMR) — diverse, non-redundant evidence chunks |
| **Deployment** | Render (free tier, 512MB RAM CPU) |
| **Language** | Python 3.10+ |

---

## 🧠 Key Design Decisions

### RAG Approach: Code-Level Retrieval (Approach C)
Three RAG approaches were evaluated:

- **Approach A** — Pre-RAG: structure query with RAG, then justify codes
- **Approach B** — Post-RAG: vectorise structured query fields for chunk retrieval
- **Approach C ✅ (Selected)** — Post-RAG: vectorise each individual SNOMED code's short description to target the most relevant guideline chunks per code, then LLM judges relevance for the research question

Approach C produced **richer, more code-specific justification text** across a wider range of clinically relevant codes.

### Validation Scoring Model
Each candidate code is scored across four signals:

| Signal | Weight | Description |
|---|---|---|
| Provenance | High | Code appears in QOF rules, NHS Digital refsets, or OpenCodelists |
| Consensus | Bonus | Code appears across multiple independent sources |
| Semantic Similarity | Medium | Cosine similarity between code definition and target concept |
| Course Consistency | Adjustment | Acute/chronic alignment with clinical context |

Codes scoring below **0.25** are excluded. Remaining codes are tiered (Tier 1 / 2 / 3) for human review.

### Human-in-the-Loop by Design
AI is a **decision-support tool, not an automated decision-maker**. The human review interface presents code cards with full provenance, tier badges, and evidence quotes — users accept, reject, or skip each code. Feedback is stored persistently to improve future runs.

---

## 📊 Results

**Test Case: "Obesity with Type 2 Diabetes"**

| Pipeline Stage | Result |
|---|---|
| Candidate codes retrieved | 70 |
| Validated codes (post-scoring) | 54 |
| Tier 1 — high confidence | 13 |
| Tier 2 / 3 — human review required | 41 |

**Highlights:**
- `Type 2 diabetes mellitus`, `Brittle type 2 diabetes mellitus`, and 11 more correctly promoted to Tier 1 (confidence: 0.85), appearing across QOF, NHS Digital, and OpenCodelists
- `Type 2 diabetes mellitus in obese` achieved highest semantic score (0.81) with correct NICE NG28 evidence quote (p.48)
- `Dapagliflozin` correctly justified using NICE NG28 (p.98): *"Licensed for adults with type 2 diabetes…"*
- **Cost per query: ~£0.01** | **Runtime: ~2 minutes** | Deployed on 512MB CPU (no GPU required)

---

## ⚙️ Implementation & Economics

| Metric | Value |
|---|---|
| Cost per query | ~£0.01 |
| Average runtime | ~2 minutes |
| Infrastructure | Render free tier (512MB RAM, CPU only) |
| LLM calls per query | Query understanding (1×) + Code justification (1× per validated code) |
| Embedding calls | ~50+ SNOMED codes vectorised per query |

---

## ⚠️ Known Limitations & Future Work

- **Exclusion shield** needs hardening — paediatric and gestational phenotypes are occasionally included incorrectly
- **Tier calibration** needs refinement — codes with very high semantic similarity (e.g., 0.81) can be downgraded to Tier 2 if absent from QOF/NHS curated lists
- **Human feedback loop** is stored but not yet integrated back into the scoring pipeline
- **Precision vs. recall trade-off** — the system currently excels at high-recall discovery; future work focuses on improving shortlist precision without losing rare but relevant codes
- **Benchmarking** against expert-reviewed gold-standard code lists is in progress

---

## 📁 Repository Structure

```
├── src/                    # Core pipeline code
│   ├── pipeline/           # LangGraph node definitions
│   ├── rag/                # LangChain RAG components (Chroma, embeddings, MMR)
│   ├── validator/          # Deterministic scoring & tier assignment
│   └── api/                # NHS FHIR API integration
├── docs/
│   ├── LAB-FAM-NICE-Final-Report.pdf      # Full technical report
│   └── 3C_Clinical_Code_Collector_presentation.pdf  # Presentation deck
└── README.md
```

---

## 👥 Team & Attribution

**Cambridge Data Science Career Accelerator — LAB FAM Group 2 | April 2026**

| Name | Role |
|---|---|
| Ali Aydin Yildiz | Technical Lead — pipeline architecture, LangGraph/LangChain engineering, RAG design, deployment |
| Angelo di Legge | Team member |
| Bihter Ekin Kaplanlioglu | Team member |
| Farhio Ali | Team member |
| Jegamohan Vicneswararajah | Team member |
| Lemmy Emasit | Team member |

---

## 📄 Documentation

- [📋 Full Technical Report](./docs/LAB-FAM-NICE-Final-Report.pdf)
- [🎤 Presentation Deck](./docs/3C_Clinical_Code_Collector_presentation.pdf)

---

## 🔗 Related

- [NHS FHIR Terminology Server](https://ontology.nhs.uk/)
- [NICE NG28 — Type 2 Diabetes in Adults: Management](https://www.nice.org.uk/guidance/ng28)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/)
