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

def get_relevant_pdf(condition_name: str, pdf_folder: str = "pdf_docs") -> str:
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
        clinical_allowed_files.append(f"pdf_docs/{primary_pdf}")
        
    for related in related_conditions:
        related_pdf = get_relevant_pdf(related)
        if related_pdf and f"pdf_docs/{related_pdf}" not in clinical_allowed_files:
            clinical_allowed_files.append(f"pdf_docs/{related_pdf}")
            
    print(f"[*] Target Demographic identified as: {target_demographic.upper()}")
    print(f"[*] Applying strict clinical metadata filter. Allowed files: {clinical_allowed_files}")
    
    clinical_search_filter = {"source": {"$in": clinical_allowed_files}} if clinical_allowed_files else None
    
    all_retrieved_documents = []
    demo_prefix = "Pediatric" if target_demographic == "pediatric" else "Adult"
    
    # --- QUERY 1: QOF Specific Query (Primary Condition Only) ---
    if primary:
        qof_query = f"QOF indicator business rules register {qof_prefix} {primary}"
        print(f"    -> Querying Vector DB: '{qof_query}' (Strict QOF File Filter - Similarity Only)")
        docs = vector_db.similarity_search(
            qof_query,
            k=3,
            filter={"source": f"pdf_docs/{QOF_FILE}"} 
        )
        all_retrieved_documents.extend(docs)
        
        # --- QUERY 2: Clinical Definitions & Management (Primary) ---
        clin_query = f"{demo_prefix} Definitions, diagnostic criteria, clinical management rules, pharmacological treatment {primary}"
        print(f"    -> Querying Vector DB: '{clin_query}' (Clinical Filter)")
        docs = vector_db.max_marginal_relevance_search(
            clin_query,
            k=3,
            fetch_k=15,
            lambda_mult=0.5,
            filter=clinical_search_filter
        )
        all_retrieved_documents.extend(docs)
    
    # --- QUERY 3: Related Conditions Context ---
    for related in related_conditions:
        rel_query = f"{demo_prefix} Diagnostic criteria clinical management {related}"
        print(f"    -> Querying Vector DB: '{rel_query}' (Clinical Filter)")
        docs = vector_db.max_marginal_relevance_search(
            rel_query,
            k=3,
            fetch_k=15,
            lambda_mult=0.5,
            filter=clinical_search_filter
        )
        all_retrieved_documents.extend(docs)
        
    # --- DEDUPLICATION AND DYNAMIC SHIELDING ---
    print("[*] Deduplicating, cleaning, and applying dynamic demographic/exclusion shields...")
    unique_chunks = {}
    
    for doc in all_retrieved_documents:
        content_lower = doc.page_content.lower()
        source_file = doc.metadata.get('source', '')
        
        # 1. QOF DOMAIN SHIELD: Prevent unrelated diseases from leaking through QOF rules
        if "qof_combined" in source_file and qof_prefix:
            if qof_prefix.lower() not in content_lower:
                continue 

        # 2. DYNAMIC DEMOGRAPHIC SHIELD: Prevent adult/pediatric guidelines from mixing
        has_pediatric_terms = any(term in content_lower for term in ["children", "young person", "paediatric", "pediatric", "child", "infant"])
        has_adult_terms = "adult" in content_lower

        if target_demographic == "pediatric":
            # If the patient is a child, block pure adult chunks
            if has_adult_terms and not has_pediatric_terms:
                continue
        else:
            # If the patient is an adult, block pure pediatric chunks
            if has_pediatric_terms and not has_adult_terms:
                continue 

        # 3. EXCLUSION SHIELD: Discard chunks that explicitly mention excluded terms
        should_exclude = False
        if exclusions:
            for exc in exclusions:
                if exc.strip() and exc.strip().lower() in content_lower:
                    should_exclude = True
                    break
                    
        if should_exclude:
            print("    [!] Shield activated: Chunk discarded due to an explicit exclusion rule.")
            continue
            
        doc_snippet = doc.page_content[:100]
        if doc_snippet not in unique_chunks:
            doc.page_content = clean_boilerplate_text(doc.page_content)
            unique_chunks[doc_snippet] = doc
            
    final_documents = list(unique_chunks.values())
    print(f"--- [PHASE 2 COMPLETE]: Retrieved {len(final_documents)} highly relevant, {target_demographic}-focused chunks ---")
    return final_documents
