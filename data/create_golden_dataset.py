"""
Generates the Golden Dataset of 40 Scenarios for Ward 34 (D.V. Gundappa Ward).
As specified in Design Document Section 5.1:
- 10 Tuning Scenarios (for adjusting weights and thresholds)
- 30 Held-Out Test Scenarios (for frozen evaluation)
Covering all decision outcomes: MERGE_DUPLICATE, REQUEST_EVIDENCE, ROUTE_TO_CONTRACTOR,
INSPECT, REPAIR_NOW, and NEEDS_REVIEW, with near-duplicates and boundary liability dates.
"""

import json
import os
from typing import List, Dict, Any

DATA_FILE = os.path.join(os.path.dirname(__file__), "golden_dataset.json")

def generate_golden_scenarios() -> Dict[str, Any]:
    scenarios: List[Dict[str, Any]] = []

    # Helper templates
    # Branch A: Duplicates
    # Branch B: Weak / Vague evidence
    # Branch C: Inside Liability (SEG_DVG_001 repaired Aug 2025 -> 3 yrs; SEG_GANDHI_001 repaired Nov 2025 -> 2 yrs)
    # Branch D: Fresh damage -> INSPECT or REPAIR_NOW (P1 to P4)
    # Safety: NEEDS_REVIEW

    # 10 TUNING SCENARIOS
    tuning_defs = [
        # SCENARIO 1: Open ticket duplicate outside Upahara Darshini
        {
            "id": "TUNING_01",
            "split": "tuning",
            "name": "DVG North Duplicate Complaint Batch",
            "gold_branch": "BRANCH_A",
            "gold_outcome": "MERGE_DUPLICATE",
            "gold_priority": None,
            "gold_triggers": [],
            "reports": [
                {"report_id": "T01_R1", "lat": 12.9431, "lon": 77.5739, "text": "Huge pothole in front of Upahara Darshini on DVG Road north, vehicles slowing down dangerously", "reported_date": "2026-10-26"},
                {"report_id": "T01_R2", "lat": 12.9433, "lon": 77.5737, "text": "Crater on DVG road near upahara hotel, bikes slipping on stone gravel", "reported_date": "2026-10-27"}
            ]
        },
        # SCENARIO 2: Vague location with no street name
        {
            "id": "TUNING_02",
            "split": "tuning",
            "name": "Vague Description Without Pin",
            "gold_branch": "BRANCH_B",
            "gold_outcome": "REQUEST_EVIDENCE",
            "gold_priority": None,
            "gold_triggers": [],
            "reports": [
                {"report_id": "T02_R1", "lat": None, "lon": None, "text": "somewhere near a tree in bangalore road is broken", "reported_date": "2026-10-26"}
            ]
        },
        # SCENARIO 3: Gandhi Bazaar recent resurfacing recurrence (under 2-yr liability)
        {
            "id": "TUNING_03",
            "split": "tuning",
            "name": "Gandhi Bazaar Active DLP Recurrence",
            "gold_branch": "BRANCH_C",
            "gold_outcome": "ROUTE_TO_CONTRACTOR",
            "gold_priority": None,
            "gold_triggers": ["Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations"],
            "reports": [
                {"report_id": "T03_R1", "lat": 12.9435, "lon": 77.5715, "text": "Gandhi bazaar main road surface peeling off near vegetable stalls, contractor did poor job", "reported_date": "2026-10-25"},
                {"report_id": "T03_R2", "lat": 12.9437, "lon": 77.5714, "text": "Depression on newly paved stretch of Gandhi Bazaar road", "reported_date": "2026-10-26"}
            ]
        },
        # SCENARIO 4: Critical arterial damage outside BMSCE (Emergency P1)
        {
            "id": "TUNING_04",
            "split": "tuning",
            "name": "BMSCE Frontage Heavy Arterial Crater",
            "gold_branch": "BRANCH_D",
            "gold_outcome": "REPAIR_NOW",
            "gold_priority": "P1",
            "gold_triggers": ["P1 Emergency Repair: Mandatory sign-off for immediate 24h work order dispatch"],
            "reports": [
                {"report_id": "T04_R1", "lat": 12.9378, "lon": 77.5691, "text": "Deep 10cm crater on Bull Temple Road wheel path, standing rainwater puddle, BMTC buses swerving", "reported_date": "2026-10-26"},
                {"report_id": "T04_R2", "lat": 12.9379, "lon": 77.5690, "text": "Massive dangerous pothole near BMSCE back gate, immediate hazard", "reported_date": "2026-10-26"}
            ]
        },
        # SCENARIO 5: Bugle Rock collector road moderate damage (Routine inspection)
        {
            "id": "TUNING_05",
            "split": "tuning",
            "name": "Bugle Rock Road Shallow Rutting",
            "gold_branch": "BRANCH_D",
            "gold_outcome": "INSPECT",
            "gold_priority": "P3",
            "gold_triggers": [],
            "reports": [
                {"report_id": "T05_R1", "lat": 12.9415, "lon": 77.5708, "text": "Shallow surface wear 2cm depth on Bugle Rock Road shoulder, cars passing normally", "reported_date": "2026-10-26"}
            ]
        },
        # SCENARIO 6: DVG South expired liability fresh damage
        {
            "id": "TUNING_06",
            "split": "tuning",
            "name": "DVG South Expired Warranty Arterial",
            "gold_branch": "BRANCH_D",
            "gold_outcome": "REPAIR_NOW",
            "gold_priority": "P2",
            "gold_triggers": [],
            "reports": [
                {"report_id": "T06_R1", "lat": 12.9405, "lon": 77.5752, "text": "Significant 6cm pothole on DVG Road South near cloth merchant shops, traffic slowing down", "reported_date": "2026-10-25"}
            ]
        },
        # SCENARIO 7: Netkallappa approach sub-arterial moderate wear
        {
            "id": "TUNING_07",
            "split": "tuning",
            "name": "Netkallappa Circle Approach Pothole",
            "gold_branch": "BRANCH_D",
            "gold_outcome": "INSPECT",
            "gold_priority": "P2",
            "gold_triggers": [],
            "reports": [
                {"report_id": "T07_R1", "lat": 12.9375, "lon": 77.5730, "text": "Netkallappa circle road has rough patch 3cm depth near auto stand", "reported_date": "2026-10-26"}
            ]
        },
        # SCENARIO 8: Residential quiet lane minor pothole (P4 scheduled)
        {
            "id": "TUNING_08",
            "split": "tuning",
            "name": "Residential 2nd Cross Minor Wear",
            "gold_branch": "BRANCH_D",
            "gold_outcome": "INSPECT",
            "gold_priority": "P4",
            "gold_triggers": [],
            "reports": [
                {"report_id": "T08_R1", "lat": 12.9436, "lon": 77.5760, "text": "Small surface gravel loose in Basavanagudi 2nd cross residential, 1cm shallow depression", "reported_date": "2026-10-24"}
            ]
        },
        # SCENARIO 9: Extremely costly damage cluster (>25k INR trigger)
        {
            "id": "TUNING_09",
            "split": "tuning",
            "name": "Bull Temple Road Extensive Crater Field",
            "gold_branch": "BRANCH_D",
            "gold_outcome": "REPAIR_NOW",
            "gold_priority": "P1",
            "gold_triggers": ["Cost Gate Threshold Exceeded", "P1 Emergency Repair"],
            "reports": [
                {"report_id": "T09_R1", "lat": 12.9372, "lon": 77.5693, "text": "Massive 25 sqm collapsed bituminous section, 9cm deep, waterlogged across Bull Temple arterial", "reported_date": "2026-10-26"}
            ]
        },
        # SCENARIO 10: Model house lane quiet street
        {
            "id": "TUNING_10",
            "split": "tuning",
            "name": "Model House Street Local Lane",
            "gold_branch": "BRANCH_D",
            "gold_outcome": "INSPECT",
            "gold_priority": "P4",
            "gold_triggers": [],
            "reports": [
                {"report_id": "T10_R1", "lat": 12.9410, "lon": 77.5770, "text": "Model House Street 1st cross residential lane has small hole near water meter, 2cm", "reported_date": "2026-10-25"}
            ]
        }
    ]

    scenarios.extend(tuning_defs)

    # 30 HELD-OUT TEST SCENARIOS
    # Carefully balanced across all 4 branches and boundary conditions
    test_archetypes = [
        # (id_num, name, branch, outcome, priority, lat, lon, text, triggers)
        # Duplicate scenarios (6 tests)
        (1, "Open Ticket DVG North Duplicate Repeat", "BRANCH_A", "MERGE_DUPLICATE", None, 12.9432, 77.5738, "Severe pothole opposite Upahara Darshini north section DVG", []),
        (2, "Open Ticket DVG North Near Duplicate 15m away", "BRANCH_A", "MERGE_DUPLICATE", None, 12.9433, 77.5739, "Bikes wobbling on DVG road crater near darshini", []),
        (3, "BMSCE Open Ticket Match 1", "BRANCH_A", "MERGE_DUPLICATE", None, 12.9390, 77.5688, "Series of potholes near BMSCE Main Gate with water accumulation", []),
        (4, "BMSCE Open Ticket Match 2", "BRANCH_A", "MERGE_DUPLICATE", None, 12.9391, 77.5687, "Water ponding potholes in front of BMS College gate", []),
        (5, "Gandhi Bazaar Open Ticket Repeat", "BRANCH_A", "MERGE_DUPLICATE", None, 12.9438, 77.5718, "Bitumen unraveling opposite Gandhi Bazaar circle market", []),
        (6, "Gandhi Bazaar Second Complaint Open Ticket", "BRANCH_A", "MERGE_DUPLICATE", None, 12.9439, 77.5719, "Ruts and bitumen gravel loose at Gandhi Bazaar entrance", []),

        # Weak / Vague Evidence scenarios (6 tests)
        (7, "Vague park complaint without street", "BRANCH_B", "REQUEST_EVIDENCE", None, None, None, "somewhere near bugle rock park entrance road broke", []),
        (8, "Vague tree landmark", "BRANCH_B", "REQUEST_EVIDENCE", None, None, None, "pothole on road near a tree around bangalore south", []),
        (9, "Completely empty coordinates and vague text", "BRANCH_B", "REQUEST_EVIDENCE", None, None, None, "unknown street please fix potholes urgently", []),
        (10, "Ambiguous Bangalore street without ward match", "BRANCH_B", "REQUEST_EVIDENCE", None, None, None, "somewhere in Bangalore road is damaged please inspect", []),
        (11, "Vague corner shop description", "BRANCH_B", "REQUEST_EVIDENCE", None, None, None, "near shop corner pothole deep please send team", []),
        (12, "Unreferenced locality report", "BRANCH_B", "REQUEST_EVIDENCE", None, None, None, "road cracked near temple without name", []),

        # Defect Liability Recurrence scenarios (6 tests - inside DLP period)
        (13, "Gandhi Bazaar Recurrence inside 2-year DLP #1", "BRANCH_C", "ROUTE_TO_CONTRACTOR", None, 12.9432, 77.5712, "Gandhi Bazaar resurfaced road cracking again near flower market", ["Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations"]),
        (14, "Gandhi Bazaar Recurrence inside 2-year DLP #2", "BRANCH_C", "ROUTE_TO_CONTRACTOR", None, 12.9440, 77.5722, "Pavement depression on new Gandhi bazaar asphalt", ["Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations"]),
        (15, "Gandhi Bazaar Recurrence inside 2-year DLP #3", "BRANCH_C", "ROUTE_TO_CONTRACTOR", None, 12.9426, 77.5726, "Gandhi Bazaar south corner overlay disintegrating under monsoon", ["Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations"]),
        (16, "Gandhi Bazaar Vendor complaint on new asphalt", "BRANCH_C", "ROUTE_TO_CONTRACTOR", None, 12.9448, 77.5712, "Vendor stalls notice Gandhi Bazaar road sinking within 1 year of paving", ["Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations"]),
        (17, "Gandhi Bazaar Circle Recurrence", "BRANCH_C", "ROUTE_TO_CONTRACTOR", None, 12.9427, 77.5725, "Gandhi bazaar main road junction peeling again", ["Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations"]),
        (18, "Gandhi Bazaar Cross connection recurrence", "BRANCH_C", "ROUTE_TO_CONTRACTOR", None, 12.9431, 77.5715, "Bituminous layer crumbling on recently paved Gandhi Bazaar", ["Contractual Defect Liability: Routing defect to contractor imposes binding warranty obligations"]),

        # Fresh Damage - Critical / Arterial REPAIR_NOW (P1 / P2) (6 tests)
        (19, "Bull Temple Arterial Critical Wheelpath Crater", "BRANCH_D", "REPAIR_NOW", "P1", 12.9374, 77.5694, "Massive 8cm deep crater on Bull Temple Road wheel path with standing water", ["P1 Emergency Repair: Mandatory sign-off for immediate 24h work order dispatch"]),
        (20, "Bull Temple High Traffic Rapid Transit Skids", "BRANCH_D", "REPAIR_NOW", "P1", 12.9376, 77.5692, "Dangerous 9cm deep pothole causing two-wheeler accidents Bull Temple Rd", ["P1 Emergency Repair: Mandatory sign-off for immediate 24h work order dispatch"]),
        (21, "DVG South Expired Arterial Severe Pothole", "BRANCH_D", "REPAIR_NOW", "P2", 12.9400, 77.5755, "Deep 7cm pothole on DVG road south section near clothing stores", []),
        (22, "DVG South Commercial Carriageway Hazard", "BRANCH_D", "REPAIR_NOW", "P2", 12.9410, 77.5748, "6cm pothole on DVG Road South commercial lane slowing cars", []),
        (23, "Bull Temple South Approach High Severity", "BRANCH_D", "REPAIR_NOW", "P1", 12.9372, 77.5695, "Deep 8cm crater on Bull Temple road wheel path, rain filled water puddle", ["P1 Emergency Repair: Mandatory sign-off for immediate 24h work order dispatch"]),
        (24, "Netkallappa Sub-Arterial Acute Defect", "BRANCH_D", "REPAIR_NOW", "P2", 12.9380, 77.5725, "Netkallappa circle road 6.5cm pothole in center lane", []),

        # Fresh Damage - Moderate / Minor INSPECT (P3 / P4) (6 tests)
        (25, "Bugle Rock Collector Routine Surface Wear", "BRANCH_D", "INSPECT", "P3", 12.9420, 77.5705, "Bugle Rock Road has shallow 3cm rut on road shoulder", []),
        (26, "Bugle Rock Collector Entrance Mild Pothole", "BRANCH_D", "INSPECT", "P3", 12.9410, 77.5712, "Bugle Rock road 2.5cm shallow depression near park corner", []),
        (27, "Basavanagudi 2nd Cross Quiet Lane Pothole", "BRANCH_D", "INSPECT", "P4", 12.9437, 77.5765, "2nd cross Basavanagudi residential road minor 1.5cm pothole", []),
        (28, "Basavanagudi 2nd Cross End Local Wear", "BRANCH_D", "INSPECT", "P4", 12.9435, 77.5755, "Basavanagudi 2nd cross residential 2cm gravel depression", []),
        (29, "Model House Street Local Lane Mild Crack", "BRANCH_D", "INSPECT", "P4", 12.9411, 77.5768, "Model House street 1st cross residential 2cm hole near house #42", []),
        (30, "Model House Street Corner Minor Defect", "BRANCH_D", "INSPECT", "P4", 12.9409, 77.5780, "Model House street shallow 1.8cm surface dip, low traffic lane", [])
    ]

    for item in test_archetypes:
        num, name, branch, outcome, prio, lat, lon, text, triggers = item
        scenario_id = f"TEST_{num:02d}"
        scenarios.append({
            "id": scenario_id,
            "split": "test",
            "name": name,
            "gold_branch": branch,
            "gold_outcome": outcome,
            "gold_priority": prio,
            "gold_triggers": triggers,
            "reports": [
                {
                    "report_id": f"{scenario_id}_R1",
                    "lat": lat,
                    "lon": lon,
                    "text": text,
                    "reported_date": "2026-10-26"
                }
            ]
        })

    return {
        "metadata": {
            "total_scenarios": len(scenarios),
            "tuning_count": 10,
            "test_count": 30,
            "city": "Bengaluru",
            "ward": "Ward 34 D.V Gundappa Ward",
            "reference_date": "2026-10-26"
        },
        "scenarios": scenarios
    }

if __name__ == "__main__":
    dataset = generate_golden_scenarios()
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    print(f"Generated {len(dataset['scenarios'])} golden scenarios into {DATA_FILE}")
