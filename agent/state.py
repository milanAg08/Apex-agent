"""
State Definitions for the Road-Damage Prioritization LangGraph Workflow.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

class ThoughtStep(TypedDict):
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Optional[str]

class RoadAgentState(TypedDict):
    # Run and context identification
    run_id: str
    scenario_id: Optional[str]
    reports: List[Dict[str, Any]]
    
    # Active cluster state
    current_cluster_index: int
    clusters: List[Dict[str, Any]]
    active_cluster: Optional[Dict[str, Any]]
    
    # Bounded execution controls
    step_count: int
    max_steps: int
    loop_limit_hit: bool
    
    # ReAct reasoning trajectory
    thoughts: Annotated[List[ThoughtStep], operator.add]
    
    # Dynamic Branch resolution
    active_branch: Optional[str]  # 'BRANCH_A', 'BRANCH_B', 'BRANCH_C', 'BRANCH_D'
    branch_rationale: Optional[str]
    
    # Tool execution results
    location_result: Optional[Dict[str, Any]]
    maintenance_result: Optional[Dict[str, Any]]
    severity_result: Optional[Dict[str, Any]]
    cost_result: Optional[Dict[str, Any]]
    priority_result: Optional[Dict[str, Any]]
    rag_result: Optional[Dict[str, Any]]
    
    # Outcome and Citations
    outcome: Optional[str]       # MERGE_DUPLICATE, REQUEST_EVIDENCE, ROUTE_TO_CONTRACTOR, INSPECT, REPAIR_NOW, NEEDS_REVIEW
    priority: Optional[str]      # P1, P2, P3, P4, or None
    citation: Optional[str]
    rationale: Optional[str]
    
    # Human-in-the-Loop Approval Gate
    requires_approval: bool
    gate_triggers: List[str]
    gate_status: str             # 'PENDING_EVAL', 'PAUSED_FOR_ENGINEER', 'APPROVED', 'EDITED', 'REJECTED', 'BYPASSED'
    engineer_feedback: Optional[Dict[str, Any]]
    
    # Final consolidated results per cluster
    final_decisions: List[Dict[str, Any]]
