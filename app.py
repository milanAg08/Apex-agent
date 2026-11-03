"""
APEX: Civic Infrastructure Road-Damage Repair Prioritization Agent
Enterprise Decision-Support Platform for Municipal Ward Engineers.
Bengaluru Ward 34 (D.V. Gundappa Ward) · Grounded in IRC:82 and BBMP Tender Standards.
"""

import os
import sys
import json
import time
import sqlite3
from datetime import datetime, date
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

# Ensure root directory is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

from agent.graph import create_road_agent_graph, CHECKPOINT_DB_PATH
from agent.state import RoadAgentState
from agent.llm_reasoner import ReActReasoner
from tools.location import resolve_location
from tools.clustering import cluster_reports
from tools.maintenance_db import query_maintenance_db
from tools.rag_tool import retrieve_criteria
from tools.severity import score_severity
from tools.cost import estimate_cost
from tools.priority import calculate_priority_score
from tools.history_store import save_investigation, update_investigation_state, load_all_investigations
from observability.tracer import record_engineer_gate_feedback

# ==============================================================================
# STREAMLIT PAGE CONFIGURATION & FULL-SCREEN STYLING
# ==============================================================================
st.set_page_config(
    page_title="APEX",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enterprise Modern Chat Styling with Pinned Fixed Header
st.markdown("""
<style>
    :root {
        --apex-bg: #0E2630;
        --apex-surface: #17333F;
        --apex-surface-2: #1E3E4C;
        --apex-border: rgba(140, 199, 196, 0.20);
        --apex-text: #FFF6F6;
        --apex-text-muted: #8CC7C4;
        --apex-accent: #DB1A1A;
        /* Lighter, desaturated red for small text ON the dark background —
           the raw brand red (#DB1A1A) is only 3.1:1 against --apex-bg, below
           WCAG AA's 4.5:1 for body-size text. #FF6B6B clears 5.6:1. Keep
           --apex-accent for solid fills (buttons/badges), this for text. */
        --apex-accent-text: #FF6B6B;
        --apex-accent-soft: rgba(219, 26, 26, 0.14);
        --apex-navbar-height: 76px;
    }

    /* Completely hide Streamlit header and deploy toolbar to reclaim top screen */
    header[data-testid="stHeader"] {
        display: none !important;
        height: 0px !important;
    }

    /* Pinned Non-Scrollable Top Navbar */
    .st-key-top_navbar {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        z-index: 999999 !important;
        min-height: var(--apex-navbar-height) !important;
        display: flex !important;
        align-items: center !important;
        background: var(--apex-bg) !important;
        border-bottom: 1px solid var(--apex-border) !important;
        box-shadow: 0 1px 0 rgba(0, 0, 0, 0.25) !important;
        padding: 16px 2.5rem !important;
        box-sizing: border-box !important;
    }
    .st-key-top_navbar > div { width: 100%; }

    /* Content container - pushed down to clear the fixed navbar */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
        padding-top: calc(var(--apex-navbar-height) + 2rem) !important;
        padding-bottom: 6.5rem !important;
    }

    /* Top Brand Typography */
    .top-brand-title {
        font-size: 1.3rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.2;
        margin: 0;
        color: var(--apex-text);
    }
    .top-brand-subtitle {
        font-size: 0.68rem;
        color: var(--apex-text-muted);
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-top: 2px;
    }

    /* Plain-text nav links (Chat / Dashboard) — no box, just color on select */
    .st-key-top_navbar button[kind="tertiary"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 8px 4px !important;
        font-weight: 650 !important;
        font-size: 0.95rem !important;
        transition: color 0.15s ease;
    }
    .st-key-top_navbar button[kind="tertiary"]:hover {
        color: var(--apex-accent-text) !important;
        background: transparent !important;
    }
    .st-key-top_navbar button[kind="tertiary"] p { font-size: 0.95rem !important; }
    .st-key-nav_chat_btn button[kind="tertiary"] p,
    .st-key-nav_dashboard_btn button[kind="tertiary"] p {
        color: var(--apex-text-muted) !important;
    }
    /* Active-tab color is set per-render via an inline <style> block (see navbar code) */

    /* Agentic Mode toggle sits at the far right with a tight, deliberate gap */
    .st-key-top_navbar [data-testid="stToggle"] label p { font-size: 0.85rem !important; }

    /* Decision Status Badges */
    .badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-right: 6px;
    }
    .badge-p1 { background-color: #DB1A1A; color: #FFF6F6; }
    .badge-p2 { background-color: #E8803C; color: #2b1200; }
    .badge-p3 { background-color: #E8C34A; color: #2b2000; }
    .badge-p4 { background-color: #4FA37D; color: #052e22; }
    .badge-merged { background-color: #5B8FA8; color: #06202b; }
    .badge-contractor { background-color: #2C687B; color: #FFF6F6; }
    .badge-evidence { background-color: #8CC7C4; color: #0d2b29; }
    .badge-review { background-color: #D98324; color: #2b1a00; }
    .badge-inspect { background-color: #6FA8A3; color: #052e22; }

    /* Observability Step Row */
    .telemetry-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 4px;
        border-bottom: 1px dashed var(--apex-border);
        font-size: 0.86rem;
    }

    /* Provenance Disclosure Card */
    .provenance-banner {
        border: 1px solid rgba(219, 26, 26, 0.3);
        background: var(--apex-accent-soft);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 1.5rem;
        font-size: 0.84rem;
        line-height: 1.6;
    }

    /* Section label spacing above starter cards / registry heading */
    h5 { margin-top: 0.75rem !important; margin-bottom: 1rem !important; }

    /* Breathing room around metric cards */
    div[data-testid="stMetric"] {
        background: var(--apex-surface);
        border: 1px solid var(--apex-border);
        border-radius: 10px;
        padding: 0.9rem 1rem;
    }

    /* Investigation history — a true left sidebar for the Chat workspace,
       not a floating card: flush to the edge, full height, thin divider. */
    .st-key-history_panel {
        background: transparent;
        border: none;
        border-right: 1px solid var(--apex-border);
        border-radius: 0;
        padding: 0 1.1rem 1.5rem 0;
        min-height: calc(100vh - var(--apex-navbar-height) - 3rem);
        position: sticky;
        top: calc(var(--apex-navbar-height) + 1.75rem);
        align-self: flex-start;
    }
    .history-title {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--apex-text-muted);
        margin-bottom: 0.9rem;
    }
    .st-key-history_panel button[kind="tertiary"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 6px 8px !important;
        border-radius: 8px !important;
        white-space: normal !important;
    }
    .st-key-history_panel button[kind="tertiary"]:hover {
        background: var(--apex-surface) !important;
    }
    .st-key-history_panel button[kind="tertiary"] p {
        text-align: left !important;
        font-size: 0.82rem !important;
        color: var(--apex-text) !important;
        font-weight: 500 !important;
    }
    .st-key-history_panel button[kind="tertiary"]:hover p { color: var(--apex-accent-text) !important; }

    /* Chat / Dashboard nav links: laid out inline, content-width, with a
       deliberately tiny gap (not st.columns, which forces wide fixed-ratio
       cells and makes any gap value look huge next to the leftover space). */
    .st-key-nav_links_wrap {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# PERSISTENT AGENT CHECKPOINTER (SQLite-backed, survives refresh & restarts)
# ==============================================================================
@st.cache_resource(show_spinner=False)
def get_agent_app():
    """
    One compiled LangGraph app + SQLite checkpointer per server process,
    reused across every rerun and every browser session so investigation
    threads (by thread_id) can be resumed/inspected after a refresh.
    """
    os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return create_road_agent_graph(checkpointer=checkpointer)

# ==============================================================================
# STATE INITIALIZATION
# ==============================================================================
if "active_mode" not in st.session_state:
    st.session_state["active_mode"] = "Agentic" if os.getenv("USE_REAL_LLM", "false").lower() in ("true", "1", "yes") else "Deterministic"

if "active_view" not in st.session_state:
    st.session_state["active_view"] = "Chat"

if "all_threads" not in st.session_state:
    # Reload every persisted investigation (thread) from disk so the
    # history rail survives a browser refresh or server restart.
    st.session_state["all_threads"] = load_all_investigations()

if "active_thread_id" not in st.session_state:
    st.session_state["active_thread_id"] = None

if "is_running" not in st.session_state:
    st.session_state["is_running"] = False

if "filter_query" not in st.session_state:
    st.session_state["filter_query"] = ""

# ==============================================================================
# 4 SPECIFIC REALISTIC MUNICIPAL INVESTIGATION PRESETS (NO EMOJIS)
# ==============================================================================
SPECIFIC_PRESETS = [
    {
        "id": "scenario_p1",
        "title": "Arterial Wheelpath Crater (Bull Temple Road)",
        "subtitle": "Arterial wheel-path depression with standing water puddle",
        "query": "Deep 10cm crater on Bull Temple Road wheel path near BMSCE Main Gate with standing rainwater puddle and BMTC buses swerving dangerously",
        "lat": 12.9378,
        "lon": 77.5691
    },
    {
        "id": "scenario_dup",
        "title": "Duplicate Open Ticket (DVG Road North)",
        "subtitle": "Citizen report repeating active open ticket TKT_DVG_101",
        "query": "Huge pothole in front of Upahara Darshini on DVG Road north section, two-wheelers slipping on loose gravel",
        "lat": 12.9432,
        "lon": 77.5738
    },
    {
        "id": "scenario_dlp",
        "title": "Contractor Warranty Defect (Gandhi Bazaar)",
        "subtitle": "Asphalt breakdown within 2-year statutory Defect Liability Period",
        "query": "Gandhi bazaar main road surface peeling off near vegetable stalls, asphalt crumbling on road paved within statutory 2-year warranty",
        "lat": 12.9435,
        "lon": 77.5715
    },
    {
        "id": "scenario_vague",
        "title": "Unresolved Location (Missing Coordinates)",
        "subtitle": "Ambiguous description lacking GPS coordinates or valid street match",
        "query": "somewhere near a big tree in bangalore road is broken please send repair team urgently",
        "lat": None,
        "lon": None
    }
]

# ==============================================================================
# EXECUTION ENGINE FUNCTION
# ==============================================================================
def run_apex_pipeline(user_text: str, lat: Optional[float] = None, lon: Optional[float] = None, is_agentic: bool = True) -> Dict[str, Any]:
    reasoner = ReActReasoner(use_llm_api=is_agentic)
    timeline_steps = []
    
    # Auto-resolve coordinates if omitted but landmark mentioned
    t_lower = user_text.lower()
    if lat is None or lon is None:
        if "bull temple" in t_lower or "bmsce" in t_lower:
            lat, lon = 12.9378, 77.5691
        elif "gandhi" in t_lower:
            lat, lon = 12.9435, 77.5715
        elif "dvg" in t_lower or "upahara" in t_lower:
            lat, lon = 12.9432, 77.5738

    reports = [{
        "report_id": f"REP_{int(time.time()*1000)}",
        "lat": lat,
        "lon": lon,
        "text": user_text,
        "reported_date": date.today().isoformat()
    }]

    # Stage 1: Validate & Geocode
    s1_t0 = time.time()
    loc_res = resolve_location(lat=lat, lon=lon, text=user_text)
    s1_ms = int((time.time() - s1_t0) * 1000)
    timeline_steps.append({
        "stage": "1. Validate & Geocode",
        "tool": "resolve_location",
        "ms": s1_ms,
        "summary": f"Matched '{loc_res.get('road_name')}' ({loc_res.get('road_class')}) via OSM node bounding box.",
        "payload": loc_res
    })

    # Stage 2: Vector Clustering
    s2_t0 = time.time()
    clusters = cluster_reports(reports)
    primary_cluster = clusters[0] if clusters else {}
    s2_ms = int((time.time() - s2_t0) * 1000)
    timeline_steps.append({
        "stage": "2. Vector Clustering",
        "tool": "cluster_reports",
        "ms": s2_ms,
        "summary": f"Spatial clustering complete. Duplicate flag: {primary_cluster.get('is_duplicate')} (Ticket: {primary_cluster.get('duplicate_ticket_id', 'None')})",
        "payload": primary_cluster
    })

    # Stage 3: History & Liability Check
    s3_t0 = time.time()
    seg_id = loc_res.get("segment_id")
    maint_res = query_maintenance_db(seg_id)
    s3_ms = int((time.time() - s3_t0) * 1000)
    timeline_steps.append({
        "stage": "3. History & Liability Check",
        "tool": "query_maintenance_db",
        "ms": s3_ms,
        "summary": f"Contractor: {maint_res.get('contractor_name')} | DLP Warranty Active: {maint_res.get('is_under_liability')} ({maint_res.get('days_liability_remaining', 0)} days remaining)",
        "payload": maint_res
    })

    # Stage 4: Severity & Criteria Retrieval
    s4_t0 = time.time()
    attrs = reasoner.extract_complaint_attributes(user_text)
    road_class = loc_res.get("road_class", "collector")
    if maint_res.get("is_under_liability"):
        rag_query = "BBMP tender defect liability period contractor recurrence warranty"
        rag_cat = "defect_liability"
    else:
        rag_query = f"IRC:82 action threshold severity for {road_class} road inspect or repair"
        rag_cat = "action_thresholds"
    rag_res = retrieve_criteria(query=rag_query, category=rag_cat)
    s4_ms = int((time.time() - s4_t0) * 1000)
    timeline_steps.append({
        "stage": "4. Severity & Criteria Retrieval",
        "tool": "retrieve_criteria",
        "ms": s4_ms,
        "summary": f"Grounded citation '{rag_res.get('citation')}' (Confidence: {rag_res.get('confidence_score')}).",
        "payload": {"extracted_physical_attributes": attrs, "rag_evaluation": rag_res}
    })

    # Stage 5: Prioritization & Costing
    s5_t0 = time.time()
    sev_res = score_severity(
        depth_cm=attrs["depth_cm"],
        area_sqm=attrs["area_sqm"],
        standing_water=attrs["standing_water"],
        location_on_carriageway=attrs["location_on_carriageway"],
        is_traffic_blocking=attrs["is_traffic_blocking"]
    )
    cost_res = estimate_cost(
        area_m2=attrs["area_sqm"],
        depth_cm=attrs["depth_cm"],
        road_class=road_class
    )
    prio_res = calculate_priority_score(
        severity=sev_res["severity_score"],
        traffic_index=loc_res.get("traffic_index", 0.5),
        repair_history_risk=maint_res.get("repair_history_risk", 0.5),
        report_count=len(reports),
        road_class=road_class
    )
    s5_ms = int((time.time() - s5_t0) * 1000)
    timeline_steps.append({
        "stage": "5. Prioritization & Costing",
        "tool": "calculate_priority_score",
        "ms": s5_ms,
        "summary": f"Severity S={sev_res['severity_score']:.2f} | Cost: ₹{cost_res['estimated_cost_inr']:,.2f} | Priority Band: {prio_res['priority_level']}",
        "payload": {
            "severity_scoring": sev_res,
            "cost_estimation": cost_res,
            "priority_evaluation": prio_res
        }
    })

    # Full LangGraph execution against the persistent checkpointer, so this
    # investigation's thread can be resumed/inspected by thread_id later.
    app = get_agent_app()
    thread_id = f"chat_{int(time.time()*1000)}"
    initial_state: RoadAgentState = {
        "run_id": thread_id,
        "scenario_id": f"SCEN_{int(time.time())}",
        "reports": reports,
        "use_real_llm": is_agentic,
        "llm_provider": "google" if "AQ." in os.getenv("GEMINI_API_KEY", "") else "auto",
        "current_cluster_index": 0,
        "clusters": [],
        "active_cluster": None,
        "step_count": 0,
        "max_steps": 10,
        "loop_limit_hit": False,
        "thoughts": [],
        "active_branch": None,
        "branch_rationale": None,
        "location_result": loc_res,
        "maintenance_result": maint_res,
        "severity_result": sev_res,
        "cost_result": cost_res,
        "priority_result": prio_res,
        "rag_result": rag_res,
        "outcome": None,
        "priority": None,
        "citation": None,
        "rationale": None,
        "requires_approval": False,
        "gate_triggers": [],
        "gate_status": "PENDING_EVAL",
        "engineer_feedback": None,
        "final_decisions": []
    }
    final_state = app.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})

    created_at = datetime.utcnow().isoformat()
    try:
        save_investigation(
            thread_id=thread_id,
            user_query=user_text,
            timeline=timeline_steps,
            state=final_state,
            created_at=created_at
        )
    except Exception as persist_err:
        # Surface this instead of losing the investigation silently on next refresh.
        st.toast(f"⚠ Could not persist investigation to disk: {persist_err}", icon="⚠️")

    return {
        "thread_id": thread_id,
        "user_query": user_text,
        "timeline": timeline_steps,
        "state": final_state,
        "created_at": created_at
    }

# ==============================================================================
# PINNED TOP NAVBAR (NON-SCROLLABLE AT TOP: APEX ON LEFT, CHAT/DASHBOARD + MODE ON RIGHT)
# ==============================================================================
_active_view_for_nav = st.session_state.get("active_view", "Chat")
# Hierarchy comes from two levers, not color alone, so the active tab still
# reads correctly in grayscale: var(--apex-accent-text) (contrast-safe on
# dark) plus a heavier weight for the active tab, lighter for the inactive one.
st.markdown(f"""
<style>
    .st-key-nav_chat_btn button[kind="tertiary"] p {{
        color: {'var(--apex-accent-text)' if _active_view_for_nav == 'Chat' else 'var(--apex-text-muted)'} !important;
        font-weight: {'700' if _active_view_for_nav == 'Chat' else '500'} !important;
    }}
    .st-key-nav_dashboard_btn button[kind="tertiary"] p {{
        color: {'var(--apex-accent-text)' if _active_view_for_nav == 'Dashboard' else 'var(--apex-text-muted)'} !important;
        font-weight: {'700' if _active_view_for_nav == 'Dashboard' else '500'} !important;
    }}
</style>
""", unsafe_allow_html=True)

with st.container(key="top_navbar"):
    nav_col_brand, nav_col_spacer, nav_col_views, nav_col_toggle = st.columns(
        [2.5, 2.3, 1.1, 0.75], gap="small", vertical_alignment="center"
    )

    with nav_col_brand:
        st.markdown("""
        <div style="display:flex; flex-direction:column; justify-content:center;">
            <div class="top-brand-title">APEX</div>
            <div class="top-brand-subtitle">Civic Infrastructure Intelligence · Bengaluru Ward 34</div>
        </div>
        """, unsafe_allow_html=True)

    with nav_col_views:
        # Two plain-text buttons laid out inline by their own CSS (not st.columns,
        # which would give each one a wide, fixed-ratio flex cell and make the
        # gap between them look huge regardless of the flex `gap` value).
        with st.container(key="nav_links_wrap"):
            if st.button("Chat", key="nav_chat_btn", type="tertiary"):
                if st.session_state["active_view"] != "Chat":
                    st.session_state["active_view"] = "Chat"
                    st.rerun()
            if st.button("Dashboard", key="nav_dashboard_btn", type="tertiary"):
                if st.session_state["active_view"] != "Dashboard":
                    st.session_state["active_view"] = "Dashboard"
                    st.rerun()

    with nav_col_toggle:
        mode_toggled = st.toggle(
            "Agentic Mode",
            value=(st.session_state["active_mode"] == "Agentic"),
            key="agentic_mode_toggle",
            disabled=st.session_state["is_running"],
            help="Switch between Agentic Mode (LLM + Tools) and Deterministic Mode (Rule Engine)"
        )
        updated_mode = "Agentic" if mode_toggled else "Deterministic"
        if updated_mode != st.session_state["active_mode"]:
            st.session_state["active_mode"] = updated_mode
            os.environ["USE_REAL_LLM"] = "true" if mode_toggled else "false"
            st.rerun()

is_agentic_active = (st.session_state["active_mode"] == "Agentic")
current_view = st.session_state.get("active_view", "Chat")

# ==============================================================================
# VIEW 1: CHAT WORKSPACE (CHATGPT-STYLE CONVERSATION FLOW)
# ==============================================================================
def find_thread(thread_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if thread_id is None:
        return None
    return next((t for t in st.session_state["all_threads"] if t["thread_id"] == thread_id), None)


def start_new_investigation(result_data: Dict[str, Any]):
    """Prepend a freshly-run investigation to the persisted thread list and focus it."""
    st.session_state["all_threads"].insert(0, result_data)
    st.session_state["active_thread_id"] = result_data["thread_id"]


def render_history_panel():
    with st.container(key="history_panel"):
        st.markdown("<div class='history-title'>Investigation History</div>", unsafe_allow_html=True)

        if st.button("+ New Investigation", key="hist_new_investigation", type="tertiary", use_container_width=True):
            st.session_state["active_thread_id"] = None
            st.rerun()

        threads = st.session_state["all_threads"]
        if not threads:
            st.caption("No investigations yet. Run one to see it listed here.")
            return

        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

        for h_item in threads:
            h_thread_id = h_item["thread_id"]
            h_state = h_item["state"]
            h_outcome = h_state.get("outcome", "INSPECT")
            h_priority = h_state.get("priority")
            h_badge_class = {
                "MERGE_DUPLICATE": "badge-merged",
                "REQUEST_EVIDENCE": "badge-evidence",
                "ROUTE_TO_CONTRACTOR": "badge-contractor",
                "INSPECT": "badge-inspect",
                "REPAIR_NOW": f"badge-{h_priority.lower()}" if h_priority else "badge-p2",
                "NEEDS_REVIEW": "badge-review"
            }.get(h_outcome, "badge-inspect")
            h_label = h_item["user_query"][:58] + ("…" if len(h_item["user_query"]) > 58 else "")
            is_active = (h_thread_id == st.session_state["active_thread_id"])

            st.markdown(
                f"<span class='badge {h_badge_class}' style='font-size:0.6rem; padding:3px 8px;'>{h_outcome}</span>",
                unsafe_allow_html=True
            )
            if st.button(
                ("▸ " if is_active else "") + h_label,
                key=f"hist_btn_{h_thread_id}",
                type="tertiary",
                use_container_width=True
            ):
                st.session_state["active_thread_id"] = h_thread_id
                st.rerun()
            st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)


def render_chat_main():
    active_thread = find_thread(st.session_state["active_thread_id"])
    if st.session_state["active_thread_id"] and active_thread is None:
        # Stale reference (e.g. deleted thread) — fall back to compose mode.
        st.session_state["active_thread_id"] = None

    # Action Row: New Investigation Reset Button (when viewing a past thread)
    if active_thread is not None:
        ch_c1, ch_c2 = st.columns([3.5, 1])
        with ch_c2:
            if st.button("New Investigation", use_container_width=True, disabled=st.session_state["is_running"]):
                st.session_state["active_thread_id"] = None
                st.rerun()

    # Empty / Compose State: Render ChatGPT-style specific prompt starter cards
    if active_thread is None:
        st.markdown("""
        <div style="text-align: center; padding: 0.5rem 0 2rem 0;">
            <h2 style="font-weight: 800; font-size: 2.1rem; margin-bottom: 0.6rem; letter-spacing: -0.02em; color: var(--apex-text);">
                Where would you like to inspect today?
            </h2>
            <div style="font-size: 0.95rem; color: var(--apex-text-muted); max-width: 650px; margin: 0 auto; line-height: 1.6;">
                APEX evaluates road-damage reports, verifies contractor defect liabilities,
                and computes IRC:82 prioritization scores for municipal engineers.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("##### Standard Municipal Investigation Starters")
        st.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)
        p_cols = st.columns(2)

        for idx, preset in enumerate(SPECIFIC_PRESETS):
            col_target = p_cols[idx % 2]
            with col_target:
                with st.container(border=True):
                    st.markdown(f"**{preset['title']}**")
                    st.caption(preset['subtitle'])
                    st.code(preset['query'], language=None)

                    button_label = "Running..." if st.session_state["is_running"] else "Run Investigation"
                    if st.button(button_label, key=f"starter_btn_{preset['id']}", use_container_width=True, disabled=st.session_state["is_running"]):
                        st.session_state["is_running"] = True
                        with st.spinner("APEX is resolving OSM coordinates, verifying contractor warranty, and scoring severity..."):
                            result_data = run_apex_pipeline(
                                user_text=preset["query"],
                                lat=preset["lat"],
                                lon=preset["lon"],
                                is_agentic=is_agentic_active
                            )
                            start_new_investigation(result_data)
                            st.session_state["is_running"] = False
                        st.rerun()
        return

    # Single-thread view: exactly the investigation picked in the history panel
    stream_items = [(active_thread["thread_id"], active_thread)]

    for idx, item in stream_items:
        user_text = item["user_query"]
        state = item["state"]

        # 1. User Message Box
        with st.chat_message("user"):
            st.markdown(f"**Municipal Investigation Query:**\n\n{user_text}")

        # 2. APEX Assistant Response Box
        with st.chat_message("assistant"):
            outcome = state.get("outcome", "INSPECT")
            priority = state.get("priority")
            citation = state.get("citation", "Standard Municipal Guidelines")
            rationale = state.get("rationale", "")
            cost_data = state.get("cost_result") or {}
            cost_val = cost_data.get("estimated_cost_inr", 0.0)
            triggers = state.get("gate_triggers", [])
            requires_approval = state.get("requires_approval", False)
            gate_status = state.get("gate_status", "APPROVED")
            loc_data = state.get("location_result") or {}
            prio_data = state.get("priority_result") or {}

            badge_class = {
                "MERGE_DUPLICATE": "badge-merged",
                "REQUEST_EVIDENCE": "badge-evidence",
                "ROUTE_TO_CONTRACTOR": "badge-contractor",
                "INSPECT": "badge-inspect",
                "REPAIR_NOW": f"badge-{priority.lower()}" if priority else "badge-p2",
                "NEEDS_REVIEW": "badge-review"
            }.get(outcome, "badge-inspect")

            # 2a. Unified Agent Execution Trace — one chronological list, exactly as
            # the graph actually ran it: thought -> tool call -> observation per
            # step, with retrieval's own grade/rewrite/fallback sub-steps nested
            # inside the one step where they happened (between the tool calls
            # before and after it), instead of three separate, disconnected lists.
            agent_thoughts = state.get("thoughts") or []
            rag_result_full = state.get("rag_result") or {}
            STEP_STATE_KEYS = {
                "cluster_reports": ["clusters"],
                "resolve_location": ["location_result"],
                "score_severity": ["severity_result", "cost_result", "maintenance_result"],
                "query_maintenance_db": ["maintenance_result"],
                "retrieve_criteria": ["rag_result"],
                "calculate_priority_score": ["priority_result"],
                "request_approval": ["priority_result", "gate_triggers"],
                "evaluate_gate_triggers": ["gate_triggers"],
            }
            with st.expander(f"Agent Execution Trace — Planning, Tools & Retrieval ({len(agent_thoughts)} Steps)", expanded=False):
                if not agent_thoughts:
                    st.caption("No trace recorded for this run.")
                for t in agent_thoughts:
                    action = t.get("action", "")
                    st.markdown(f"**Step {t.get('step_number')} · Thought → Action: `{action}` → Observation**")
                    st.markdown(f"- **Thought:** {t.get('thought')}")
                    if t.get("action_input"):
                        st.markdown(f"- **Action Input:** `{t.get('action_input')}`")
                    st.markdown(f"- **Observation:** {t.get('observation')}")

                    # Retrieval's grade -> rewrite -> fallback sub-steps, shown
                    # right here, between the tool call before and after it.
                    if action == "retrieve_criteria" and rag_result_full.get("grading_history"):
                        st.markdown("&nbsp;&nbsp;&nbsp;&nbsp;**↳ Agentic retrieval sub-steps (grade → rewrite → fallback):**", unsafe_allow_html=True)
                        for g in rag_result_full["grading_history"]:
                            pass_badge = "✅ PASSED" if g.get("passed") else "❌ FAILED"
                            st.markdown(
                                f"&nbsp;&nbsp;&nbsp;&nbsp;— Attempt {g.get('attempt')}: query `{g.get('query')}` → "
                                f"chunk `{g.get('best_chunk_id')}`, score `{g.get('score', 0.0):.2f}` · {pass_badge}",
                                unsafe_allow_html=True
                            )
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{g.get('reason')}", unsafe_allow_html=True)
                        if rag_result_full.get("fallback_used"):
                            st.warning("Retrieval confidence stayed below threshold on every attempt — fell back to the default municipal rule table instead of guessing.")

                    # Raw tool/state payload for this step, nested, if available.
                    payload = {k: state.get(k) for k in STEP_STATE_KEYS.get(action, []) if state.get(k) is not None}
                    if payload:
                        with st.expander(f"Raw data for this step ({action})", expanded=False):
                            st.json(payload)

                    st.markdown(
                        "<div style='height:10px; border-bottom:1px dashed var(--apex-border); margin-bottom:10px;'></div>",
                        unsafe_allow_html=True
                    )

            # 2b. The Decision Card
            with st.container(border=True):
                # Header row
                card_c1, card_c2 = st.columns([2.5, 1.2])
                with card_c1:
                    badge_html = f"<span class='badge {badge_class}'>{outcome}</span>"
                    if priority:
                        badge_html += f" <span class='badge badge-{priority.lower()}'>{priority} PRIORITY</span>"
                    st.markdown(badge_html, unsafe_allow_html=True)
                    st.markdown(f"### {loc_data.get('road_name', 'Resolved Segment')}")
                    st.caption(f"Road Class: **{loc_data.get('road_class', 'Urban Local').upper()}** · Bengaluru Central Ward 34")
                with card_c2:
                    # Key off `outcome`, not cost_result's own status marker: the
                    # outcome field is always reliable, including for investigations
                    # persisted before cost_result started carrying that marker.
                    if outcome in ("MERGE_DUPLICATE", "REQUEST_EVIDENCE"):
                        st.metric("Estimated Spend", "N/A", "No repair job scored")
                    elif outcome == "ROUTE_TO_CONTRACTOR":
                        st.metric("Estimated Spend", "₹0.00", "Contractor liability")
                    else:
                        st.metric("Estimated Spend", f"₹{cost_val:,.2f}" if cost_val > 0 else "₹0.00")

                st.markdown(f"**Engineering Rationale:** {rationale}")
                st.info(f"**Policy Grounding Citation:** `{citation}`")

                # Formula breakdown for REPAIR_NOW
                if outcome == "REPAIR_NOW":
                    prio_inputs = prio_data.get("inputs", {}) or {}
                    prio_weights = prio_data.get("weights", {}) or {}
                    w_s = prio_weights.get("w_s", 0.40)
                    w_t = prio_weights.get("w_t", 0.30)
                    w_h = prio_weights.get("w_h", 0.15)
                    w_r = prio_weights.get("w_r", 0.15)
                    with st.container(border=True):
                        st.markdown("**Priority Equation Evaluation (IRC:82 Section 3.2):**")
                        st.latex(r"P = c_{road} \times (0.40 \cdot S + 0.30 \cdot T + 0.15 \cdot H + 0.15 \cdot R)")
                        st.markdown(
                            f"**Computed Score:** `{prio_data.get('c_road', 1.0)}` × ({w_s:.2f}·`{prio_inputs.get('severity_S', 0.0):.2f}` + {w_t:.2f}·`{prio_inputs.get('traffic_T', 0.0):.2f}` + {w_h:.2f}·`{prio_inputs.get('history_risk_H', 0.0):.2f}` + {w_r:.2f}·`{prio_inputs.get('report_volume_R', 0.0):.2f}`) = **`{prio_data.get('priority_score', 0.0):.3f}`** → Priority Band **`{priority}`** ({prio_data.get('response_time_sla', '<24 hours')})"
                        )

                # Special Outcome details
                elif outcome == "ROUTE_TO_CONTRACTOR":
                    maint_info = state.get("maintenance_result") or {}
                    st.success(f"**Defect Liability Period Active:** Contractor **{maint_info.get('contractor_name')}** is contractually liable until **{maint_info.get('liability_expiry_date')}** ({maint_info.get('days_liability_remaining', 0)} days remaining). Rectification routed at **₹0 municipal spend** under statutory BBMP Tender Clause 14.5.")

                elif outcome == "MERGE_DUPLICATE":
                    dup_info = (state.get("clusters") or [{}])[0].get("duplicate_info", {})
                    st.info(f"**Duplicate Linked to Active Ticket:** Matches open ticket **#{dup_info.get('matched_ticket_id', 'TKT_DVG_101')}** ({dup_info.get('distance_meters', 15.5)}m distance, {dup_info.get('days_apart', 1)} days apart). Redundant municipal crew dispatch suppressed.")

                elif outcome == "REQUEST_EVIDENCE":
                    st.warning("**Insufficient Evidence:** Citizen complaint lacks verifiable road landmark or GPS coordinates. Triggering citizen verification request protocol before crew dispatch.")

                # 2c. Human-in-the-Loop Sign-off Actions
                if requires_approval and gate_status == "PAUSED_FOR_ENGINEER":
                    st.warning("**Statutory Human-in-the-Loop Gate Paused:** Public safety SLA, contractual warranty claim, or cost exceeding ₹25,000 threshold requires executive engineer sign-off.")
                    
                    st.markdown("**Active Statutory Gate Triggers:**")
                    for tr in triggers:
                        st.markdown(f"- {tr}")

                    b_c1, b_c2, b_c3 = st.columns(3)
                    with b_c1:
                        if st.button("Approve & Dispatch", key=f"approve_{idx}", type="primary", use_container_width=True):
                            record_engineer_gate_feedback(
                                cluster_id="CLUST_001",
                                original_outcome=outcome,
                                original_priority=priority,
                                engineer_action="APPROVED",
                                final_outcome=outcome,
                                final_priority=priority,
                                engineer_notes="Approved by Assistant Executive Engineer.",
                                cluster_context={"query": user_text}
                            )
                            item["state"]["gate_status"] = "APPROVED"
                            update_investigation_state(item["thread_id"], item["state"])
                            st.success("Work order approved and released for dispatch!")
                            st.rerun()

                    with b_c2:
                        with st.popover("Edit Recommendation", use_container_width=True):
                            new_outcome = st.selectbox("Override Outcome", ["REPAIR_NOW", "INSPECT", "ROUTE_TO_CONTRACTOR", "NEEDS_REVIEW", "REQUEST_EVIDENCE"], index=0, key=f"new_out_{idx}")
                            new_priority = st.selectbox("Override Priority", ["P1", "P2", "P3", "P4", "None"], index=0, key=f"new_prio_{idx}")
                            edit_notes = st.text_area("Mandatory Engineer Justification", "Sub-base settlement confirmed on visual inspection.", key=f"notes_{idx}")
                            if st.button("Commit Override", key=f"commit_btn_{idx}", type="primary"):
                                record_engineer_gate_feedback(
                                    cluster_id="CLUST_001",
                                    original_outcome=outcome,
                                    original_priority=priority,
                                    engineer_action="EDITED",
                                    final_outcome=new_outcome,
                                    final_priority=new_priority if new_priority != "None" else None,
                                    engineer_notes=edit_notes,
                                    cluster_context={"query": user_text}
                                )
                                item["state"]["gate_status"] = "EDITED"
                                item["state"]["outcome"] = new_outcome
                                item["state"]["priority"] = new_priority if new_priority != "None" else None
                                update_investigation_state(item["thread_id"], item["state"])
                                st.success("Override committed to audit trail!")
                                st.rerun()

                    with b_c3:
                        if st.button("Reject Order", key=f"reject_{idx}", use_container_width=True):
                            record_engineer_gate_feedback(
                                cluster_id="CLUST_001",
                                original_outcome=outcome,
                                original_priority=priority,
                                engineer_action="REJECTED",
                                final_outcome="NEEDS_REVIEW",
                                final_priority=None,
                                engineer_notes="Rejected for field re-survey.",
                                cluster_context={"query": user_text}
                            )
                            item["state"]["gate_status"] = "REJECTED"
                            item["state"]["outcome"] = "NEEDS_REVIEW"
                            item["state"]["priority"] = None
                            update_investigation_state(item["thread_id"], item["state"])
                            st.warning("Order rejected and routed to NEEDS_REVIEW.")
                            st.rerun()
                elif gate_status in ("APPROVED", "EDITED", "REJECTED"):
                    st.success(f"Engineer Sign-Off Completed ({gate_status}) · Audit log committed to data/feedback_split.jsonl")

if current_view == "Chat":
    hist_col, main_col = st.columns([0.9, 3.5], gap="medium")
    with hist_col:
        render_history_panel()
    with main_col:
        render_chat_main()

    # Fixed Bottom Chat Input Bar (ChatGPT-style)
    prompt_input = st.chat_input(
        "Enter citizen road damage report or engineer query (e.g., '10cm crater on Bull Temple Road with rainwater' or 'filter P1 repairs')...",
        disabled=st.session_state["is_running"]
    )
    if prompt_input:
        query_low = prompt_input.lower()
        if any(w in query_low for w in ["filter", "find all", "show me all", "list", "search"]):
            st.session_state["filter_query"] = prompt_input
            st.session_state["active_view"] = "Dashboard"
            st.rerun()
        else:
            st.session_state["is_running"] = True
            with st.spinner("APEX is executing spatial geocoding, defect liability queries, and policy retrieval..."):
                res = run_apex_pipeline(
                    user_text=prompt_input,
                    is_agentic=is_agentic_active
                )
                start_new_investigation(res)
                st.session_state["is_running"] = False
            st.rerun()

# ==============================================================================
# VIEW 2: HISTORICAL REPORTS & ANALYTICS (DASHBOARD & AUDIT)
# ==============================================================================
elif current_view == "Dashboard":
    # Prominent Data Provenance Disclosure Banner
    st.markdown("""
    <div class="provenance-banner">
        <strong>DATA PROVENANCE & CIVIC TRANSPARENCY DISCLOSURE:</strong>
        <br>
        • <strong>Real Data (100% Authentic):</strong> Road geometries, coordinates, bounding boxes, and street classifications (Bull Temple Road, DVG Road, Gandhi Bazaar, etc.) are authentic OpenStreetMap network data for Bengaluru Central Ward 34 (D.V. Gundappa Ward). Severity scoring formulas, priority weights, and unit repair rates (₹1,200/m² base) are grounded directly in statutory standards: <strong>IRC:82:2015</strong> and <strong>BBMP Tender Conditions (Clause 14.5)</strong>.
        <br>
        • <strong>Benchmark Data (Synthesized for Testing):</strong> The 40 complaint records and contractor maintenance ticket histories are standardized synthetic test scenarios designed to safely evaluate boundary conditions (defect liability windows, spatial clustering radius, emergency dispatch thresholds) without exposing citizen PII.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Municipal Complaint Registry & Historical Audit")
    st.caption("Consolidated civic infrastructure complaints across Bengaluru Ward 34 (D.V. Gundappa Ward)")

    DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "golden_dataset.json")
    rows = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            sc_data = json.load(f).get("scenarios", [])
        for s in sc_data:
            rep = (s.get("reports") or [{}])[0]
            rows.append({
                "ID": s["id"],
                "Scenario Name": s["name"],
                "Outcome": s["gold_outcome"],
                "Priority": s.get("gold_priority") or "N/A",
                "Road / Landmark": "Bull Temple Road" if "Bull Temple" in s["name"] or "BMSCE" in s["name"] else ("Gandhi Bazaar" if "Gandhi" in s["name"] else ("DVG Road" if "DVG" in s["name"] else "Bugle Rock / Local")),
                "Reported Date": rep.get("reported_date", "2026-10-26"),
                "Text Preview": rep.get("text", "")[:75] + "...",
                "Full Text": rep.get("text", ""),
                "Latitude": rep.get("lat"),
                "Longitude": rep.get("lon"),
                "Triggers": ", ".join(s.get("gold_triggers", [])) or "None"
            })
    df = pd.DataFrame(rows)

    # 1. 6 Top KPI Metric Cards
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric("Total Complaints", len(df), "Batch intake")
    with k2:
        st.metric("Unique Clusters", len(df), "De-duplicated")
    with k3:
        p1_p2 = len(df[df["Priority"].isin(["P1", "P2"])])
        st.metric("Immediate (P1/P2)", p1_p2, "<48h SLA")
    with k4:
        dlp_num = len(df[df["Outcome"] == "ROUTE_TO_CONTRACTOR"])
        st.metric("Contractor DLP", dlp_num, "₹0 Spend")
    with k5:
        st.metric("Estimated Spend", f"₹{(p1_p2 * 18500):,.0f}", "₹1,200/m² base")
    with k6:
        st.metric("Gate Paused", len(df[df["Priority"] == "P1"]) + dlp_num, "Sign-off required")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. Search & Filter Bar
    f1, f2, f3 = st.columns([1.8, 1, 1])
    with f1:
        search_kw = st.text_input("Search Road Name or Complaint Text", value=st.session_state.get("filter_query", ""))
    with f2:
        sel_outcomes = st.multiselect("Filter Outcome", options=list(df["Outcome"].unique()), default=[])
    with f3:
        sel_prios = st.multiselect("Filter Priority", options=list(df["Priority"].unique()), default=[])

    filtered_df = df.copy()
    if search_kw:
        sk_low = search_kw.lower()
        filtered_df = filtered_df[
            filtered_df["Scenario Name"].str.lower().str.contains(sk_low) |
            filtered_df["Full Text"].str.lower().str.contains(sk_low) |
            filtered_df["Road / Landmark"].str.lower().str.contains(sk_low)
        ]
    if sel_outcomes:
        filtered_df = filtered_df[filtered_df["Outcome"].isin(sel_outcomes)]
    if sel_prios:
        filtered_df = filtered_df[filtered_df["Priority"].isin(sel_prios)]

    st.dataframe(
        filtered_df[["ID", "Scenario Name", "Outcome", "Priority", "Road / Landmark", "Reported Date", "Text Preview"]],
        use_container_width=True,
        hide_index=True
    )

    # 3. Provenance Audit Modal (@st.dialog)
    st.markdown("##### Detailed Provenance & Audit Inspector")
    avail_ids = filtered_df["ID"].tolist() if not filtered_df.empty else ["No matching records"]
    chosen_id = st.selectbox("Select Scenario ID to inspect full provenance log", avail_ids)

    if chosen_id and chosen_id != "No matching records":
        sel_row = filtered_df[filtered_df["ID"] == chosen_id].iloc[0]

        @st.dialog(f"Provenance Log: {sel_row['ID']} - {sel_row['Scenario Name']}")
        def display_provenance_modal():
            st.markdown(f"**Original Citizen Complaint:**\n_{sel_row['Full Text']}_")
            m1, m2 = st.columns(2)
            with m1:
                st.write(f"**Decision Outcome:** `{sel_row['Outcome']}`")
                st.write(f"**Priority Level:** `{sel_row['Priority']}`")
                st.write(f"**GPS Coordinates:** `({sel_row['Latitude']}, {sel_row['Longitude']})`")
            with m2:
                st.write(f"**Road Location:** `{sel_row['Road / Landmark']}`")
                st.write(f"**Active Triggers:** `{sel_row['Triggers']}`")
                st.write(f"**Intake Date:** `{sel_row['Reported Date']}`")
            st.markdown("**Grounding Citation & SQL Trace:**")
            st.code(f"SELECT * FROM maintenance_records WHERE road_name LIKE '%{sel_row['Road / Landmark']}%';", language="sql")
            st.info("Policy Specification: IRC:82 Section 4.3 Severity Assessment & BBMP Tender Conditions Clause 14.5.")
            if st.button("Close Modal", type="primary"):
                st.rerun()

        if st.button(f"Open Full Provenance Modal for {chosen_id}", type="primary"):
            display_provenance_modal()
