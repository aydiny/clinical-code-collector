"""
NICE Clinical Code Recommendation System
LangGraph StateGraph — main graph assembly.
Wires all 5 agent nodes together with conditional routing.
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.state import NICEState

# --- Import agent node functions (stubs until each node is built) ---
from src.nodes.query_understanding import query_understanding_node
from src.nodes.snomed_search import snomed_search_node
from src.nodes.validator import validator_node
from src.nodes.justification import justification_node
from src.nodes.human_review import human_review_node


# --- Routing function: Validator → loop back OR proceed ---
def route_after_validator(state: NICEState) -> str:
    """
    Conditional edge after Node 3 (Validator).
    Loops back to SNOMED Search if low-confidence codes remain
    and iteration limit not reached. Otherwise proceeds to Justification.
    """
    if (
        state.get("routing_decision") == "loop_back"
        and state.get("iteration_count", 0) < 3
    ):
        return "snomed_search"
    return "justification"


# --- Build the graph ---
def build_graph():
    graph = StateGraph(NICEState)

    # Register nodes
    graph.add_node("query_understanding", query_understanding_node)
    graph.add_node("snomed_search",       snomed_search_node)
    graph.add_node("validator",           validator_node)
    graph.add_node("justification",       justification_node)
    graph.add_node("human_review",        human_review_node)

    # Entry point
    graph.set_entry_point("query_understanding")

    # Sequential edges
    graph.add_edge("query_understanding", "snomed_search")
    graph.add_edge("snomed_search",       "validator")

    # Conditional edge: Validator → loop back or proceed
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "snomed_search": "snomed_search",
            "justification": "justification"
        }
    )

    # Human-in-the-loop: interrupt_before fires here
    graph.add_edge("justification", "human_review")
    graph.add_edge("human_review",  END)

    # Compile with memory checkpointer (enables interrupt_before)
    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"]   # pauses here for human review
    )


# --- Run the graph (entry point for testing) ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    app = build_graph()

    # Test input — replace with your test case research question
    initial_state = {
        "research_question": (
            "What SNOMED codes identify patients with heart failure with reduced "
            "ejection fraction (HFrEF, LVEF < 40%) eligible for SGLT2 inhibitor "
            "therapy in UK primary care?"
        ),
        "iteration_count": 0,
        "human_review_flag": False,
        "human_feedback": None,
        "final_output": None
    }

    config = {"configurable": {"thread_id": "test-run-001"}}

    print("=== Running NICE Clinical Code Recommendation Pipeline ===\n")
    for step in app.stream(initial_state, config=config):
        node_name = list(step.keys())[0]
        print(f"✅ Completed: {node_name}")
        print(f"   State keys updated: {list(step[node_name].keys())}\n")

    print("=== Pipeline paused at human_review checkpoint ===")
    print("Review the justifications in state, then resume with:")
    print('   app.invoke(None, config=config)  # to approve and continue to END')
