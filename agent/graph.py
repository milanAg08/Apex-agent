"""
LangGraph Workflow Assembly for Road-Damage Repair Prioritization.
Bounded state machine with SQLite checkpointing and Human-in-the-Loop approval gate.
"""

import os
import sqlite3
from typing import Optional, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver

from agent.state import RoadAgentState
from agent.nodes import (
    intake_node,
    plan_reason_node,
    tool_node,
    rag_node,
    decide_rank_node,
    approval_gate_node
)

CHECKPOINT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "checkpoints.sqlite")

def route_after_planning(state: RoadAgentState) -> Literal["approval_gate", "tools"]:
    """Conditional router after plan_reason_node."""
    # Branch A: Duplicates skip all downstream tools & retrieval
    if state.get("active_branch") == "BRANCH_A":
        return "approval_gate"
    return "tools"

def route_after_tools(state: RoadAgentState) -> Literal["approval_gate", "rag"]:
    """Conditional router after tool_node."""
    # Branch B: Unresolved location / weak evidence skips to gate/output
    if state.get("active_branch") == "BRANCH_B":
        return "approval_gate"
    return "rag"

def create_road_agent_graph(checkpointer=None):
    """
    Constructs and compiles the bounded LangGraph prioritization workflow.
    """
    workflow = StateGraph(RoadAgentState)

    # 1. Register Graph Nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("plan_reason", plan_reason_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("decide_rank", decide_rank_node)
    workflow.add_node("approval_gate", approval_gate_node)

    # 2. Add Graph Edges
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "plan_reason")

    # Conditional Branch after Planning
    workflow.add_conditional_edges(
        "plan_reason",
        route_after_planning,
        {
            "approval_gate": "approval_gate",
            "tools": "tools"
        }
    )

    # Conditional Branch after Tools
    workflow.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "approval_gate": "approval_gate",
            "rag": "rag"
        }
    )

    workflow.add_edge("rag", "decide_rank")
    workflow.add_edge("decide_rank", "approval_gate")
    workflow.add_edge("approval_gate", END)

    # Compile with checkpointer and human-in-the-loop interrupt if specified
    if checkpointer is None:
        checkpointer = MemorySaver()

    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval_gate"]
    )
    return app

def run_agent_workflow(
    reports: list,
    scenario_id: Optional[str] = None,
    auto_approve: bool = True
) -> dict:
    """
    Executes the agent workflow end-to-end for a given batch of reports.
    If auto_approve is True, automatically resumes if paused at the approval gate.
    """
    # Use MemorySaver for fast thread-isolated execution
    checkpointer = MemorySaver()
    app = create_road_agent_graph(checkpointer=checkpointer)

    thread_id = f"thread_{scenario_id or 'run'}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: RoadAgentState = {
        "run_id": thread_id,
        "scenario_id": scenario_id,
        "reports": reports,
        "current_cluster_index": 0,
        "clusters": [],
        "active_cluster": None,
        "step_count": 0,
        "max_steps": 10,
        "loop_limit_hit": False,
        "thoughts": [],
        "active_branch": None,
        "branch_rationale": None,
        "location_result": None,
        "maintenance_result": None,
        "severity_result": None,
        "cost_result": None,
        "priority_result": None,
        "rag_result": None,
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

    # Execute until interrupt or completion
    state = app.invoke(initial_state, config=config)

    # Check if interrupted before approval gate
    state_snapshot = app.get_state(config)
    if state_snapshot.next:  # Paused before approval_gate
        if auto_approve:
            # Resume past gate
            state = app.invoke(None, config=config)

    return state
