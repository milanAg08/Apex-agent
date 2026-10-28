"""
CLI Interactive Runner and Trace Walkthrough for Road-Damage Prioritization Agent.
Demonstrates:
- Visible ReAct reasoning ('Thought', 'Action', 'Observation')
- Dynamic branching across Branches A, B, C, and D
- Human-in-the-Loop gate pause and interactive engineer sign-off
"""

import sys
import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from agent.graph import create_road_agent_graph
from agent.state import RoadAgentState
from observability.tracer import AgentTracer, record_engineer_gate_feedback

console = Console()

DEMO_SCENARIOS = {
    "1": {
        "title": "Branch A Demo: Duplicate of Open Ticket",
        "description": "Complaint outside Upahara Darshini on DVG Road north, where ticket TKT_DVG_101 is already active.",
        "reports": [
            {
                "report_id": "DEMO_REP_A",
                "lat": 12.9432,
                "lon": 77.5738,
                "text": "Huge crater pothole outside Upahara Darshini on DVG Road north, vehicles slowing down dangerously",
                "reported_date": "2026-10-26"
            }
        ]
    },
    "2": {
        "title": "Branch B Demo: Weak & Vague Evidence",
        "description": "Complaint with vague text description and no GPS coordinates.",
        "reports": [
            {
                "report_id": "DEMO_REP_B",
                "lat": None,
                "lon": None,
                "text": "somewhere near a tree in bangalore road is broken please fix",
                "reported_date": "2026-10-26"
            }
        ]
    },
    "3": {
        "title": "Branch C Demo: Contractor Defect Liability Recurrence",
        "description": "Pothole on Gandhi Bazaar Main Road, resurfaced within the 2-year warranty period.",
        "reports": [
            {
                "report_id": "DEMO_REP_C",
                "lat": 12.9435,
                "lon": 77.5715,
                "text": "Gandhi bazaar main road surface peeling off near vegetable stalls, asphalt crumbling",
                "reported_date": "2026-10-26"
            }
        ]
    },
    "4": {
        "title": "Branch D Demo: Critical Arterial Damage (Emergency P1)",
        "description": "Deep 9cm waterlogged pothole on Bull Temple Road (BMSCE Frontage) with heavy bus traffic.",
        "reports": [
            {
                "report_id": "DEMO_REP_D",
                "lat": 12.9375,
                "lon": 77.5692,
                "text": "Deep 9cm crater on Bull Temple Road wheel path, standing rainwater puddle, BMTC buses swerving",
                "reported_date": "2026-10-26"
            }
        ]
    }
}

def run_interactive_demo():
    console.print(Panel.fit(
        "[bold cyan]Road-Damage Repair Prioritization Agent[/bold cyan]\n"
        "[italic]Civic Infrastructure & Urban Planning - BMSCE Review 2 Prototype[/italic]",
        border_style="cyan"
    ))

    console.print("\n[bold]Select a decision branch scenario to execute:[/bold]")
    for key, sc in DEMO_SCENARIOS.items():
        console.print(f" [bold green]{key}[/bold green]. {sc['title']}")
        console.print(f"    [dim]{sc['description']}[/dim]")

    choice = Prompt.ask("\nEnter scenario choice (1-4)", choices=["1", "2", "3", "4"], default="4")
    selected = DEMO_SCENARIOS[choice]

    console.print(f"\n[bold yellow]>>> Launching {selected['title']}...[/bold yellow]\n")

    app = create_road_agent_graph()
    thread_id = f"demo_thread_{choice}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: RoadAgentState = {
        "run_id": thread_id,
        "scenario_id": f"DEMO_SCENARIO_{choice}",
        "reports": selected["reports"],
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

    # Step-by-step stream with visible reasoning
    state = app.invoke(initial_state, config=config)

    # Print Thought Trajectory
    console.print(Panel("[bold]VISIBLE REACT REASONING TRAJECTORY[/bold]", style="bold blue"))
    for t in state.get("thoughts", []):
        console.print(f"\n[bold yellow]Step {t['step_number']}:[/bold yellow]")
        console.print(f"[bold cyan]{t['thought']}[/bold cyan]")
        console.print(f"  [bold]Action:[/bold] {t['action']}")
        console.print(f"  [bold]Action Input:[/bold] {t['action_input']}")
        console.print(f"  [bold]Observation:[/bold] [italic green]{t['observation']}[/italic green]")

    # Check if halted at approval gate
    snapshot = app.get_state(config)
    if snapshot.next:
        console.print("\n" + "="*70)
        console.print(Panel(
            f"[bold red]HUMAN-IN-THE-LOOP APPROVAL GATE PAUSED[/bold red]\n\n"
            f"Preliminary Outcome: [bold]{state.get('outcome')}[/bold]\n"
            f"Priority: [bold]{state.get('priority') or 'N/A'}[/bold]\n"
            f"Active Triggers:\n" + "\n".join([f"  • {tr}" for tr in state.get('gate_triggers', [])]) + "\n\n"
            f"Cited Clause: {state.get('citation')}\n"
            f"Rationale: {state.get('rationale')}",
            title="[bold yellow]Approval Gate Triggered[/bold yellow]",
            border_style="red"
        ))

        engineer_choice = Prompt.ask(
            "Engineer Decision",
            choices=["Approve", "Edit", "Reject"],
            default="Approve"
        )

        final_outcome = state.get("outcome")
        final_priority = state.get("priority")
        notes = "No edits."

        if engineer_choice == "Edit":
            final_outcome = Prompt.ask("Override Outcome", choices=["REPAIR_NOW", "INSPECT", "ROUTE_TO_CONTRACTOR", "NEEDS_REVIEW"], default=final_outcome)
            final_priority = Prompt.ask("Override Priority", choices=["P1", "P2", "P3", "P4", "None"], default=final_priority or "None")
            notes = Prompt.ask("Engineer justification notes", default="Adjusted per on-site ground inspection.")
        elif engineer_choice == "Reject":
            final_outcome = "NEEDS_REVIEW"
            notes = "Rejected by engineer for field re-survey."

        # Record feedback into feedback split
        record_engineer_gate_feedback(
            cluster_id=state.get("active_cluster", {}).get("cluster_id", "CLUST_001"),
            original_outcome=state.get("outcome", ""),
            original_priority=state.get("priority"),
            engineer_action=engineer_choice.upper(),
            final_outcome=final_outcome,
            final_priority=final_priority if final_priority != "None" else None,
            engineer_notes=notes,
            cluster_context={"scenario": selected["title"]}
        )

        console.print(f"\n[bold green]Engineer decision ({engineer_choice}) logged to feedback split.[/bold green]")

        # Resume graph execution
        state = app.invoke(None, config=config)

    console.print("\n" + "="*70)
    console.print(Panel(
        f"[bold green]WORKFLOW COMPLETED[/bold green]\n\n"
        f"Final Decision Outcome: [bold yellow]{state.get('outcome')}[/bold yellow]\n"
        f"Priority Assigned: [bold yellow]{state.get('priority') or 'N/A'}[/bold yellow]\n"
        f"Official Citation: {state.get('citation')}\n"
        f"Engineering Rationale: {state.get('rationale')}",
        title="[bold green]Final Dispatch Result[/bold green]",
        border_style="green"
    ))

if __name__ == "__main__":
    run_interactive_demo()
