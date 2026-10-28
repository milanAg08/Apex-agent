"""
Observability and Tracing Module for Road Repair Agent.
Provides:
1. Step-level and tool-level span instrumentation (compatible with LangSmith & OpenInference).
2. Visible reasoning tracer capturing Thoughts, Actions, Observations, and Retrieval Grades.
3. Feedback loop recorder for Engineer Gate sign-offs/edits into data/feedback_split.jsonl.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

FEEDBACK_SPLIT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "feedback_split.jsonl")

class Span:
    def __init__(self, name: str, span_type: str, metadata: Optional[Dict[str, Any]] = None):
        self.name = name
        self.span_type = span_type  # 'thought', 'tool', 'retrieval_grade', 'gate', 'decision'
        self.metadata = metadata or {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.output: Any = None
        self.status = "RUNNING"

    def end(self, output: Any = None, status: str = "SUCCESS"):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.output = output
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "span_type": self.span_type,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metadata": self.metadata,
            "output": self.output
        }

class AgentTracer:
    """
    Centralized execution tracer for collecting spans, agent thoughts,
    tool invocations, and recording gate feedback loops.
    """
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or f"run_{int(time.time()*1000)}"
        self.spans: List[Span] = []
        self.active_spans: Dict[str, Span] = {}
        self.start_timestamp = datetime.utcnow().isoformat()

    def start_span(self, name: str, span_type: str, metadata: Optional[Dict[str, Any]] = None) -> Span:
        span = Span(name=name, span_type=span_type, metadata=metadata)
        self.spans.append(span)
        self.active_spans[name] = span
        return span

    def end_span(self, name: str, output: Any = None, status: str = "SUCCESS"):
        if name in self.active_spans:
            span = self.active_spans.pop(name)
            span.end(output=output, status=status)

    def log_thought(self, step_number: int, thought: str, planned_action: str):
        """Logs structured LLM visible reasoning thought."""
        span = self.start_span(f"Thought_Step_{step_number}", "thought", {
            "step": step_number,
            "planned_action": planned_action
        })
        span.end(output=thought)

    def log_tool_call(self, tool_name: str, args: Dict[str, Any], result: Any, status: str = "SUCCESS"):
        """Logs tool invocation arguments and results."""
        span = self.start_span(f"Tool_{tool_name}", "tool", {"tool_name": tool_name, "args": args})
        span.end(output=result, status=status)

    def log_retrieval_grade(self, query: str, score: float, passed: bool, fallback_used: bool, citation: str):
        """Logs runtime feedback loop of the agentic RAG grader."""
        span = self.start_span("Retrieval_Grade_Feedback", "retrieval_grade", {
            "query": query,
            "confidence_score": score,
            "passed": passed,
            "fallback_used": fallback_used,
            "citation": citation
        })
        span.end(output={"passed": passed, "fallback": fallback_used})

    def log_gate_event(self, cluster_id: str, outcome: str, active_triggers: List[str], paused: bool):
        """Logs Human-in-the-loop gate trigger checks."""
        span = self.start_span(f"Gate_{cluster_id}", "gate", {
            "cluster_id": cluster_id,
            "outcome": outcome,
            "triggers": active_triggers,
            "paused_for_engineer": paused
        })
        span.end(output={"paused": paused, "triggers": active_triggers})

    def render_rich_summary(self):
        """Prints a colorized terminal trace summary."""
        table = Table(title=f"Agent Run Trace: {self.run_id}", show_header=True, header_style="bold magenta")
        table.add_column("Span Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Details")

        for span in self.spans:
            details = ""
            if span.span_type == "thought":
                details = f"Action: {span.metadata.get('planned_action', '')}"
            elif span.span_type == "tool":
                details = f"Args: {str(span.metadata.get('args', ''))[:40]}..."
            elif span.span_type == "retrieval_grade":
                details = f"Score: {span.metadata.get('confidence_score')}, Fallback: {span.metadata.get('fallback_used')}"
            elif span.span_type == "gate":
                details = f"Triggers: {len(span.metadata.get('triggers', []))}"
            elif span.span_type == "decision":
                details = f"Outcome: {span.output}"

            status_style = "green" if span.status == "SUCCESS" else "red"
            table.add_row(
                span.name,
                span.span_type,
                f"{span.duration_ms:.1f}ms",
                f"[{status_style}]{span.status}[/{status_style}]",
                details
            )
        console.print(table)

    def export_trace_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "start_time": self.start_timestamp,
            "total_spans": len(self.spans),
            "spans": [s.to_dict() for s in self.spans]
        }

def record_engineer_gate_feedback(
    cluster_id: str,
    original_outcome: str,
    original_priority: Optional[str],
    engineer_action: str,  # "APPROVED", "EDITED", "REJECTED"
    final_outcome: str,
    final_priority: Optional[str],
    engineer_notes: str,
    cluster_context: Dict[str, Any],
    file_path: str = FEEDBACK_SPLIT_FILE
) -> Dict[str, Any]:
    """
    Saves human engineer gate interactions into feedback_split.jsonl
    for future tuning without contaminating the held-out test split (Section 5.1).
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    feedback_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "cluster_id": cluster_id,
        "original_outcome": original_outcome,
        "original_priority": original_priority,
        "engineer_action": engineer_action,
        "final_outcome": final_outcome,
        "final_priority": final_priority,
        "engineer_notes": engineer_notes,
        "cluster_context": cluster_context
    }

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(feedback_entry) + "\n")

    return feedback_entry
