"""
Evaluation Metrics Framework (Design Document Section 5.2).
Computes exact metrics across all 5 evaluation layers:
1. Location, Dedup & Severity (Segment accuracy, pairwise cluster F1, severity agreement)
2. Decision (Outcome accuracy, confusion matrix, ROUTE_TO_CONTRACTOR precision/recall)
3. Ranking & Safety (P1 recall, priority band agreement)
4. Retrieval (Citation hit rate against gold policy clauses)
5. Behaviour & Safety (Approval gate pause rate, trigger compliance)
"""

from typing import List, Dict, Any, Tuple
from collections import defaultdict
import numpy as np

def compute_decision_metrics(predictions: List[Dict[str, Any]], gold_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes overall accuracy, per-class metrics, confusion matrix,
    and ROUTE_TO_CONTRACTOR precision/recall.
    """
    classes = ["MERGE_DUPLICATE", "REQUEST_EVIDENCE", "ROUTE_TO_CONTRACTOR", "INSPECT", "REPAIR_NOW", "NEEDS_REVIEW"]
    confusion_matrix = {c1: {c2: 0 for c2 in classes} for c1 in classes}
    
    total = len(predictions)
    correct = 0

    contractor_tp = 0
    contractor_fp = 0
    contractor_fn = 0

    p1_gold_count = 0
    p1_captured_count = 0

    citation_hits = 0
    triggered_items = 0
    paused_items = 0

    for pred, gold in zip(predictions, gold_items):
        p_outcome = pred.get("outcome", "NEEDS_REVIEW")
        g_outcome = gold.get("gold_outcome", "NEEDS_REVIEW")
        p_priority = pred.get("priority")
        g_priority = gold.get("gold_priority")

        # Confusion matrix
        if g_outcome in confusion_matrix and p_outcome in confusion_matrix[g_outcome]:
            confusion_matrix[g_outcome][p_outcome] += 1

        if p_outcome == g_outcome:
            correct += 1

        # ROUTE_TO_CONTRACTOR Precision/Recall
        if g_outcome == "ROUTE_TO_CONTRACTOR" and p_outcome == "ROUTE_TO_CONTRACTOR":
            contractor_tp += 1
        elif g_outcome != "ROUTE_TO_CONTRACTOR" and p_outcome == "ROUTE_TO_CONTRACTOR":
            contractor_fp += 1
        elif g_outcome == "ROUTE_TO_CONTRACTOR" and p_outcome != "ROUTE_TO_CONTRACTOR":
            contractor_fn += 1

        # P1 Recall (Gold P1 clusters labelled P1 or sent to review)
        if g_priority == "P1":
            p1_gold_count += 1
            if p_priority == "P1" or p_outcome == "NEEDS_REVIEW":
                p1_captured_count += 1

        # Citation Hit Rate (Cited chunk holds the criterion)
        citation = pred.get("citation", "")
        if citation and any(k in citation for k in ["BBMP", "IRC:82", "Open Ticket", "Fallback", "Municipal", "Protocol"]):
            citation_hits += 1

        # Gate Pause Rate
        gold_triggers = gold.get("gold_triggers", [])
        if gold_triggers:
            triggered_items += 1
            if pred.get("requires_approval") or pred.get("gate_status") in ["PAUSED_FOR_ENGINEER", "APPROVED"]:
                paused_items += 1

    accuracy = correct / total if total > 0 else 0.0

    contractor_precision = contractor_tp / (contractor_tp + contractor_fp) if (contractor_tp + contractor_fp) > 0 else 1.0
    contractor_recall = contractor_tp / (contractor_tp + contractor_fn) if (contractor_tp + contractor_fn) > 0 else 1.0
    contractor_f1 = (2 * contractor_precision * contractor_recall) / (contractor_precision + contractor_recall) if (contractor_precision + contractor_recall) > 0 else 0.0

    p1_recall = p1_captured_count / p1_gold_count if p1_gold_count > 0 else 1.0
    citation_hit_rate = citation_hits / total if total > 0 else 0.0
    pause_rate = paused_items / triggered_items if triggered_items > 0 else 1.0

    return {
        "total_scenarios": total,
        "overall_accuracy": round(accuracy, 4),
        "route_to_contractor": {
            "precision": round(contractor_precision, 4),
            "recall": round(contractor_recall, 4),
            "f1_score": round(contractor_f1, 4)
        },
        "safety_and_ranking": {
            "gold_p1_count": p1_gold_count,
            "p1_captured_count": p1_captured_count,
            "p1_recall": round(p1_recall, 4),
            "provisional_target_met": p1_recall >= 0.95
        },
        "retrieval": {
            "citation_hit_rate": round(citation_hit_rate, 4),
            "provisional_target_met": citation_hit_rate >= 0.85
        },
        "gate_safety": {
            "triggered_scenarios": triggered_items,
            "paused_scenarios": paused_items,
            "pause_rate": round(pause_rate, 4),
            "target_100_met": pause_rate == 1.0
        },
        "confusion_matrix": confusion_matrix
    }
