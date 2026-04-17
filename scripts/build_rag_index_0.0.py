# scripts/build_rag_index.py
"""
Run once to build the NICE guidelines vector store.
Output: data/vectorstore/nice_guidelines/
"""
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from pathlib import Path

DOCS_DIR      = Path("data/docs/nice_guidelines/")
VECTORSTORE   = "data/vectorstore/nice_guidelines"

def build_index():
    docs = []

    for pdf_path in DOCS_DIR.glob("*.pdf"):
        loader = PyPDFLoader(str(pdf_path))
        pages  = loader.load()

        # Add source metadata to every chunk — critical for citations
        for page in pages:
            page.metadata["source"]       = pdf_path.stem
            page.metadata["display_name"] = _display_name(pdf_path.stem)

        docs.extend(pages)
        print(f"Loaded {len(pages)} pages from {pdf_path.name}")

    # Chunk — overlap preserves context across page boundaries
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(docs)
    print(f"Total chunks: {len(chunks)}")

    # Embed and persist — runs once, reused every pipeline call
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTORSTORE
    )
    vectorstore.persist()
    print(f"Vector store saved to {VECTORSTORE}")


def _display_name(stem: str) -> str:
    names = {
        "nice_ng106_heart_failure":       "NICE NG106 — Chronic Heart Failure",
        "nice_ng28_type2_diabetes":       "NICE NG28 — Type 2 Diabetes",
        "nice_ng196_atrial_fibrillation": "NICE NG196 — Atrial Fibrillation",
        "nice_ng115_copd":                "NICE NG115 — COPD",
        "nice_ng136_hypertension":        "NICE NG136 — Hypertension",
        "nice_ng203_ckd":                 "NICE NG203 — Chronic Kidney Disease",
        "qof_business_rules_2025_26":     "QOF Business Rules 2025/26",
    }
    return names.get(stem, stem)


if __name__ == "__main__":
    build_index()
