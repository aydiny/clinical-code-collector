# main.py (in the root folder)

import asyncio
import sys
from dotenv import load_dotenv
from src.state import NICEState
from src.graph import build_graph

# Dummy human review node (since we haven't built the real UI yet)
async def human_review_node(state: NICEState) -> dict:
    print("\n[human_review] 👤 Processing human feedback...")
    return {"human_review_flag": False}

async def main():
    load_dotenv()
    print("🏥 Starting NICE Clinical Cohort Pipeline...")
    
    # 1. Define the user's research question
    research_question = (
        "Identify all patients with heart failure with reduced ejection fraction "
        "(HFrEF) suitable for SGLT2 inhibitor therapy review in primary care"
    )
    
    # 2. Build the LangGraph app
    app = build_graph()
    
    # 3. Initialize the starting state
    initial_state = {
        "research_question": research_question,
        "iteration_count": 0
    }
    
    # Thread ID is required for memory checkpointers!
    config = {"configurable": {"thread_id": "test-run-001"}}

    print("\n=======================================================")
    print("🚀 RUNNING NICE CLINICAL PIPELINE (NODES 1 → 4)")
    print("=======================================================\n")

    # 4. Run the graph up to the breakpoint
    async for event in app.astream(initial_state, config=config):
        for node_name, state_update in event.items():
            print(f"✅ Completed Node: {node_name}")

    # 5. Inspect the paused state
    print("\n=======================================================")
    print("⏸️  PIPELINE PAUSED AT HUMAN REVIEW CHECKPOINT")
    print("=======================================================\n")
    
    current_state = app.get_state(config).values
    justifications = current_state.get("justifications", [])
    
    print(f"Generated {len(justifications)} Justifications. Here are the top 3:")
    for j in justifications[:3]:
        icon = "💊" if j.get("category") == "Medication" else "🔬" if j.get("category") == "Observation" else "🩺"
        print(f"\n{icon} [{j['tier'].upper()}] {j['snomed_id']} - {j['preferred_term']}")
        print(f"   Reason: {j['justification_text']}")
        print(f"   Source: {j['source_chunk']}")

    # 6. Simulate Human Approval and finish
    print("\n=======================================================")
    print("🤖 SIMULATING HUMAN APPROVAL & RESUMING PIPELINE")
    print("=======================================================\n")
    
    app.update_state(config, {"human_feedback": "Looks great, approved!", "human_review_flag": False})

    async for event in app.astream(None, config=config):
        for node_name, state_update in event.items():
            print(f"✅ Completed Node: {node_name}")

    print("\n🎉 END-TO-END PIPELINE COMPLETE!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())
