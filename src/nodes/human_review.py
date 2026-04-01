from src.state import NICEState

async def human_review_node(state: NICEState) -> dict:
    """
    Dummy node for testing. In production, the graph pauses BEFORE this node,
    a human reviews the state in the UI, injects feedback, and resumes.
    """
    print("\n[human_review] 👤 Processing human feedback...")
    
    # We just clear the flag to let the pipeline finish
    return {"human_review_flag": False}