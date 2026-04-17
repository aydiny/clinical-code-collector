import os
from langchain_community.vectorstores import Chroma

# --- DYNAMIC PATHING ---
# Automatically resolve paths based on the GitHub repository structure
# Works flawlessly regardless of where the script is executed.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
PDF_DOCS_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "methodology_pdfs")

# --- FILE MAPPING DICTIONARY ---
# This acts as our "Fast Track" exact mapping to prevent irrelevant searches.
CONDITION_TO_FILE = {
    "type 2 diabetes": "NG28_type_2_diabetes.pdf",
    "obesity": "NG246_obesity.pdf",
    "hypertension": "NG136_hypertension.pdf",
    "heart failure": "NG106_chronic-heart-failure-in-adults.pdf",
    "atrial fibrillation": "NG196_atrial-fibrillation.pdf"
}
QOF_FILE = "quality-outcomes-framework-guidance-for-2025-26.pdf"

# ADVANCED RAG UTILITIES

def get_relevant_pdfs(condition_name: str, pdf_folder: str = PDF_DOCS_DIR) -> list[str]:
    """
    UPGRADED MULTI-ROUTER:
    Scans for ALL matching guidelines in a complex query.
    """
    if not condition_name:
        return []
        
    found_pdfs = []
    cond_lower = condition_name.lower().strip()
    
    # 1. Check dictionary for partial matches
    for key, filename in CONDITION_TO_FILE.items():
        if key in cond_lower:
            found_pdfs.append(filename)
            
    # 2. Dynamic Fallback: Scan folder for keywords not in dictionary
    if not os.path.exists(pdf_folder):
        return found_pdfs
        
    search_terms = cond_lower.replace("-", " ").split()
    for filename in os.listdir(pdf_folder):
        if filename.endswith(".pdf") and filename != QOF_FILE:
            # Avoid duplicates if already added from dictionary
            if filename in found_pdfs: continue
            
            name_lower = filename.lower().replace("_", " ")
            # If a word longer than 4 chars matches the filename, grab it
            if any(term in name_lower for term in search_terms if len(term) > 4):
                found_pdfs.append(filename)
                
    return list(set(found_pdfs)) # Ensure unique filenames


# THE CORE RETRIEVAL ENGINE (Item-Level / Per-Code RAG)

def retrieve_context_for_code(
    snomed_term: str, 
    category: str, 
    primary_condition: str, 
    target_demographic: str,
    vector_db: Chroma
) -> str:
    """
    Takes a single validated SNOMED code and performs a highly targeted, 
    low-k search to find its exact justification in the clinical guidelines.
    """
    demo_prefix = "Pediatric" if target_demographic.lower() == "pediatric" else "Adult"
    
    # 1. SMART ROUTER: Identify which PDFs we are allowed to search
    allowed_pdfs = get_relevant_pdfs(primary_condition)
    
    # Always include QOF
    if QOF_FILE not in allowed_pdfs:
        allowed_pdfs.append(QOF_FILE)

    print(f"[*] Allowed pdf's for RAG: {allowed_pdfs}")

    # Clean the stems for ChromaDB metadata match
    allowed_stems = [f.replace(".pdf", "") for f in allowed_pdfs]

    # ... Build filter as we discussed:
    if len(allowed_stems) == 1:
        clinical_search_filter = {"source_file": allowed_stems[0]}
    else:
        clinical_search_filter = {"source_file": {"$in": allowed_stems}}

    # 2. DYNAMIC QUERY CONSTRUCTION
    # We alter the query based on whether it's a Diagnosis, Med, or Observation
    if category == "Medication":
        query = f" dosage titration, prescribing rules, and administration of {snomed_term}"
    elif category == "Observation":
        query = f" monitoring frequency, clinical targets, and measurement of  {snomed_term}"
    else: # Diagnosis
        query = f"definitions, diagnostic criteria, and clinical signs of {snomed_term}"

    # 3. HIGH-PRECISION RETRIEVAL
    # Notice k=2. We want a sniper rifle approach, not a shotgun.
    retrieved_docs = vector_db.max_marginal_relevance_search(
        query,
        k=5,          
        fetch_k=20,    
        lambda_mult=0.7, # Higher lambda favors relevance over diversity for specific codes
        filter=clinical_search_filter
    )

    print ("# retrieved docs for RAG:" , len(retrieved_docs))

    # 4. DEMOGRAPHIC SHIELDING
    valid_chunks = []
    for doc in retrieved_docs:
        content_lower = doc.page_content.lower()
        has_pediatric_terms = any(term in content_lower for term in ["children", "young person", "paediatric", "pediatric", "child", "infant"])
        has_adult_terms = "adult" in content_lower

        if target_demographic.lower() == "pediatric":
            if has_adult_terms and not has_pediatric_terms: continue
        else:
            if has_pediatric_terms and not has_adult_terms: continue 
            
        valid_chunks.append(doc)

    # 5. FORMATTING FOR THE LLM
    # Combine the valid chunks into a single readable string with citations
    if not valid_chunks:
        return "No specific guideline context found."

    context_blocks = []
    for i, doc in enumerate(valid_chunks):
        source = doc.metadata.get('display_name', doc.metadata.get('source_file', 'Unknown Guideline'))
        page = doc.metadata.get('page_number', 'N/A')
        
        # Wrap each chunk in its own tag with metadata attributes
        block = f'<CHUNK index="{i+1}" source="{source}" page="{page}">\n{doc.page_content}\n</CHUNK>'
        context_blocks.append(block)

    return "\n\n".join(context_blocks)
