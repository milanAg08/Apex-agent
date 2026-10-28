"""
Policy Corpus for Road Maintenance and Defect Liability.
Grounds the agent in:
1. IRC:82 (Code of Practice for Maintenance of Bituminous Surfaces of Highways)
2. BBMP Tender Conditions on Defect Liability (2021)
3. Greater Bengaluru Authority (GBA) Response-Time Guidelines
"""

from typing import List, Dict, Any

POLICY_CHUNKS: List[Dict[str, Any]] = [
    {
        "chunk_id": "BBMP_DLP_001",
        "doc_name": "BBMP Tender Conditions on Defect Liability (2021)",
        "clause": "Clause 14.2: Defect Liability Period (DLP) Durations",
        "category": "defect_liability",
        "text": (
            "Clause 14.2 Defect Liability Durations: For all asphalt and road surfacing works "
            "undertaken under municipal contracts: (a) 3 (three) years for bituminous layers with "
            "compacted thickness greater than 40 mm (including Dense Bituminous Macadam and Bituminous Concrete overlays); "
            "(b) 2 (two) years for bituminous surfacing layers under 40 mm thickness (including premix carpet and surface dressing); "
            "(c) 1 (one) year for standalone civil masonry and kerb works. The defect liability period starts strictly from the date "
            "of the final bill / completion certificate."
        ),
        "keywords": ["defect liability", "liability period", "3 years", "2 years", "40 mm", "bituminous", "contractor"]
    },
    {
        "chunk_id": "BBMP_DLP_002",
        "doc_name": "BBMP Tender Conditions on Defect Liability (2021)",
        "clause": "Clause 14.5: Contractor Recurrence Obligation and Routing",
        "category": "contractor_recurrence",
        "text": (
            "Clause 14.5 Recurrence of Damage in DLP: If any pothole, unraveling, rutting, or pavement depression occurs "
            "on the road segment within the operative defect liability period, the assigned contractor is contractually bound "
            "to execute rectifications at zero cost to the municipal corporation. The ward engineer must route the defect notice "
            "directly to the contractor (ROUTE_TO_CONTRACTOR). Fresh civic repair tenders or departmental cash outflows shall not "
            "be sanctioned for segments covered by an active defect liability warranty."
        ),
        "keywords": ["route to contractor", "contractor liability", "recurrence", "zero cost", "warranty", "active defect liability"]
    },
    {
        "chunk_id": "IRC82_SEV_001",
        "doc_name": "IRC:82 Maintenance of Bituminous Surfaces",
        "clause": "Section 4.3: Severity Classification Criteria",
        "category": "severity_threshold",
        "text": (
            "IRC:82 Section 4.3 Pothole Severity Grading: Potholes shall be assessed based on depth, surface area, water ponding, "
            "and carriageway lateral placement: Low Severity (score < 0.40): depth < 25 mm, area < 0.1 m², dry surface; "
            "Medium Severity (score 0.40 - 0.65): depth 25 mm to 50 mm, area 0.1 to 0.5 m², occasional water; "
            "High / Critical Severity (score > 0.65): depth > 50 mm, area > 0.5 m², active standing water, or located on primary wheel path. "
            "Any pothole exceeding 75 mm depth on arterial carriageways represents an acute vehicular stability hazard."
        ),
        "keywords": ["severity", "depth", "water", "wheel path", "high severity", "irc:82", "depth > 50 mm"]
    },
    {
        "chunk_id": "IRC82_ROAD_THRESH_001",
        "doc_name": "IRC:82 / BBMP Road Class Severity Action Thresholds",
        "clause": "Section 5.1: Thresholds Separating INSPECT from REPAIR_NOW",
        "category": "action_thresholds",
        "text": (
            "Section 5.1 Action Thresholds by Road Class: The decision boundary between advisory field inspection (INSPECT) "
            "and immediate repair dispatch (REPAIR_NOW) is calibrated by functional road classification: "
            "1. Arterial Roads (c_road = 1.30): Severity threshold >= 0.65 triggers REPAIR_NOW; below 0.65 triggers INSPECT. "
            "2. Sub-Arterial Roads (c_road = 1.15): Severity threshold >= 0.70 triggers REPAIR_NOW; below 0.70 triggers INSPECT. "
            "3. Collector Roads (c_road = 1.00): Severity threshold >= 0.75 triggers REPAIR_NOW; below 0.75 triggers INSPECT. "
            "4. Local Residential Streets / Lanes (c_road = 0.85): Severity threshold >= 0.85 triggers REPAIR_NOW; below 0.85 triggers INSPECT."
        ),
        "keywords": ["action threshold", "road class", "arterial", "sub-arterial", "collector", "local", "inspect", "repair_now", "0.65", "0.75"]
    },
    {
        "chunk_id": "GBA_RESP_001",
        "doc_name": "Greater Bengaluru Authority Service Standards (2024-2026)",
        "clause": "Standard 7.2: Response Time and Priority Bands",
        "category": "response_times",
        "text": (
            "Standard 7.2 Response-Time Requirements for Pothole Redressal: "
            "Priority P1 (Score >= 0.80): Emergency resolution within 24 hours. Mandatory engineer sign-off gate before dispatch. "
            "Priority P2 (0.60 <= Score < 0.80): Urgent redressal within 48 hours. "
            "Priority P3 (0.40 <= Score < 0.60): Standard routine maintenance batching within 7 days. "
            "Priority P4 (Score < 0.40): Deferred or scheduled cyclic surface renewal within 30 days."
        ),
        "keywords": ["response time", "p1", "p2", "p3", "p4", "24 hours", "48 hours", "7 days", "priority"]
    },
    {
        "chunk_id": "COST_SPEC_001",
        "doc_name": "BBMP Schedule of Rates (Pavement Maintenance)",
        "clause": "Item 18.4: Unit Rates for Pothole Patching & Cost Gates",
        "category": "cost_specification",
        "text": (
            "Item 18.4 Unit Patching Rate: The standard municipal unit rate for cold-mix or hot-mix bituminous patching is "
            "pegged at 1,200 Indian Rupees (INR) per square meter of patch area (base thickness up to 50 mm). "
            "For deep craters (>75 mm) requiring Granular Sub-Base (GSB) levelling, a depth multiplier of 1.35 applies. "
            "Engineer Cost Gate: Any repair cluster with estimated patch expenditure exceeding 25,000 INR (approx 20 m² at baseline rate) "
            "shall not be automatically dispatched and must be paused at the approval gate for Assistant Executive Engineer (AEE) sign-off."
        ),
        "keywords": ["unit rate", "1200", "cost gate", "25000", "patching rate", "rupees per m2"]
    }
]
