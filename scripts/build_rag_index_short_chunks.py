# scripts/build_rag_index.py
"""
Run once to build the NICE guidelines vector store.
Output: data/vectorstore/methodology_db_openai/
"""
import os
import re
import shutil
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

# --- FOLDER AND MODEL SETTINGS ---
DOCS_DIR = Path("data/raw/methodology_pdfs")
VECTORSTORE_DIR = "data/vectorstore/short_chunks"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

def clean_pdf_text(text: str) -> str:
    """Removes excessive newlines and chaotic PDF spacing."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\s+([?.!,;])', r'\1', text)
    return text.strip()

def _display_name(stem: str) -> str:
    names = {
        "NG106_chronic-heart-failure-in-adults":        "NICE NG106 — Chronic Heart Failure",
        "NG28_type_2_diabetes":                         "NICE NG28 — Type 2 Diabetes",
        "NG196_atrial-fibrillation":                    "NICE NG196 — Atrial Fibrillation",
        "NG246_obesity":                                "NICE NG246 — Obesity",
        "NG136_hypertension":                           "NICE NG136 — Hypertension",
        "nice_ng203_ckd":                               "NICE NG203 — Chronic Kidney Disease",
        "quality-outcomes-framework-guidance-for-2025-26":     "QOF Business Rules 2025/26",
    }
    return names.get(stem, stem.replace("_", " ").title())


def build_index():
    print(f"--- Phase 0: Data Ingestion Started ---")

    if os.path.exists(VECTORSTORE_DIR):
        print(f"[*] Deleting old database: {VECTORSTORE_DIR}")
        shutil.rmtree(VECTORSTORE_DIR)

    if not DOCS_DIR.exists() or not any(DOCS_DIR.iterdir()):
        print(f"[!] ERROR: Folder '{DOCS_DIR}' not found or is empty.")
        return

    docs = []
    
    # 1. Native Pathlib Iteration + Fast PyMuPDF Loading
    print(f"[*] Loading and cleaning PDF documents using PyMuPDF...")
    for pdf_path in DOCS_DIR.glob("*.pdf"):
        loader = PyMuPDFLoader(str(pdf_path))
        pages = loader.load()

        for page in pages:
            # Clean the chaotic PDF text
            page.page_content = clean_pdf_text(page.page_content)
            
            # Inject rich, UI-ready metadata
            stem = pdf_path.stem
            page.metadata["source_file"] = stem
            page.metadata["display_name"] = _display_name(stem)
            
            # PyMuPDF sets 'page' as 0-indexed, let's make it 1-indexed for human citations
            page.metadata["page_number"] = page.metadata.get("page", 0) + 1

        docs.extend(pages)
        print(f"  ↳ Loaded {len(pages)} pages from {pdf_path.name}")

    if not docs:
        print("[!] No documents could be read. Cancelling operation.")
        return

    # ── THE GOLDILOCKS CHUNKING STRATEGY ──
    # 800 chars (~150 words) perfectly captures a full clinical rule without vector dilution.
    # 150 char overlap ensures rules crossing page/paragraph boundaries aren't severed.
    print(f"\n[*] Splitting structured documents into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        length_function=len,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = splitter.split_documents(docs)
    print(f"[*] PDFs split into a total of {len(chunks)} contextual chunks.")

    # 3. Embed and Persist
    print(f"[*] Initializing OpenAI Embedding Model: '{EMBEDDING_MODEL_NAME}'")
    try:
        embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME)
    except Exception as e:
        print(f"[!] Error connecting to OpenAI. Error: {e}")
        return

    print(f"[*] Generating embeddings and saving to ChromaDB at: {VECTORSTORE_DIR}")
    # langchain-chroma automatically persists; no need to call .persist() manually
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTORSTORE_DIR
    )

    print(f"--- Data Ingestion Complete! ---")
    print(f"[*] Your vector database was successfully saved to '{VECTORSTORE_DIR}'.")

if __name__ == "__main__":
    build_index()

    print("\n[*] Zipping the vector database for GitHub...")
    if os.path.exists(VECTORSTORE_DIR):
        shutil.make_archive("methodology_db_openai", 'zip', VECTORSTORE_DIR)
        print("[*] Success! Database zipped and ready for upload.")
    else:
        print(f"[!] Error: {VECTORSTORE_DIR} folder not found.")



