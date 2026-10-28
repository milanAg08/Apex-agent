"""
LangGraph Nodes for Road-Damage Repair Prioritization Agent.
Implements bounded ReAct steps, branch routing (A to D), RAG retrieval, and approval gate.
"""

from typing import Dict, Any, List
from agent.state import RoadAgentState, ThoughtStep
from agent.llm_reasoner import ReActReasoner
from tools.location import resolve_location
from tools.clustering import cluster_reports
from tools.severity import score_severity
from tools.maintenance_db import query_maintenance_db
from tools.cost import estimate_cost
from tools.priority import calculate_priority_score
from tools.rag_tool import retrieve_criteria
from tools.approval import evaluate_gate_triggers, request_approval
from observability.tracer import AgentTracer

reasoner = ReActReasoner()

def intake_node(state: RoadAgentState) -> Dict[str, Any]:
    """Step 1: Intake and Validate. Merges reports into spatial/temporal clusters."""
    reports = state.get("reports", [])
    step_count = state.get("step_count", 0) + 1
    
    first_rep = reports[0] if reports else {}
    thought_text, planned_action = reasoner.generate_intake_thought(len(reports), first_rep)
    
    # Execute clustering tool
    clusters = cluster_reports(reports)
    
    thought_entry: ThoughtStep = {
        "step_number": step_count,
        "thought": thought_text,
        "action": planned_action,
        "action_input": {"report_count": len(reports)},
        "observation": f"Successfully formed {len(clusters)} report cluster(s) for Ward 34."
    }

    return {
        "step_count": step_count,
        "clusters": clusters,
        "current_cluster_index": 0,
        "active_cluster": clusters[0] if clusters else None,
        "thoughts": [thought_entry]
    }

def plan_reason_node(state: RoadAgentState) -> Dict[str, Any]:
    """Step 2: Plan and Reason. Evaluates active cluster for Branch A or Branch B."""
    cluster = state.get("active_cluster")
    step_count = state.get("step_count", 0) + 1
    
    if not cluster:
        return {"step_count": step_count}

    thought_text, planned_action, branch = reasoner.generate_cluster_evaluation_thought(cluster)

    thought_entry: ThoughtStep = {
        "step_number": step_count,
        "thought": thought_text,
        "action": planned_action,
        "action_input": {"cluster_id": cluster.get("cluster_id")},
        "observation": f"Branch status: {branch or 'PROCEED_GEOCODING'}"
    }

    updates: Dict[str, Any] = {
        "step_count": step_count,
        "thoughts": [thought_entry],
        "active_branch": branch
    }

    # Branch A Immediate Stop
    if branch == "BRANCH_A":
        dup_info = cluster.get("duplicate_info", {})
        updates.update({
            "outcome": "MERGE_DUPLICATE",
            "priority": None,
            "citation": f"[Open Ticket Registry - Ticket #{cluster.get('duplicate_ticket_id')}]",
            "rationale": (
                f"Cluster repeats active open ticket {cluster.get('duplicate_ticket_id')} "
                f"({dup_info.get('distance_meters', 0)}m distance, {dup_info.get('days_apart', 0)} days apart). "
                f"Merged to prevent redundant municipal dispatch."
            ),
            "requires_approval": False,
            "gate_status": "BYPASSED"
        })

    return updates

def tool_node(state: RoadAgentState) -> Dict[str, Any]:
    """Step 3: Call deterministic tools for geocoding and maintenance lookup."""
    cluster = state.get("active_cluster")
    step_count = state.get("step_count", 0) + 1
    
    if not cluster:
        return {"step_count": step_count}

    # 1. Location Resolution
    lat = cluster.get("centroid_lat")
    lon = cluster.get("centroid_lon")
    text = cluster.get("combined_text", "")
    loc_res = resolve_location(lat=lat, lon=lon, text=text)

    # Check Branch B (Weak Evidence / Unresolved Location)
    if loc_res.get("status") == "UNRESOLVED":
        thought_text = (
            f"THOUGHT [Branch B - Unresolved Evidence]: Location geocoding failed. "
            f"Neither coordinates nor text matched known Ward 34 infrastructure. "
            f"Per Branch B, triggering REQUEST_EVIDENCE for citizen photo/pin."
        )
        thought_entry: ThoughtStep = {
            "step_number": step_count,
            "thought": thought_text,
            "action": "REQUEST_EVIDENCE",
            "action_input": {"cluster_id": cluster.get("cluster_id")},
            "observation": "Location remains unresolved. Halting further computation."
        }
        return {
            "step_count": step_count,
            "location_result": loc_res,
            "active_branch": "BRANCH_B",
            "outcome": "REQUEST_EVIDENCE",
            "priority": None,
            "citation": "[Municipal Citizen Intake Protocol - Verification Standards]",
            "rationale": "Location coordinates and description are insufficient to identify road segment. Requesting photo or GPS pin.",
            "requires_approval": False,
            "gate_status": "BYPASSED",
            "thoughts": [thought_entry]
        }

    # 2. Query Maintenance Database
    seg_id = loc_res.get("segment_id")
    maint_res = query_maintenance_db(seg_id)
    
    thought_text, planned_action, branch = reasoner.generate_liability_decision_thought(
        cluster.get("cluster_id"), maint_res
    )

    thought_entry = {
        "step_number": step_count,
        "thought": thought_text,
        "action": planned_action,
        "action_input": {"segment_id": seg_id},
        "observation": f"Maintenance record loaded. Liability status: {maint_res.get('is_under_liability')}"
    }

    return {
        "step_count": step_count,
        "location_result": loc_res,
        "maintenance_result": maint_res,
        "active_branch": branch,
        "thoughts": [thought_entry]
    }

def rag_node(state: RoadAgentState) -> Dict[str, Any]:
    """Step 4: Retrieve and Grade criteria using agentic RAG."""
    branch = state.get("active_branch")
    loc_res = state.get("location_result") or {}
    step_count = state.get("step_count", 0) + 1
    road_class = loc_res.get("road_class", "collector")

    if branch == "BRANCH_C":
        query = "BBMP tender defect liability period contractor recurrence warranty"
        category = "defect_liability"
    else:
        query = f"IRC:82 action threshold severity for {road_class} road inspect or repair"
        category = "action_thresholds"

    rag_res = retrieve_criteria(query=query, category=category)

    thought_text = (
        f"THOUGHT [Agentic RAG Graded]: Retrieved citation '{rag_res.get('citation')}' "
        f"with confidence {rag_res.get('confidence_score')}. "
        f"Fallback used: {rag_res.get('fallback_used')}. Rewrites: {rag_res.get('rewrites_attempted')}."
    )
    thought_entry: ThoughtStep = {
        "step_number": step_count,
        "thought": thought_text,
        "action": "retrieve_criteria",
        "action_input": {"query": query, "category": category},
        "observation": f"Criteria retrieved and verified under {rag_res.get('clause')}"
    }

    return {
        "step_count": step_count,
        "rag_result": rag_res,
        "citation": rag_res.get("citation"),
        "thoughts": [thought_entry]
    }

def decide_rank_node(state: RoadAgentState) -> Dict[str, Any]:
    """Step 5: Decide outcome and priority (Branches C and D)."""
    branch = state.get("active_branch")
    step_count = state.get("step_count", 0) + 1
    cluster = state.get("active_cluster") or {}
    loc_res = state.get("location_result") or {}
    maint_res = state.get("maintenance_result") or {}
    rag_res = state.get("rag_result") or {}

    # Branch C Resolution
    if branch == "BRANCH_C":
        contractor = maint_res.get("contractor_name", "Contractor")
        warranty_end = maint_res.get("liability_expiry_date", "")
        rationale = (
            f"Road segment was resurfaced on {maint_res.get('last_repair_date')} and remains under "
            f"statutory defect liability until {warranty_end}. Per {rag_res.get('citation')}, damage must be "
            f"rectified by {contractor} at zero cost to the municipality."
        )
        gate_eval = evaluate_gate_triggers(outcome="ROUTE_TO_CONTRACTOR", priority=None, cost_inr=0.0)
        
        thought_text = (
            f"THOUGHT: Routing defect directly to {contractor}. Bypassing priority scoring because "
            f"rectification is contractor's contractual liability. Flagging for mandatory engineer sign-off gate."
        )
        thought_entry: ThoughtStep = {
            "step_number": step_count,
            "thought": thought_text,
            "action": "request_approval",
            "action_input": {"outcome": "ROUTE_TO_CONTRACTOR"},
            "observation": "Branch C decision finalized. Pausing at gate."
        }

        return {
            "step_count": step_count,
            "outcome": "ROUTE_TO_CONTRACTOR",
            "priority": None,
            "rationale": rationale,
            "requires_approval": gate_eval["requires_approval"],
            "gate_triggers": gate_eval["active_triggers"],
            "gate_status": "PAUSED_FOR_ENGINEER" if gate_eval["requires_approval"] else "APPROVED",
            "thoughts": [thought_entry]
        }

    # Branch D: Fresh Damage Computation
    # 1. Extract physical attributes and compute severity
    text = cluster.get("combined_text", "")
    attrs = reasoner.extract_complaint_attributes(text)
    sev_res = score_severity(
        depth_cm=attrs["depth_cm"],
        area_sqm=attrs["area_sqm"],
        standing_water=attrs["standing_water"],
        location_on_carriageway=attrs["location_on_carriageway"],
        is_traffic_blocking=attrs["is_traffic_blocking"]
    )
    severity_score = sev_res["severity_score"]

    # 2. Cost estimation
    road_class = loc_res.get("road_class", "collector")
    cost_res = estimate_cost(
        area_m2=attrs["area_sqm"],
        depth_cm=attrs["depth_cm"],
        road_class=road_class
    )
    total_cost = cost_res["estimated_cost_inr"]

    # 3. Priority calculation
    p_res = calculate_priority_score(
        severity=severity_score,
        traffic_index=loc_res.get("traffic_index", 0.5),
        repair_history_risk=maint_res.get("repair_history_risk", 0.5),
        report_count=cluster.get("report_count", 1),
        road_class=road_class
    )
    priority_level = p_res["priority_level"]

    # 4. Action threshold evaluation
    thresholds = {"arterial": 0.65, "sub_arterial": 0.70, "collector": 0.75, "local": 0.85}
    action_threshold = thresholds.get(road_class.lower(), 0.70)

    if severity_score >= action_threshold:
        outcome = "REPAIR_NOW"
    else:
        outcome = "INSPECT"

    rationale = (
        f"Assessed on {loc_res.get('road_name')} ({road_class}). "
        f"Severity score {severity_score:.2f} (threshold {action_threshold:.2f}). "
        f"Estimated patch cost ₹{total_cost:,.2f}. Priority {priority_level} ({p_res['response_time_sla']})."
    )

    gate_eval = evaluate_gate_triggers(
        outcome=outcome,
        priority=priority_level,
        cost_inr=total_cost
    )

    thought_text = (
        f"THOUGHT [Branch D - Scoring Complete]: Computed severity={severity_score:.2f}, "
        f"priority={priority_level}, cost=₹{total_cost:,.2f}. Outcome={outcome}. "
        f"Gate triggers active: {gate_eval['active_triggers']}."
    )
    thought_entry = {
        "step_number": step_count,
        "thought": thought_text,
        "action": "request_approval",
        "action_input": {"outcome": outcome, "priority": priority_level, "cost": total_cost},
        "observation": f"Gate evaluation complete. Requires approval: {gate_eval['requires_approval']}"
    }

    return {
        "step_count": step_count,
        "severity_result": sev_res,
        "cost_result": cost_res,
        "priority_result": p_res,
        "outcome": outcome,
        "priority": priority_level,
        "rationale": rationale,
        "requires_approval": gate_eval["requires_approval"],
        "gate_triggers": gate_eval["active_triggers"],
        "gate_status": "PAUSED_FOR_ENGINEER" if gate_eval["requires_approval"] else "APPROVED",
        "thoughts": [thought_entry]
    }

def approval_gate_node(state: RoadAgentState) -> Dict[str, Any]:
    """Step 6: Human-in-the-loop gate node. Checkpoints state and handles engineer decision."""
    requires_approval = state.get("requires_approval", False)
    status = state.get("gate_status", "APPROVED")
    
    cost_dict = state.get("cost_result") or {}
    cluster = state.get("active_cluster") or {}
    decision_summary = {
        "cluster_id": cluster.get("cluster_id", "CLUST_001"),
        "outcome": state.get("outcome"),
        "priority": state.get("priority"),
        "cost_inr": cost_dict.get("estimated_cost_inr", 0.0),
        "citation": state.get("citation"),
        "rationale": state.get("rationale"),
        "gate_status": status,
        "gate_triggers": state.get("gate_triggers", []),
        "engineer_feedback": state.get("engineer_feedback")
    }

    current_decisions = list(state.get("final_decisions", []))
    current_decisions.append(decision_summary)

    return {
        "final_decisions": current_decisions,
        "gate_status": status
    }
