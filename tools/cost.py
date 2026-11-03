from typing import Dict, Any, Optional

BASE_RATE_INR_PER_SQM = 1200.0   # BBMP-era patch rate
COST_GATE_INR = 25000.0          # Approval gate limit
UNCERTAINTY = 0.25               # +/-25% on the estimate

ROAD_CLASS_MULTIPLIERS = {
    "arterial": 1.25, 
    "sub_arterial": 1.15, 
    "collector": 1.00, 
    "local": 0.85,
}

DEPTH_BANDS = [
    (7.5, 1.35, "deep (over 75 mm)"),
    (5.0, 1.15, "medium (over 50 mm, up to 75 mm)"),
    (0.0, 1.00, "shallow (up to 50 mm)"),
]

def estimate_cost(
    area_m2: Optional[float] = 1.5,
    depth_cm: Optional[float] = 4.0,
    road_class: Optional[str] = "collector",
) -> Dict[str, Any]:
    # 1. Fallback defaults if citizen complaint did not specify physical dimensions
    safe_area = float(area_m2) if (area_m2 is not None and area_m2 > 0) else 1.5
    safe_depth = float(depth_cm) if (depth_cm is not None and depth_cm > 0) else 4.0
    rc = road_class.strip().lower() if road_class else "collector"
    road_mult = ROAD_CLASS_MULTIPLIERS.get(rc, 1.00)

    # 2. Depth band resolution
    depth_mult, depth_band = next(
        (m, label) for t, m, label in DEPTH_BANDS if safe_depth > t
    )

    # 3. Calculate estimate and +/-25% uncertainty range
    mid = safe_area * BASE_RATE_INR_PER_SQM * depth_mult * road_mult
    low = mid * (1 - UNCERTAINTY)
    high = mid * (1 + UNCERTAINTY)

    est_rounded = float(round(mid, -2))

    return {
        "status": "ok",
        "estimated_cost_inr": est_rounded,      # Required by existing agent/nodes.py & app.py
        "estimate_inr": est_rounded,            # Your preferred key
        "range_inr": (float(round(low, -2)), float(round(high, -2))),
        "area_m2": safe_area,
        "depth_cm": safe_depth,
        "depth_band": depth_band,
        "depth_multiplier": depth_mult,
        "road_class": rc,
        "road_class_multiplier": road_mult,
        "exceeds_cost_gate": high > COST_GATE_INR,  # Conservative: uses high end
        "cost_gate_limit_inr": COST_GATE_INR,
    }