import os
from langchain_community.vectorstores import Chroma


# --- FILE MAPPING DICTIONARY ---
# This acts as our "Fast Track" exact mapping to prevent irrelevant searches.
CONDITION_TO_FILE = {
    "type 2 diabetes": "NG28_type_2_diabetes.pdf",
    "obesity": "NG246_obesity.pdf",
    "hypertension": "NG136_hypertension.pdf",
    "heart failure": "NG106_chronic-heart-failure-in-adults.pdf",
    "atrial fibrillation": "NG196_atrial-fibrillation.pdf"
}
QOF_FILE = "qof_combined.pdf"

PDF_DOCS_DIR = "data/raw/methodology_pdfs"

# -------------------------------------------------------------------
# ADVANCED RAG UTILITIES
# -------------------------------------------------------------------

def clean_boilerplate_text(text: str) -> str:
    """
    Cleans up repetitive boilerplate texts, headers, and footers from NICE guidelines
    so they don't distract the LLM during the synthesis phase.
    """
    noise = [
        "© NICE 2026. All rights reserved.",
        "Subject to Notice of rights",
        "(https://www.nice.org.uk/terms-and- conditions#notice-of-rights)",
        "(https://www.nice.org.uk/terms-and-conditions#notice-of-rights)",
        "Return to recommendations",
        "Why the committee made the recommendations",
        "How the recommendations might affect practice"
    ]
    cleaned_text = text
    for n in noise:
        cleaned_text = cleaned_text.replace(n, "")
    
    # Remove stray "Page X of Y" lines
    lines = [line for line in cleaned_text.split('\n') if not line.strip().startswith("Page ") and "of 1" not in line]
    return " ".join(lines).strip()

def get_relevant_pdf(condition_name: str, pdf_folder: str = PDF_DOCS_DIR) -> str:
    """
    SMART DOCUMENT ROUTER:
    First checks the exact dictionary mapping. If not found, it dynamically scans 
    the pdf_docs directory to find a matching filename, preventing future bottlenecks.
    """
    if not condition_name:
        return None
        
    # 1. Fast Track: Exact Match in Dictionary
    if condition_name in CONDITION_TO_FILE:
        return CONDITION_TO_FILE[condition_name]
        
    # 2. Dynamic Fallback: Scan the folder for filenames containing the condition words
    print(f"[*] '{condition_name}' not found in dictionary. Scanning '{pdf_folder}' dynamically...")
    if not os.path.exists(pdf_folder):
        return None
        
    search_terms = condition_name.lower().replace("-", " ").split()
    
    for filename in os.listdir(pdf_folder):
        if filename.endswith(".pdf") and filename != QOF_FILE:
            name_lower = filename.lower().replace("_", " ")
            if any(term in name_lower for term in search_terms if len(term) > 4):
                print(f"[*] Auto-mapped '{condition_name}' to '{filename}' based on filename match.")
                return filename
                
    return None

# -------------------------------------------------------------------
# THE CORE RETRIEVAL ENGINE (Your Grounded Logic)
# -------------------------------------------------------------------

def grounded_retrieval(research_question: str, vector_db: Chroma) -> list:
    """
    Takes the RAW user query, uses the Smart Router to target specific files, 
    performs an MMR search, and cleans the output for LLM Grounding.
    """
    print("\n--- [PHASE 1] GROUNDED RAG RETRIEVAL STARTED ---")
    
    # 1. SMART ROUTER INTEGRATION
    clinical_allowed_files = []
    question_lower = research_question.lower()
    
    # Scan the raw question for known condition keywords
    for condition in CONDITION_TO_FILE.keys():
        if condition.lower() in question_lower:
            # If a condition is mentioned, route it through Bihter's method
            filename = get_relevant_pdf(condition_name=condition)
            
            if filename:
                # THE FIX: Add BOTH Windows and Linux path variations to the allowed list!
                linux_path = f"{PDF_DOCS_DIR}/{filename}"
                windows_path = f"{PDF_DOCS_DIR}\\{filename}".replace("/", "\\")
                
                if linux_path not in clinical_allowed_files:
                    clinical_allowed_files.append(linux_path)
                if windows_path not in clinical_allowed_files:
                    clinical_allowed_files.append(windows_path)
                    
                print(f"[*] Smart Router activated: Limiting search to '{filename}' (Omni-Slash active)")

    # If the router found a file, apply the filter. Otherwise, search the whole DB.
    clinical_search_filter = {"source": {"$in": clinical_allowed_files}} if clinical_allowed_files else None
    
    if not clinical_allowed_files:
         print("[*] No exact condition matched in routing. Performing global database search.")

    # 2. SEMANTIC MMR SEARCH
    print(f"    -> Querying Vector DB with raw research question...")
    docs = vector_db.max_marginal_relevance_search(
        research_question,
        k=8,          # Final number of chunks to send to the LLM
        fetch_k=30,   # Initial pool to pick diverse chunks from
        lambda_mult=0.5,
        filter=clinical_search_filter
    )
        
    # 3. DEDUPLICATION AND CLEANING
    print("[*] Deduplicating and cleaning boilerplate text...")
    unique_chunks = {}
    
    for doc in docs:
        doc_snippet = doc.page_content[:100]
        if doc_snippet not in unique_chunks:
            # Apply Bihter's boilerplate cleaner here!
            doc.page_content = clean_boilerplate_text(doc.page_content)
            unique_chunks[doc_snippet] = doc
            
    final_documents = list(unique_chunks.values())
    print(f"--- [PHASE 1 COMPLETE]: Retrieved {len(final_documents)} chunks for LLM Grounding ---")

    return final_documents