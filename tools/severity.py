"""
Tool 3: score_severity
Calculates deterministic rule-based severity from 0.0 to 1.0 using extracted
engineering attributes (depth, area, standing water, and location on carriageway).
The LLM extracts attributes; the tool computes the numeric score.
"""

from typing import Dict, Any, Optional

def score_severity(
    depth_cm: Optional[float] = None,
    area_sqm: Optional[float] = None,
    standing_water: bool = False,
    location_on_carriageway: str = "wheel_path",
    is_traffic_blocking: bool = False
) -> Dict[str, Any]:
    """
    Computes severity score according to IRC:82 guidelines.
    Formula:
      Depth Factor (D) = min(1.0, depth_cm / 10.0)   [40% weight]
      Area Factor (A)  = min(1.0, area_sqm / 3.0)    [30% weight]
      Water Ponding (W)= 0.20 if True, else 0.0      [Bonus hazard]
      Carriageway (L)  = 0.20 if wheel_path, 0.15 if center, 0.05 if shoulder
    """
    # Reasonable defaults if not provided in raw report
    d = float(depth_cm) if depth_cm is not None else 4.0
    a = float(area_sqm) if area_sqm is not None else 0.8
    loc = location_on_carriageway.lower() if location_on_carriageway else "wheel_path"

    # Normalized components
    d_norm = min(1.0, max(0.0, d / 10.0))
    a_norm = min(1.0, max(0.0, a / 3.0))
    w_factor = 0.20 if standing_water else 0.0

    # IRC:82 Sec 4.3 rule: depth > 50mm (5cm) constitutes high severity threshold
    depth_hazard_bonus = 0.15 if d >= 5.0 else 0.0

    if "wheel" in loc or "path" in loc:
        l_factor = 0.20
    elif "center" in loc or "middle" in loc or "lane" in loc:
        l_factor = 0.15
    elif "shoulder" in loc or "edge" in loc:
        l_factor = 0.08
    else:
        l_factor = 0.05

    raw_score = (0.40 * d_norm) + (0.30 * a_norm) + w_factor + l_factor + depth_hazard_bonus
    if is_traffic_blocking:
        raw_score += 0.10

    final_score = min(1.0, max(0.0, raw_score))

    # Determine severity label
    if final_score >= 0.75:
        grade = "CRITICAL"
    elif final_score >= 0.60:
        grade = "HIGH"
    elif final_score >= 0.40:
        grade = "MEDIUM"
    else:
        grade = "LOW"

    return {
        "severity_score": round(final_score, 3),
        "grade": grade,
        "attributes": {
            "depth_cm": d,
            "area_sqm": a,
            "standing_water": standing_water,
            "carriageway_location": loc,
            "traffic_blocking": is_traffic_blocking
        },
        "formula_breakdown": {
            "depth_contribution": round(0.40 * d_norm, 3),
            "area_contribution": round(0.30 * a_norm, 3),
            "water_bonus": w_factor,
            "location_bonus": l_factor
        }
    }
