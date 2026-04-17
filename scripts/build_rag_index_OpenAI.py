import os
import shutil
import subprocess
import time
from langchain_community.document_loaders import DirectoryLoader, UnstructuredPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv

load_dotenv()

# --- FOLDER AND MODEL SETTINGS ---
PDF_DOCS_DIR = "data/raw/methodology_pdfs"
CHROMA_DB_DIR = "data/vectorstore/methodology_db_openai"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

def prepare_vector_database(pdf_dir=PDF_DOCS_DIR, db_dir=CHROMA_DB_DIR, model_name=EMBEDDING_MODEL_NAME):
    """
    Reads PDFs using 'Unstructured' via DirectoryLoader.
    Uses the 'fast' strategy since the goal is to search for DEFINITIONS and RULES rather than tables/SNOMED codes.
    """
    print(f"--- Phase 0: Data Ingestion Started ---")

    if os.path.exists(db_dir):
        print(f"[*] Deleting old database: {db_dir}")
        shutil.rmtree(db_dir)

    if not os.path.exists(pdf_dir) or len(os.listdir(pdf_dir)) == 0:
        print(f"[!] ERROR: Folder '{pdf_dir}' not found or is empty.")
        return

    # Using LangChain DirectoryLoader + UnstructuredPDFLoader
    # This is a more robust way to load a directory of PDFs.
    # It avoids the 'UnstructuredDirectoryLoader' import error.
    print(f"[*] Loading PDF documents by analyzing them with 'Unstructured' (fast mode)...")

    loader = DirectoryLoader(
        pdf_dir,
        glob="**/*.pdf",
        loader_cls=UnstructuredPDFLoader,
        loader_kwargs={"strategy": "fast", "mode": "single"} # 'fast' mode preserves text hierarchy optimally
    )
    documents = loader.load()

    if not documents:
        print("[!] No PDF documents could be read. Cancelling operation.")
        return

    print(f"[*] PDFs successfully processed and structurally loaded.")

    # Text Splitting (Chunking)
    # Since rules and definitions usually span 1-2 paragraphs,
    # chunk_size is optimized to 1500 (approx. 250-300 words).
    print("[*] Splitting structured documents into chunks for the vector database...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
        length_function=len
    )
    chunks = text_splitter.split_documents(documents)
    print(f"[*] PDFs split into a total of {len(chunks)} contextual chunks.")

    # 6. Embedding Model and Database Saving
    print(f"[*] Initializing OpenAI Embedding Model: '{model_name}'")
    try:
        embeddings = OpenAIEmbeddings(model=model_name)
    except Exception as e:
        print(f"[!] Error connecting to OpenAI. Error: {e}")
        return

    print(f"[*] Generating embeddings and saving to ChromaDB at: {db_dir}")

    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=db_dir
    )

    print(f"--- Data Ingestion Complete! ---")
    print(f"[*] Your vector database was successfully saved to the '{db_dir}' folder.")


if __name__ == "__main__":
    # Calling the function
    prepare_vector_database()

    # Zip the Database for GitHub Download
    print("[*] Zipping the vector database...")
    
    # Use the variable you defined at the top!
    if os.path.exists(CHROMA_DB_DIR):
        # We save the zip file as 'methodology_db_openai.zip' in the current folder
        shutil.make_archive("methodology_db_openai", 'zip', CHROMA_DB_DIR)
        print("[*] Success! Database zipped and ready for upload.")
    else:
        print(f"[!] Error: {CHROMA_DB_DIR} folder not found.")