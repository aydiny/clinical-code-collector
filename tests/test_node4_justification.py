import pytest
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# 👉 UPDATE THIS IMPORT to point to your actual node file
from src.nodes.justification import justification_node

async def test_justification_node_isolation():
    """
    Tests the justification node in isolation by providing fake 
    SNOMED codes and fake RAG context.
    """
    print("\n--- Starting Justification Node Test ---")

    # 1. Mock the State exactly as it would arrive from the previous nodes
    mock_state = {
        "research_question": "Patients with Type 2 diabetes who need further medicines.",
        
        # Fake RAG context wrapped in the XML tags your prompt expects
        "rag_context": (
            "<CHUNK id='0' source='NG28_type_2_diabetes.pdf' page='22'>\n"
            "For adults with type 2 diabetes who are living with obesity who need "
            "further medicines to reach their individualised glycaemic targets, "
            "consider prescribing a GLP-1 receptor agonist.\n"
            "</CHUNK>"
        ),
        
        # Fake SNOMED codes that need justifying
        "validated_codes": [
            {
                "snomed_id": "44054006",
                "preferred_term": "Type 2 diabetes mellitus",
                "tier": "TIER_1"
            },
            {
                "snomed_id": "12345678",
                "preferred_term": "Some completely unrelated fake disease",
                "tier": "TIER_3"
            }
        ]
    }

    # 2. Run the node directly (Since it's async, we await it)
    print("[*] Calling Justification Node (Hitting LLM...)")
    updated_state = await justification_node(mock_state)

    # 3. Extract the results
    # (Update "validated_codes" if your node returns a differently named key)
    justified_codes = updated_state.get("justifications", [])

    print("\n--- LLM Output Results ---")
    for code in justified_codes:
        print(f"\n🩺 Concept: {code.get('preferred_term')} ({code.get('snomed_id')})")
        print(f"   Justification : {code.get('justification_text')}")
        print(f"   Quote         : {code.get('evidence_quote')}")
        print(f"   Source        : {code.get('source_document')}")
        print(f"   Chunk Ref     : {code.get('source_chunk')}")

    # 4. Assertions to prove it worked
    assert len(justified_codes) == 2, "Should return the same number of codes"
    
    # Check the valid code
    valid_code = justified_codes[0]
    assert "justification_text" in valid_code, "Missing justification key"
    assert "evidence_quote" in valid_code, "Missing quote key"
    assert "NG28" in valid_code.get("source_document", ""), "Failed to extract source file"

    # Check the invalid code (LLM should say no evidence found)
    invalid_code = justified_codes[1]
    assert "No direct guideline evidence" in invalid_code.get("justification_text", ""), \
        "LLM hallucinated a justification for a fake disease!"

    print("\n✅ All assertions passed!")

# --- Helper block to run it without pytest if you prefer ---
if __name__ == "__main__":
    asyncio.run(test_justification_node_isolation())