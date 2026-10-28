"""
Tool 5: estimate_cost
Calculates rough repair expenditure from cluster patch area (m²), depth (cm), and road class.
Flags if total estimated cost exceeds the 25,000 INR approval gate threshold.
"""

from typing import Dict, Any, Optional

BASE_UNIT_RATE_INR_PER_SQM = 1200.0
APPROVAL_GATE_COST_LIMIT_INR = 25000.0

ROAD_CLASS_MULTIPLIERS = {
    "arterial": 1.25,
    "sub_arterial": 1.15,
    "collector": 1.00,
    "local": 0.85
}

def estimate_cost(
    area_m2: float = 1.5,
    depth_cm: float = 4.0,
    road_class: str = "collector",
    base_rate: float = BASE_UNIT_RATE_INR_PER_SQM
) -> Dict[str, Any]:
    """
    Computes patch cost based on engineering parameters.
    """
    safe_area = max(0.2, float(area_m2))
    safe_depth = max(1.0, float(depth_cm))
    rc = road_class.lower() if road_class else "collector"

    # Depth multiplier
    if safe_depth > 7.5:
        depth_multiplier = 1.35
        depth_spec = "Deep crater (>75mm), GSB course required"
    elif safe_depth > 5.0:
        depth_multiplier = 1.15
        depth_spec = "Medium depth (50-75mm), Tack coat and leveling required"
    else:
        depth_multiplier = 1.00
        depth_spec = "Standard surface patch (<50mm)"

    road_multiplier = ROAD_CLASS_MULTIPLIERS.get(rc, 1.00)

    # Unit rate with multipliers
    effective_unit_rate = base_rate * depth_multiplier * road_multiplier
    total_cost = round(safe_area * effective_unit_rate, 2)

    exceeds_cost_gate = total_cost > APPROVAL_GATE_COST_LIMIT_INR

    return {
        "estimated_cost_inr": total_cost,
        "base_unit_rate_inr": base_rate,
        "effective_unit_rate_inr": round(effective_unit_rate, 2),
        "area_m2": safe_area,
        "depth_cm": safe_depth,
        "depth_multiplier": depth_multiplier,
        "depth_specification": depth_spec,
        "road_class_multiplier": road_multiplier,
        "exceeds_cost_gate": exceeds_cost_gate,
        "cost_gate_limit_inr": APPROVAL_GATE_COST_LIMIT_INR
    }
