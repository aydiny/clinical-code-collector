"""
Shared retriever — used by Node 1 and Node 4.
Built once at import time, reused across pipeline runs.
"""
from pathlib import Path
import os

# 1. Get the absolute path to the directory where THIS file is located
# 2. Go up enough levels to hit the project root (where the 'data' folder lives)
# If this file is in src/nodes/, we go up 2 levels.
ROOT_DIR = Path(__file__).resolve().parent.parent.parent 

# 3. Join it to the database folder
VECTORSTORE = os.path.join(ROOT_DIR, "data", "vectorstore", "methodology_db")

# Add a quick print for the Render logs so you can see exactly where it's looking
print(f"--- DEBUG: Looking for VectorDB at: {VECTORSTORE}")
print(f"--- DEBUG: Does path exist? {os.path.exists(VECTORSTORE)}")

_retriever = None  # singleton — load once per process

def get_retriever(k: int = 4):
    """
    Load and return the NICE guidelines retriever using local Ollama.
    k: number of chunks to retrieve per query.
    Returns None gracefully if vector store not built yet.
    """
    global _retriever

    if _retriever is not None:
        return _retriever

    # Guard — vector store not built yet
    if not Path(VECTORSTORE).exists():
        print(f"[retriever] ⚠️  Vector store not found at '{VECTORSTORE}'")
        print("[retriever]    RAG disabled — run scripts/build_rag_index.py to enable")
        return None

    # Lazy imports — only load heavy dependencies if vector store exists
    try:
        # CHANGED 2: Swapped OpenAI for Ollama
        from langchain_ollama import OllamaEmbeddings
        from langchain_community.vectorstores import Chroma

        # CHANGED 3: Initialized the exact same embedding model used during ingestion
        embeddings = OllamaEmbeddings(model="nomic-embed-text")
        
        vectorstore = Chroma(
            persist_directory=VECTORSTORE,
            embedding_function=embeddings
        )
        
        _retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )
        print("[retriever] ✅ NICE guidelines vector store loaded via Ollama")
        return _retriever

    except ImportError as e:
        print(f"[retriever] ⚠️  Missing dependency: {e}")
        # CHANGED 4: Updated to reflect the uv pip command and new libraries
        print("[retriever]    Run: uv pip install langchain-community langchain-ollama chromadb")
        return None

    except Exception as e:
        print(f"[retriever] ⚠️  Failed to load vector store: {e}")
        print("[retriever]    Hint: Is Ollama running on your local machine?")
        return None