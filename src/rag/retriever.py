import os
from langchain_community.vectorstores import Chroma

# --- DYNAMIC PATHING ---
# Automatically resolve paths based on the GitHub repository structure
# Works flawlessly regardless of where the script is executed.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
PDF_DOCS_DIR = os.path.join(PROJECT_ROOT, "data", "methodology_pdfs")

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

# ADVANCED RAG UTILITIES

def get_relevant_pdf(condition_name: str, pdf_folder: str = PDF_DOCS_DIR) -> str:
    """
    SMART DOCUMENT ROUTER:
    Checks the exact dictionary mapping. If not found, dynamically scans 
    the local PDF directory to find a matching filename.
    """
    if not condition_name:
        return None
        
    # 1. Fast Track: Exact Match in Dictionary
    cond_lower = condition_name.lower().strip()
    if cond_lower in CONDITION_TO_FILE:
        return CONDITION_TO_FILE[cond_lower]
        
    # 2. Dynamic Fallback: Scan the folder for filenames containing the condition words
    print(f"[*] '{condition_name}' not found in dictionary. Scanning '{pdf_folder}' dynamically...")
    if not os.path.exists(pdf_folder):
        return None
        
    search_terms = cond_lower.replace("-", " ").split()
    
    for filename in os.listdir(pdf_folder):
        if filename.endswith(".pdf") and filename != QOF_FILE:
            name_lower = filename.lower().replace("_", " ")
            if any(term in name_lower for term in search_terms if len(term) > 4):
                print(f"[*] Auto-mapped '{condition_name}' to '{filename}' based on filename match.")
                return filename
                
    return None


# THE CORE RETRIEVAL ENGINE (Our Grounded Logic)

def advanced_retrieval(extracted_info: dict, vector_db: Chroma) -> list:
    """
    Takes the structured output from Node 1 (GPT-4o) and performs a highly filtered, 
    MMR-based search on ChromaDB, applying Demographic, QOF, and Exclusion shields.
    """
    print("\n--- [PHASE 2] ADVANCED RAG RETRIEVAL STARTED ---")
    
    primary = extracted_info.get('primary_condition', '')
    related_conditions = extracted_info.get('related_conditions', [])
    qof_prefix = extracted_info.get('qof_domain_prefix', '')
    target_demographic = extracted_info.get('target_demographic', 'adult').lower()
    
    # Combine all explicit exclusions for the Exclusion Shield
    exclusions = (
        extracted_info.get('excluded_diagnoses', []) + 
        extracted_info.get('excluded_medications', []) + 
        extracted_info.get('excluded_observations', [])
    )
        
    # Build allowed files list for clinical searches using the SMART ROUTER
    clinical_allowed_files = []
    primary_pdf = get_relevant_pdf(primary)
    
    if primary_pdf:
        clinical_allowed_files.append(primary_pdf)
        
    for related in related_conditions:
        related_pdf = get_relevant_pdf(related)
        if related_pdf and related_pdf not in clinical_allowed_files:
            clinical_allowed_files.append(related_pdf)
            
    print(f"[*] Target Demographic identified as: {target_demographic.upper()}")
    print(f"[*] Applying strict clinical metadata filter. Allowed files: {clinical_allowed_files}")
    
    clinical_search_filter = None
    if clinical_allowed_files:
        if len(clinical_allowed_files) == 1:
            clinical_search_filter = {"source": {"$contains": clinical_allowed_files[0]}}
        else:
            # If multiple files are allowed, use the $or operator combined with $contains
            clinical_search_filter = {"$or": [{"source": {"$contains": f}} for f in clinical_allowed_files]}
    
    all_retrieved_documents = []
    demo_prefix = "Pediatric" if target_demographic == "pediatric" else "Adult"
    
    # --- QUERY 1: QOF Specific Query (Primary Condition Only) ---
    if primary:
        qof_query = f"QOF indicator business rules register {qof_prefix} {primary}"
        print(f"    -> Querying Vector DB: '{qof_query}' (Strict QOF File Filter - Similarity Only)")
        docs = vector_db.similarity_search(
            qof_query,
            k=10,
            filter={"source": {"$contains": QOF_FILE}}
        )
        all_retrieved_documents.extend(docs)
        
        # --- QUERY 2: Clinical Definitions & Management (Primary) ---
        clin_query = f"{demo_prefix} Definitions, diagnostic criteria, clinical management rules, pharmacological treatment {primary}"
        print(f"    -> Querying Vector DB: '{clin_query}' (Clinical Filter)")
        docs = vector_db.max_marginal_relevance_search(
            clin_query,
            k=10,
            fetch_k=20,
            lambda_mult=0.5,
            filter=clinical_search_filter
        )
        all_retrieved_documents.extend(docs)
    
    # --- QUERY 3: Related Conditions Context ---
    for related in related_conditions:
        rel_query = f"{demo_prefix} Diagnostic criteria clinical management {related}"
        print(f"    -> Querying Vector DB: '{rel_query}' (Related Filter)")
        docs = vector_db.max_marginal_relevance_search(
            rel_query,
            k=5,
            fetch_k=10,
            lambda_mult=0.5,
            filter=clinical_search_filter
        )
        all_retrieved_documents.extend(docs)
        
    # --- DEDUPLICATION AND DYNAMIC SHIELDING ---
    print("[*] Deduplicating, applying dynamic demographic and exclusion shields...")
    unique_chunks = {}
    
    for doc in all_retrieved_documents:
        content_lower = doc.page_content.lower()
        source_file = os.path.basename(doc.metadata.get('source', ''))
        
        # 1. QOF Shield
        if source_file == QOF_FILE and qof_prefix:
            if qof_prefix.lower() not in content_lower:
                continue 

        # 2. Demographic Shield
        has_pediatric_terms = any(term in content_lower for term in ["children", "young person", "paediatric", "pediatric", "child", "infant"])
        has_adult_terms = "adult" in content_lower

        if target_demographic == "pediatric":
            if has_adult_terms and not has_pediatric_terms: continue
        else:
            if has_pediatric_terms and not has_adult_terms: continue 

        # 3. Exclusion Shield
        should_exclude = False
        if exclusions:
            for exc in exclusions:
                if exc.strip() and exc.strip().lower() in content_lower:
                    should_exclude = True
                    break
                    
        if should_exclude:
            continue

        # 4. Deduplication
        doc_snippet = doc.page_content[:100]
        if doc_snippet not in unique_chunks:
            unique_chunks[doc_snippet] = doc
            
    final_documents = list(unique_chunks.values())
    print(f"--- [PHASE 2 COMPLETE]: Retrieved {len(final_documents)} highly relevant, {target_demographic}-focused chunks ---")
    return final_documents
