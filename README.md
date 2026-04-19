# NICE Clinical Code Recommender

This repository contains the NICE clinical coding assistant app built with Streamlit and LangGraph.
For assessment, run the app from `app.py`:

```bash
streamlit run app.py
```

---

## 1) Prerequisites

- Python `3.10+` (recommended `3.11`)
- `pip`
- Internet access for model/API calls

---

## 2) Project setup

From the project root:

```bash
python -m venv .venv
```

Activate the environment:

- Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

- macOS/Linux (bash/zsh):

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 3) Environment variables

Create a `.env` file in the repository root and add:

```env
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_or_anon_key
```

Optional (only needed for FHIR integration scripts/tests):

```env
FHIR_CLIENT_ID=your_fhir_client_id
FHIR_CLIENT_SECRET=your_fhir_client_secret
```

---

## 4) Run the app (assessment entrypoint)

Start Streamlit from the repo root:

```bash
streamlit run app.py
```

Expected local URL:

- `http://localhost:8501`

---

## 5) Notes for tutor assessment

- Entrypoint is `app.py` (Streamlit UI).
- The app imports and runs the LangGraph pipeline via `main.py`.
- Feedback actions attempt to write to Supabase (`nice_feedback` table), so valid Supabase credentials are required for full end-to-end behavior.

---

## 6) Quick troubleshooting

- `ModuleNotFoundError`: ensure virtual environment is active and rerun `pip install -r requirements.txt`.
- `OpenAI` auth errors: verify `OPENAI_API_KEY` in `.env`.
- Supabase connection/write errors: verify `SUPABASE_URL` and `SUPABASE_KEY`.
- Streamlit command not found: run `python -m streamlit run app.py`.
