"""
Shared retriever — used by Node 1 and Node 4.
Built once at import time, reused across pipeline runs.
"""
from pathlib import Path

VECTORSTORE = "data/vectorstore/nice_guidelines"

_retriever = None  # singleton — load once per process


def get_retriever(k: int = 4):
    """
    Load and return the NICE guidelines retriever.
    k: number of chunks to retrieve per query.
    Returns None gracefully if vector store not built yet.
    """
    global _retriever

    if _retriever is not None:
        return _retriever

    # Guard — vector store not built yet (RAG team task)
    if not Path(VECTORSTORE).exists():
        print(f"[retriever] ⚠️  Vector store not found at '{VECTORSTORE}'")
        print("[retriever]    RAG disabled — run scripts/build_rag_index.py to enable")
        return None

    # Lazy imports — only load heavy dependencies if vector store exists
    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_community.vectorstores import Chroma

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vectorstore = Chroma(
            persist_directory=VECTORSTORE,
            embedding_function=embeddings
        )
        _retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )
        print("[retriever] ✅ NICE guidelines vector store loaded")
        return _retriever

    except ImportError as e:
        print(f"[retriever] ⚠️  Missing dependency: {e}")
        print("[retriever]    Run: pip install langchain-community langchain-openai chromadb")
        return None

    except Exception as e:
        print(f"[retriever] ⚠️  Failed to load vector store: {e}")
        return None
