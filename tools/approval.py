"""
Tool 7: request_approval
Evaluates human-in-the-loop approval gate triggers (Design Document Section 4).
Pauses execution if:
1. REPAIR_NOW with priority P1
2. ROUTE_TO_CONTRACTOR (contractual consequences)
3. NEEDS_REVIEW (safety fallback / unresolved evidence)
4. Estimated repair cost > 25,000 INR
"""

from typing import Dict, Any, List, Optional

COST_GATE_THRESHOLD_INR = 25000.0

def evaluate_gate_triggers(
    outcome: str,
    priority: Optional[str] = None,
    cost_inr: float = 0.0,
    is_conflicting_evidence: bool = False,
    is_unresolved_location: bool = False
) -> Dict[str, Any]:
    """
    Evaluates whether an outcome requires human engineer sign-off at the approval gate.
    """
    triggers: List[str] = []

    # Trigger 1: REPAIR_NOW at P1
    if outcome == "REPAIR_NOW" and priority == "P1":
        triggers.append("P1 Emergency Repair: Mandatory sign-off for immediate 24h work order dispatch")

    # Trigger 2: ROUTE_TO_CONTRACTOR
    if outcome == "ROUTE_TO_CONTRACTOR":
        triggers.append("Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations")

    # Trigger 3: NEEDS_REVIEW
    if outcome == "NEEDS_REVIEW":
        triggers.append("Safety Fallback: Unresolved location, conflicting reports, or missing citation")

    # Trigger 4: Cost Gate
    if cost_inr > COST_GATE_THRESHOLD_INR:
        triggers.append(f"Cost Gate Threshold Exceeded: Estimated cost ₹{cost_inr:,.2f} > threshold ₹{COST_GATE_THRESHOLD_INR:,.2f}")

    requires_approval = len(triggers) > 0

    return {
        "requires_approval": requires_approval,
        "active_triggers": triggers,
        "trigger_count": len(triggers),
        "cost_threshold_inr": COST_GATE_THRESHOLD_INR
    }

def request_approval(
    cluster_id: str,
    outcome: str,
    priority: Optional[str] = None,
    cost_inr: float = 0.0,
    rationale: str = "",
    citation: str = ""
) -> Dict[str, Any]:
    """
    Public tool function to structure approval package.
    """
    eval_result = evaluate_gate_triggers(
        outcome=outcome,
        priority=priority,
        cost_inr=cost_inr
    )

    return {
        "cluster_id": cluster_id,
        "outcome": outcome,
        "priority": priority,
        "cost_inr": cost_inr,
        "requires_approval": eval_result["requires_approval"],
        "active_triggers": eval_result["active_triggers"],
        "rationale": rationale,
        "citation": citation,
        "status": "PAUSED_AT_GATE" if eval_result["requires_approval"] else "AUTO_APPROVED"
    }
