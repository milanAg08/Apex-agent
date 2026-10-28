"""
Priority Formula Implementation (Design Document Section 3.2).
For INSPECT and REPAIR_NOW:
P = c_road * (w_s * S + w_t * T + w_h * H + w_r * R), with w_s + w_t + w_h + w_r = 1
Maps priority score to P1, P2, P3, P4 bands.
"""

from typing import Dict, Any, Tuple

DEFAULT_WEIGHTS = {
    "w_s": 0.40,  # Severity weight
    "w_t": 0.30,  # Traffic weight
    "w_h": 0.15,  # Repair history risk weight
    "w_r": 0.15   # Report volume weight
}

ROAD_CLASS_C_FACTORS = {
    "arterial": 1.30,
    "sub_arterial": 1.15,
    "collector": 1.00,
    "local": 0.85
}

def calculate_priority_score(
    severity: float,
    traffic_index: float,
    repair_history_risk: float,
    report_count: int = 1,
    road_class: str = "collector",
    weights: Dict[str, float] = DEFAULT_WEIGHTS
) -> Dict[str, Any]:
    """
    Computes numeric priority P and maps it to priority level P1..P4.
    """
    s = min(1.0, max(0.0, float(severity)))
    t = min(1.0, max(0.0, float(traffic_index)))
    h = min(1.0, max(0.0, float(repair_history_risk)))
    # Normalize report count: 1 report -> 0.20, 5+ reports -> 1.0
    r = min(1.0, max(0.0, report_count / 5.0))

    rc = road_class.lower() if road_class else "collector"
    c_road = ROAD_CLASS_C_FACTORS.get(rc, 1.00)

    w_s = weights.get("w_s", 0.40)
    w_t = weights.get("w_t", 0.30)
    w_h = weights.get("w_h", 0.15)
    w_r = weights.get("w_r", 0.15)

    weighted_inner = (w_s * s) + (w_t * t) + (w_h * h) + (w_r * r)
    raw_p = c_road * weighted_inner
    final_score = min(1.0, max(0.0, raw_p))

    # Priority banding
    if final_score >= 0.80:
        priority_level = "P1"
        response_time = "Within 24 hours (Immediate / Emergency)"
    elif final_score >= 0.60:
        priority_level = "P2"
        response_time = "Within 48 hours (Urgent redressal)"
    elif final_score >= 0.40:
        priority_level = "P3"
        response_time = "Within 7 days (Routine maintenance)"
    else:
        priority_level = "P4"
        response_time = "Within 30 days (Scheduled cyclic maintenance)"

    return {
        "priority_score": round(final_score, 4),
        "priority_level": priority_level,
        "response_time_sla": response_time,
        "c_road": c_road,
        "inputs": {
            "severity_S": s,
            "traffic_T": t,
            "history_risk_H": h,
            "report_volume_R": r,
            "report_count": report_count,
            "road_class": rc
        },
        "weights": {
            "w_s": w_s,
            "w_t": w_t,
            "w_h": w_h,
            "w_r": w_r
        }
    }
