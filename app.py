import asyncio
from main import app as clinical_graph # compiled LangGraph
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
from src.utils.dummy_data import DUMMY_STATE
import uuid
import io
import json

USE_DUMMY_DATA = True

DUMMY_KEYWORDS = [
    "obesity", "diabetes", "hypertension", "t2dm", "type 2",
    "obese", "blood pressure", "metabolic"
]

def query_has_results(query):
    query_lower = query.lower().strip()
    return any(keyword in query_lower for keyword in DUMMY_KEYWORDS)

st.set_page_config(page_title="NICE Clinical Code Generator", layout="wide")

st.markdown("""
<style>
    .tier-1 { background-color:#EAF3DE;color:#27500A;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500; }
    .tier-2 { background-color:#FAEEDA;color:#633806;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500; }
    .tier-3 { background-color:#FCEBEB;color:#791F1F;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500; }
    .badge { background-color:#E6F1FB;color:#0C447C;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500;margin-right:4px; }
    .warning-box { background-color:#FAEEDA;border:1px solid #EF9F27;border-radius:8px;padding:12px 16px;font-size:13px;color:#633806;margin-bottom:16px; }
    .code-card { background-color:#FFFFFF;border:1px solid #E0E0E0;border-radius:8px;padding:16px;margin-bottom:12px; }
    .code-card-selected { background-color:#F5FAFF;border:1px solid #85B7EB;border-radius:8px;padding:16px;margin-bottom:12px; }
    .code-card-accepted { background-color:#FFFFFF;border:1px solid #97C459;border-radius:8px;padding:16px;margin-bottom:12px; }
    .code-card-skipped { background-color:#FAFAFA;border:1px solid #E0E0E0;border-radius:8px;padding:16px;margin-bottom:12px;opacity:0.6; }
    .section-label { font-size:12px;font-weight:500;color:#888780;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px; }
    .metric-card { background-color:#F1EFE8;border-radius:8px;padding:12px 16px;text-align:center; }
    .metric-value { font-size:28px;font-weight:500;color:#2C2C2A; }
    .metric-label { font-size:12px;color:#5F5E5A;margin-top:4px; }
    .thankyou { background-color:#EAF3DE;border:1px solid #97C459;border-radius:6px;padding:8px 14px;font-size:13px;color:#27500A;margin-top:10px;text-align:center;font-weight:500; }
    .decision-accepted { background-color:#EAF3DE;color:#27500A;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500; }
    .decision-rejected { background-color:#FCEBEB;color:#791F1F;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500; }
    .decision-skipped { background-color:#F1EFE8;color:#5F5E5A;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500; }
    .error-empty { border:1px solid #E0E0E0;border-radius:12px;padding:3rem 2rem;text-align:center;background-color:#F9F9F9; }
    .footer-box { border-top:1px solid #E0E0E0;padding-top:1.5rem;margin-top:2rem;text-align:center; }
</style>
""", unsafe_allow_html=True)

if "state" not in st.session_state:
    st.session_state.state = None
if "no_results" not in st.session_state:
    st.session_state.no_results = False
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "reviews" not in st.session_state:
    st.session_state.reviews = {}
if "feedback" not in st.session_state:
    st.session_state.feedback = {}
if "feedback_submitted" not in st.session_state:
    st.session_state.feedback_submitted = {}
if "selected_codes" not in st.session_state:
    st.session_state.selected_codes = {}
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

def get_tier_badge(tier):
    if tier == "tier_1":
        return '<span class="tier-1">Tier 1 - Core</span>'
    elif tier == "tier_2":
        return '<span class="tier-2">Tier 2 - Review</span>'
    else:
        return '<span class="tier-3">Tier 3 - Supplementary</span>'

def render_footer_credits():
    st.markdown("""
    <div class="footer-box">
        <p style="font-size:13px;color:#5F5E5A;margin-bottom:4px">This project was created by Farhio, Angelo, Lemmy, Bihter, Aydin and Mohan</p>
        <p style="font-size:12px;color:#888780;margin-bottom:12px">University of Cambridge - 2025</p>
        <div style="display:flex;align-items:center;justify-content:center;gap:16px">
            <div style="background:#003087;color:#fff;font-size:11px;font-weight:700;padding:3px 8px;border-radius:3px">NHS</div>
            <span style="font-size:12px;color:#888780">University of Cambridge</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_header():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("NICE Clinical Code Generator")
        st.caption("AI-assisted code list generation - for expert clinical review only")
    with col2:
        logo_col1, logo_col2, logo_col3 = st.columns([2, 0.1, 2])
        with logo_col1:
            try:
                st.image("assets/NHS 10mm - RGB Blue on white.jpg", width=120)
            except:
                st.markdown('<div style="background:#003087;color:#fff;font-size:14px;font-weight:700;padding:6px 10px;border-radius:4px;text-align:center">NHS</div>', unsafe_allow_html=True)
        with logo_col2:
            st.markdown('<div style="border-left:1px solid #CC0000;opacity:0.3;height:60px;margin:auto"></div>', unsafe_allow_html=True)
        with logo_col3:
            try:
                st.image("assets/The University logo.png", width=200)
            except:
                st.markdown('<div style="font-size:11px;color:#5F5E5A;text-align:center">University of<br>Cambridge</div>', unsafe_allow_html=True)
    st.divider()

def render_query_input():
    st.markdown('<p class="section-label">Research question</p>', unsafe_allow_html=True)
    col1, col2 = st.columns([5, 1])
    with col1:
        query = st.text_input(
            label="Research question input",
            value=st.session_state.last_query if st.session_state.last_query else "Obesity with type 2 diabetes and hypertension",
            placeholder="Enter a patient cohort description...",
            label_visibility="collapsed",
            key="query_input"
        )
    with col2:
        run = st.button("Generate codes", type="primary", use_container_width=True)
    return query, run

def render_pipeline_status(no_results=False):
    st.markdown('<p class="section-label">Pipeline status</p>', unsafe_allow_html=True)
    cols = st.columns(5)
    labels = [
        "Node 1: Query understanding",
        "Node 2: SNOMED search",
        "Node 3: Validation",
        "Node 4: Justification",
        "Review checkpoint"
    ]
    for i, (col, label) in enumerate(zip(cols, labels)):
        with col:
            if no_results and i == 3:
                st.warning(label + " - no results")
            elif no_results and i == 4:
                st.empty()
            elif i < 4:
                st.success(label)
            else:
                st.info(label)

def render_query_summary(state):
    st.markdown('<p class="section-label">Query summary</p>', unsafe_allow_html=True)
    with st.expander("View query analysis from Node 1", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Primary condition:** {state['primary_condition']}")
            st.markdown(f"**Concept type:** {state['concept_type']}")
            st.markdown(f"**SNOMED hierarchy:** {state['snomed_top_hierarchy']}")
            st.markdown("**Related conditions:**")
            for c in state["related_conditions"]:
                st.markdown(f"- {c}")
            for c in state["relevant_medications"]:
                st.markdown(f"- {c}")
            for c in state["relevant_observations"]:
                st.markdown(f"- {c}")
        with col2:
            st.markdown("**Relevant guidelines:**")
            for g in state["relevant_guidelines"]:
                st.markdown(f"- {g}")
            st.markdown("**Explicit exclusions:**")
            for e in state["excluded_diagnoses"]:
                st.markdown(f"- {e}")
            for e in state["excluded_medications"]:
                st.markdown(f"- {e}")
            for e in state["excluded_observations"]:
                st.markdown(f"- {e}")
        if state.get("ambiguity_notes"):
            st.markdown(
                f'<div class="warning-box">Ambiguity flagged: {state["ambiguity_notes"]}</div>',
                unsafe_allow_html=True
            )
        st.markdown("**Expanded search terms used:**")
        st.markdown(", ".join(state["search_terms"]))


def render_metrics(state):
    st.markdown('<p class="section-label">Summary</p>', unsafe_allow_html=True)
    justifications = state.get("justifications", [])
    t1 = sum(1 for j in justifications if j["tier"] == "tier_1")
    t2 = sum(1 for j in justifications if j["tier"] == "tier_2")
    t3 = sum(1 for j in justifications if j["tier"] == "tier_3")
    reviewed = len([k for k, v in st.session_state.reviews.items() if v in ("accepted", "rejected", "skipped")])
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(state.get("candidate_codes", []))}</div><div class="metric-label">Candidates found</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(state.get("validated_codes", []))}</div><div class="metric-label">After validation</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{t1}</div><div class="metric-label">Tier 1 codes</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{t2 + t3}</div><div class="metric-label">Need review</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{reviewed}/{len(justifications)}</div><div class="metric-label">Reviewed</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

def render_bulk_toolbar(justifications):
    st.markdown('<p class="section-label">Suggested codes - ranked by confidence</p>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
    with col1:
        select_all = st.checkbox("Select all", key="select_all")
        if select_all:
            for j in justifications:
                st.session_state.selected_codes[j["snomed_id"]] = True
        else:
            if st.session_state.get("prev_select_all", False):
                for j in justifications:
                    st.session_state.selected_codes[j["snomed_id"]] = False
        st.session_state["prev_select_all"] = select_all
    selected_count = sum(1 for v in st.session_state.selected_codes.values() if v)
    with col2:
        st.markdown(f'<div style="font-size:13px;color:#888780;padding-top:8px">{selected_count} of {len(justifications)} selected</div>', unsafe_allow_html=True)
    with col3:
        if st.button("Accept selected", use_container_width=True):
            for snomed_id, selected in st.session_state.selected_codes.items():
                if selected:
                    st.session_state.reviews[snomed_id] = "accepted"
            st.rerun()
    with col4:
        if st.button("Reject selected", use_container_width=True):
            for snomed_id, selected in st.session_state.selected_codes.items():
                if selected:
                    st.session_state.reviews[snomed_id] = "rejected"
            st.rerun()
    with col5:
        if st.button("Skip selected", use_container_width=True):
            for snomed_id, selected in st.session_state.selected_codes.items():
                if selected:
                    st.session_state.reviews[snomed_id] = "skipped"
            st.rerun()

def render_code_cards(state):
    justifications = state.get("justifications", [])
    render_bulk_toolbar(justifications)
    for j in justifications:
        snomed_id = j["snomed_id"]
        current = st.session_state.reviews.get(snomed_id, None)
        is_selected = st.session_state.selected_codes.get(snomed_id, False)
        if current == "accepted":
            card_class = "code-card-accepted"
        elif current == "skipped":
            card_class = "code-card-skipped"
        elif is_selected:
            card_class = "code-card-selected"
        else:
            card_class = "code-card"
        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
        col_check, col_main, col_actions = st.columns([0.3, 4, 1])
        with col_check:
            checked = st.checkbox(
                label="select",
                value=is_selected,
                key=f"check_{snomed_id}",
                label_visibility="collapsed"
            )
            st.session_state.selected_codes[snomed_id] = checked
        with col_main:
            tier_badge = get_tier_badge(j["tier"])
            qof_badge = '<span class="badge">QOF validated</span>' if j["qof_match"] else ""
            nhsd_badge = '<span class="badge">NHS Digital refset</span>' if j["is_nhsd_refset"] else ""
            opencl_badge = '<span class="badge">OpenCodelists</span>' if j["opencodelists_match"] else ""
            conf_badge = f'<span class="badge">Confidence: {j["confidence_score"]:.2f}</span>'
            st.markdown(
                f'<b style="font-family:monospace">{j["snomed_id"]}</b> &nbsp; {j["preferred_term"]} &nbsp; {tier_badge} {qof_badge} {nhsd_badge} {opencl_badge} {conf_badge}',
                unsafe_allow_html=True
            )
            st.markdown(f"{j['justification_text']}")
            
            # Show the exact quote and the page reference
            quote = j.get("evidence_quote", "")
            page_ref = j.get("source_chunk", "N/A")
            
            if quote and quote not in ["N/A", "No quote found"]:
                st.markdown(f"> *\"{quote}\"*")
                st.markdown(f'<div style="font-size:12px;color:#0C447C;font-weight:bold;">Location: {page_ref}</div>', unsafe_allow_html=True)

            st.markdown(f'<div style="font-size:12px;color:#0C447C;margin-top:4px">Source: {j["source_document"]}</div>', unsafe_allow_html=True)
        with col_actions:
            if current in ("accepted", "rejected", "skipped"):
                if current == "accepted":
                    st.markdown('<span class="decision-accepted">Accepted</span>', unsafe_allow_html=True)
                elif current == "rejected":
                    st.markdown('<span class="decision-rejected">Rejected</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="decision-skipped">Skipped</span>', unsafe_allow_html=True)
            else:
                if st.button("Accept", key=f"accept_{snomed_id}", use_container_width=True):
                    st.session_state.reviews[snomed_id] = "accepted"
                    st.rerun()
                if st.button("Reject", key=f"reject_{snomed_id}", use_container_width=True):
                    st.session_state.reviews[snomed_id] = "rejected"
                    st.rerun()
                if st.button("Skip", key=f"skip_{snomed_id}", use_container_width=True):
                    st.session_state.reviews[snomed_id] = "skipped"
                    st.rerun()
        if current in ("accepted", "rejected"):
            already_submitted = st.session_state.feedback_submitted.get(snomed_id, False)
            if already_submitted:
                st.markdown('<div class="thankyou">Thank you! Your feedback has been recorded.</div>', unsafe_allow_html=True)
            else:
                decision_label = "accepting" if current == "accepted" else "rejecting"
                with st.container():
                    reason = st.text_area(
                        f"Reason for {decision_label}:",
                        key=f"reason_{snomed_id}",
                        placeholder=f"Explain why you {current} this code...",
                        height=80
                    )
                    rating = st.slider(
                        "Confidence rating (1 = low, 5 = high):",
                        min_value=1,
                        max_value=5,
                        value=3,
                        key=f"rating_{snomed_id}"
                    )
                    if st.button("Submit feedback", key=f"submit_feedback_{snomed_id}"):
                        st.session_state.feedback[snomed_id] = {
                            "timestamp": datetime.now().isoformat(),
                            "session_id": st.session_state.session_id,
                            "research_question": state["research_question"],
                            "primary_condition": state["primary_condition"],
                            "snomed_id": snomed_id,
                            "preferred_term": j["preferred_term"],
                            "tier": j["tier"],
                            "confidence_score": j["confidence_score"],
                            "decision": current,
                            "reason": reason,
                            "rating": rating,
                            "qof_match": j["qof_match"],
                            "is_nhsd_refset": j["is_nhsd_refset"],
                            "found_in_codelists": j["found_in_codelists"],
                            "reviewer_id": "clinician"
                        }
                        st.session_state.feedback_submitted[snomed_id] = True
                        st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

def render_no_results(query):
    render_pipeline_status(no_results=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="warning-box">The pipeline completed but no codes were returned for this query.</div>',
        unsafe_allow_html=True
    )
    st.markdown(f"""
    <div class="error-empty">
        <h3 style="margin-bottom:8px">No codes found</h3>
        <p style="color:#5F5E5A;margin-bottom:1.5rem">
            No clinical codes could be identified for<br>
            <b>"{query}"</b><br><br>
            This may be because the condition is not recognised in SNOMED CT<br>
            or the query needs rephrasing.
        </p>
        <div style="text-align:left;background:#fff;border:1px solid #E0E0E0;border-radius:8px;padding:12px 16px;display:inline-block;margin-bottom:1.5rem">
            <p style="font-size:12px;font-weight:500;color:#888780;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px">Suggestions</p>
            <ul style="margin:0;padding-left:16px;font-size:13px;color:#5F5E5A">
                <li style="margin-bottom:4px">Try using the full clinical name of the condition</li>
                <li style="margin-bottom:4px">Check spelling and try again</li>
                <li style="margin-bottom:4px">Try a broader term e.g. "diabetes" instead of a very specific phrase</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Try again", type="primary"):
        st.session_state.state = None
        st.session_state.no_results = False
        st.session_state.last_query = ""
        st.session_state.reviews = {}
        st.session_state.feedback = {}
        st.session_state.feedback_submitted = {}
        st.session_state.selected_codes = {}
        st.rerun()

def render_footer(state):
    st.divider()
    col1, col2 = st.columns([2, 2])
    with col1:
        if st.button("Export accepted codes", use_container_width=True):
            accepted = [
                j for j in state.get("justifications", [])
                if st.session_state.reviews.get(j["snomed_id"]) == "accepted"
            ]
            if accepted:
                df = pd.DataFrame([{
                    "SNOMED ID": j["snomed_id"],
                    "Preferred term": j["preferred_term"],
                    "Tier": j["tier"],
                    "Confidence": j["confidence_score"],
                    "QOF match": j["qof_match"],
                    "NHS Digital refset": j["is_nhsd_refset"],
                    "Source": j["source_document"]
                } for j in accepted])
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="nice_accepted_codes.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No accepted codes to export yet.")
    with col2:
        if st.button("Submit for audit", type="primary", use_container_width=True):
            total = len(state.get("justifications", []))
            reviewed = len([k for k, v in st.session_state.reviews.items() if v in ("accepted", "rejected", "skipped")])
            if reviewed < total:
                st.warning(f"Please review all codes before submitting. {reviewed}/{total} reviewed.")
            else:
                st.session_state.submitted = True
                st.success("Submitted for audit. All decisions and feedback have been recorded.")

# --- 1. ADD THE HELPER FUNCTION HERE (Above main) ---
def convert_to_excel(justifications_list):
    """Converts the list of justified codes into an Excel file in memory."""
    df = pd.DataFrame(justifications_list)
    
    if not df.empty:
        # Filter and order the columns to make it look professional
        display_columns = [
            "snomed_id", "preferred_term", "category", "tier", 
            "justification_text", "evidence_quote", "source_document", "source_chunk"
        ]
        df = df[[col for col in display_columns if col in df.columns]]

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Justified Codes')
    return buffer.getvalue()
# -----------------------------------------------------

def main():
    render_header()
    query, run = render_query_input()

    if run:
        if not query.strip():
            st.warning("Please enter a research question before generating.")
            return
        st.session_state.reviews = {}
        st.session_state.feedback = {}
        st.session_state.feedback_submitted = {}
        st.session_state.selected_codes = {}
        st.session_state.submitted = False
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.last_query = query
        
        # --- THE REAL LANGGRAPH PIPELINE ---
        with st.spinner("Running clinical AI pipeline... (This may take 30-60 seconds)"):
            try:
                initial_state = {"research_question": query}
                thread_config = {"configurable": {"thread_id": st.session_state.session_id}}
                final_state = asyncio.run(clinical_graph.ainvoke(initial_state, config=thread_config))
                
                if final_state.get("justifications") and len(final_state["justifications"]) > 0:
                    st.session_state.state = final_state
                    st.session_state.no_results = False
                else:
                    st.session_state.state = None
                    st.session_state.no_results = True
                    
            except Exception as e:
                st.error(f"Pipeline encountered an error: {str(e)}")
                st.session_state.state = None
                st.session_state.no_results = True

    if st.session_state.no_results:
        render_no_results(st.session_state.last_query)
        render_footer_credits()
    elif st.session_state.state is not None:
        state = st.session_state.state
        render_pipeline_status(no_results=False)
        st.markdown("<br>", unsafe_allow_html=True)
        render_query_summary(state)
        st.markdown("<br>", unsafe_allow_html=True)
        render_metrics(state)
        st.markdown(
            '<div class="warning-box">These suggestions are AI-generated and require expert clinical review before use in any NICE guideline or analysis.</div>',
            unsafe_allow_html=True
        )
        render_code_cards(state)
        
        # --- 2. ADD THE DOWNLOAD BUTTONS HERE ---
        st.markdown("### 📥 Export Results")
        col1, col2 = st.columns(2)
        
        with col1:
            excel_data = convert_to_excel(state["justifications"])
            st.download_button(
                label="📊 Download Output as Excel",
                data=excel_data,
                file_name="NICE_clinical_codes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        with col2:
            json_string = json.dumps(state["justifications"], indent=4)
            st.download_button(
                label="📥 Download Output as JSON",
                data=json_string,
                file_name="NICE_clinical_codes.json",
                mime="application/json"
            )
        # ----------------------------------------
        
        render_footer(state)
        render_footer_credits()
    else:
        render_footer_credits()

if __name__ == "__main__":
    main()
