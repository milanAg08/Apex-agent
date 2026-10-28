"""
Default Rule Table (Fallback Knowledge Base).
As specified in Design Document Section 3.4 & Section 2:
When agentic RAG retrieval confidence is below threshold after query rewriting,
the agent falls back gracefully to this frozen default rule table.
"""

from typing import Dict, Any

FALLBACK_RULES: Dict[str, Any] = {
    "defect_liability": {
        "source": "Default Municipal Fallback Rule Table (Sec 3.4)",
        "citation": "Fallback Rule Table: Resurfacing default liability period = 2.0 years",
        "liability_period_years": 2.0,
        "contractor_recurrence_obligation": True,
        "rule_id": "FALLBACK_DLP_001"
    },
    "severity_thresholds": {
        "source": "Default Municipal Fallback Rule Table (IRC:82 baseline)",
        "citation": "Fallback Rule Table: Baseline action threshold = 0.70 across road classes",
        "arterial": 0.65,
        "sub_arterial": 0.70,
        "collector": 0.75,
        "local": 0.85,
        "default_threshold": 0.70,
        "rule_id": "FALLBACK_SEV_001"
    },
    "response_times": {
        "source": "Default Municipal Fallback Rule Table (Service Charter)",
        "citation": "Fallback Rule Table: Standard municipal turnaround SLAs (P1 < 24h, P2 < 48h, P3 < 7d, P4 scheduled)",
        "p1_hours": 24,
        "p2_hours": 48,
        "p3_days": 7,
        "p4_days": 30,
        "rule_id": "FALLBACK_SLA_001"
    },
    "cost_parameters": {
        "source": "Default Municipal Fallback Rule Table (BBMP Schedule)",
        "citation": "Fallback Rule Table: Unit rate = 1,200 INR/m², Approval cost gate = 25,000 INR",
        "unit_rate_inr_sqm": 1200.0,
        "cost_gate_inr": 25000.0,
        "rule_id": "FALLBACK_COST_001"
    }
}

def get_fallback_rule(category: str) -> Dict[str, Any]:
    """Retrieve fallback rule configuration for a specific category."""
    return FALLBACK_RULES.get(category, {
        "source": "Default Fallback",
        "citation": "Generic Municipal Engineering Baseline Standard",
        "rule_id": "FALLBACK_GENERIC"
    })
