"""
Tool 4: query_maintenance_db
Queries the municipal SQLite maintenance database for road segment repair history,
contractor, paving thickness, defect liability validity, and traffic index.
"""

import sqlite3
import os
from typing import Dict, Any, Optional
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "maintenance_db.sqlite")

def query_maintenance_db(segment_id: str, current_date_str: str = "2026-10-26") -> Dict[str, Any]:
    """
    Retrieves segment maintenance records, contractor warranty, and liability status.
    """
    if not os.path.exists(DB_PATH):
        return {"status": "ERROR", "message": f"Database file not found at {DB_PATH}"}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Query segment properties
    cur.execute("""
    SELECT segment_id, name, road_class, traffic_index, last_repair_date,
           contractor_name, layer_thickness_mm, liability_period_years,
           liability_expiry_date, repair_history_risk, unit_rate_multiplier
    FROM segments WHERE segment_id = ?;
    """, (segment_id,))
    seg_row = cur.fetchone()

    if not seg_row:
        conn.close()
        return {
            "status": "NOT_FOUND",
            "segment_id": segment_id,
            "message": f"Segment {segment_id} not registered in municipal registry"
        }

    # Query historical repairs
    cur.execute("""
    SELECT record_id, repair_date, contractor_name, scope_description,
           cost_inr, layer_thickness_mm, defect_liability_years, defect_liability_end_date
    FROM repair_records WHERE segment_id = ?
    ORDER BY repair_date DESC;
    """, (segment_id,))
    repairs = cur.fetchall()
    conn.close()

    # Evaluate Defect Liability Status
    last_repair_date = seg_row[4]
    contractor = seg_row[5]
    layer_thickness = seg_row[6]
    liability_years = seg_row[7]
    liability_expiry = seg_row[8]
    traffic_index = seg_row[3]
    repair_risk = seg_row[9]

    is_under_liability = False
    days_remaining = 0

    if liability_expiry:
        try:
            curr_dt = datetime.fromisoformat(current_date_str.split("T")[0])
            exp_dt = datetime.fromisoformat(liability_expiry.split("T")[0])
            if exp_dt > curr_dt:
                is_under_liability = True
                days_remaining = (exp_dt - curr_dt).days
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "segment_id": seg_row[0],
        "name": seg_row[1],
        "road_class": seg_row[2],
        "traffic_index": traffic_index,
        "repair_history_risk": repair_risk,
        "last_repair_date": last_repair_date,
        "contractor_name": contractor,
        "layer_thickness_mm": layer_thickness,
        "liability_period_years": liability_years,
        "liability_expiry_date": liability_expiry,
        "is_under_liability": is_under_liability,
        "days_liability_remaining": days_remaining,
        "history_records_count": len(repairs),
        "past_repairs": [
            {
                "record_id": r[0],
                "repair_date": r[1],
                "contractor": r[2],
                "scope": r[3],
                "cost_inr": r[4],
                "thickness_mm": r[5],
                "warranty_end": r[7]
            }
            for r in repairs
        ]
    }
