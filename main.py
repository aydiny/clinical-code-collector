# main.py (in the root folder)

import asyncio
import sys
from dotenv import load_dotenv
from src.state import NICEState
from src.graph import build_graph
import json

# 1. Load environment variables first!
load_dotenv()

# 2. 🚀 EXPOSE THE GRAPH GLOBALLY SO STREAMLIT CAN IMPORT IT
app = build_graph()

# Dummy human review node (since we haven't built the real UI yet)
async def human_review_node(state: NICEState) -> dict:
    print("\n[human_review] 👤 Processing human feedback...")
    return {"human_review_flag": False}

async def main():
    print("🏥 Starting NICE Clinical Cohort Pipeline...")
    
    # 1. Define the user's research question
    research_question = (
        "Identify all patients with heart failure with reduced ejection fraction "
        "(HFrEF) suitable for SGLT2 inhibitor therapy review in primary care"
    )
    
    # 2. Initialize the starting state
    initial_state = {
        "research_question": research_question,
        "iteration_count": 0
    }
    
    # Thread ID is required for memory checkpointers!
    config = {"configurable": {"thread_id": "test-run-001"}}

    print("\n=======================================================")
    print("🚀 RUNNING NICE CLINICAL PIPELINE (NODES 1 → 4)")
    print("=======================================================\n")

    # 3. Run the graph up to the breakpoint (Using the globally defined 'app')
    async for event in app.astream(initial_state, config=config):
        for node_name, state_update in event.items():
            print(f"✅ Completed Node: {node_name}")

    # 4. Inspect the paused state
    print("\n=======================================================")
    print("⏸️  PIPELINE PAUSED AT HUMAN REVIEW CHECKPOINT")
    print("=======================================================\n")
    
    current_state = app.get_state(config).values
    justifications = current_state.get("justifications", [])
    
    print(f"Generated {len(justifications)} Justifications. Here are the top 3:")
    for j in justifications[:3]:
        icon = "💊" if j.get("category") == "Medication" else "🔬" if j.get("category") == "Observation" else "🩺"
        print(f"\n{icon} [{j.get('tier', 'Unknown').upper()}] {j.get('snomed_id', '')} - {j.get('preferred_term', '')}")
        print(f"   Reason: {j.get('justification_text', '')}")
        print(f"   Source: {j.get('source_chunk', '')}")

   # 5. Simulate Human Approval and finish
    print("\n" + "="*55)
    print("🤖 SIMULATING HUMAN APPROVAL & RESUMING PIPELINE")
    print("="*55 + "\n")
    
    # We update the state to clear the flag and provide feedback
    app.update_state(config, {"human_feedback": "Approved", "human_review_flag": False})

    # Run the remaining nodes (Output Generator, etc.)
    async for event in app.astream(None, config=config):
        for node_name, _ in event.items():
            print(f"✅ Completed Node: {node_name}")

    # --- THE FIX: Get the final state after the graph finishes ---
    final_state = app.get_state(config).values
    all_justifications = final_state.get("justifications", [])

    # 6. View the Justification Texts
    print("\n" + "="*55)
    print(f"📄 FULL REPORT: {len(all_justifications)} CODES JUSTIFIED")
    print("="*55)
    
    for j in all_justifications:
        icon = "🩺" if j.get("category") == "Diagnosis" else "💊"
        print(f"\n{icon} {j.get('snomed_id', '')} | {j.get('preferred_term', '')}")
        print(f"   Tier: {j.get('tier', 'Unknown').upper()}")
        print(f"   Justification: {j.get('justification_text', '')}")
        print(f"   Evidence: {j.get('source_chunk', 'N/A')}")

    # 7. Save to JSON
    with open("heart_failure_justifications.json", "w") as f:
        json.dump(all_justifications, f, indent=4)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())