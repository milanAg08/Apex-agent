"""
Evaluation Runner for Road-Damage Repair Prioritization Agent.
Executes the agent workflow across the 10 Tuning and 30 Held-Out Test scenarios.
Prints formatted tables and metrics reports against all design document provisional targets.
"""

import json
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agent.graph import run_agent_workflow
from evals.metrics import compute_decision_metrics

console = Console()
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "golden_dataset.json")

def run_evaluation(split: str = "test") -> dict:
    if not os.path.exists(DATA_PATH):
        console.print(f"[bold red]Golden dataset not found at {DATA_PATH}[/bold red]")
        sys.exit(1)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = [s for s in data["scenarios"] if s.get("split") == split or split == "all"]
    console.print(Panel(f"Running Evaluation on Split: [bold green]{split.upper()}[/bold green] ({len(scenarios)} scenarios)", expand=False))

    predictions = []
    gold_items = []

    results_table = Table(title=f"Scenario Results ({split.upper()})", show_header=True, header_style="bold cyan")
    results_table.add_column("ID", style="bold")
    results_table.add_column("Scenario Name", max_width=32)
    results_table.add_column("Gold Outcome", style="yellow")
    results_table.add_column("Pred Outcome", style="green")
    results_table.add_column("Gold Prio")
    results_table.add_column("Pred Prio")
    results_table.add_column("Gate Paused")
    results_table.add_column("Status", justify="center")

    for s in scenarios:
        reports = s.get("reports", [])
        state = run_agent_workflow(reports=reports, scenario_id=s["id"], auto_approve=True)
        
        pred_outcome = state.get("outcome")
        gold_outcome = s.get("gold_outcome")
        pred_prio = state.get("priority")
        gold_prio = s.get("gold_priority")
        gate_paused = state.get("requires_approval", False)

        is_match = (pred_outcome == gold_outcome)
        status_str = "[bold green]PASS[/bold green]" if is_match else "[bold red]FAIL[/bold red]"

        results_table.add_row(
            s["id"],
            s["name"][:32],
            gold_outcome or "-",
            pred_outcome or "-",
            gold_prio or "-",
            pred_prio or "-",
            "YES" if gate_paused else "NO",
            status_str
        )

        predictions.append({
            "outcome": pred_outcome,
            "priority": pred_prio,
            "citation": state.get("citation", ""),
            "requires_approval": gate_paused,
            "gate_status": state.get("gate_status")
        })
        gold_items.append(s)

    console.print(results_table)

    # Compute comprehensive layer metrics
    metrics = compute_decision_metrics(predictions, gold_items)

    metrics_table = Table(title=f"Evaluation Performance Metrics ({split.upper()})", show_header=True, header_style="bold magenta")
    metrics_table.add_column("Evaluation Layer")
    metrics_table.add_column("Metric Name")
    metrics_table.add_column("Score / Rate", style="bold green")
    metrics_table.add_column("Target (Sec 5.2)", style="cyan")
    metrics_table.add_column("Status")

    metrics_table.add_row(
        "Decision Layer",
        "Overall Outcome Accuracy",
        f"{metrics['overall_accuracy']*100:.1f}%",
        ">= 80.0%",
        "[bold green]MET[/bold green]" if metrics['overall_accuracy'] >= 0.80 else "[bold red]UNMET[/bold red]"
    )
    metrics_table.add_row(
        "Decision Layer",
        "ROUTE_TO_CONTRACTOR Precision",
        f"{metrics['route_to_contractor']['precision']*100:.1f}%",
        ">= 85.0%",
        "[bold green]MET[/bold green]" if metrics['route_to_contractor']['precision'] >= 0.85 else "[bold red]UNMET[/bold red]"
    )
    metrics_table.add_row(
        "Decision Layer",
        "ROUTE_TO_CONTRACTOR Recall",
        f"{metrics['route_to_contractor']['recall']*100:.1f}%",
        ">= 85.0%",
        "[bold green]MET[/bold green]" if metrics['route_to_contractor']['recall'] >= 0.85 else "[bold red]UNMET[/bold red]"
    )
    metrics_table.add_row(
        "Ranking & Safety",
        "P1 Emergency Recall",
        f"{metrics['safety_and_ranking']['p1_recall']*100:.1f}%",
        ">= 95.0%",
        "[bold green]MET[/bold green]" if metrics['safety_and_ranking']['provisional_target_met'] else "[bold red]UNMET[/bold red]"
    )
    metrics_table.add_row(
        "Retrieval Layer",
        "Citation Hit Rate",
        f"{metrics['retrieval']['citation_hit_rate']*100:.1f}%",
        ">= 85.0%",
        "[bold green]MET[/bold green]" if metrics['retrieval']['provisional_target_met'] else "[bold red]UNMET[/bold red]"
    )
    metrics_table.add_row(
        "Behaviour & Gate",
        "Approval Gate Pause Compliance",
        f"{metrics['gate_safety']['pause_rate']*100:.1f}%",
        "100.0%",
        "[bold green]MET[/bold green]" if metrics['gate_safety']['target_100_met'] else "[bold red]UNMET[/bold red]"
    )

    console.print(metrics_table)
    return metrics

if __name__ == "__main__":
    split_to_run = sys.argv[1] if len(sys.argv) > 1 else "test"
    run_evaluation(split=split_to_run)
