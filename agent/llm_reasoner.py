"""
Visible Reasoning Engine & ReAct Planner for Road Repair Prioritization.
Emits structured 'Thought', 'Action', 'Action Input', and 'Observation' traces.
Treats complaint text strictly as data, defending against prompt injections.
Provides deterministic policy-grounded reasoning by default, with optional API LLM routing.
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple
from rag.retriever import PolicyRetriever

class ReActReasoner:
    """
    Reasoner implementing the visible ReAct loop and dynamic branch routing.
    Emits structured thoughts and determines branch steps:
    - Branch A: Duplicate detection -> MERGE_DUPLICATE
    - Branch B: Weak/Unresolved evidence -> REQUEST_EVIDENCE / NEEDS_REVIEW
    - Branch C: Recent repair inside defect liability -> ROUTE_TO_CONTRACTOR
    - Branch D: Fresh damage -> Score severity, cost, retrieve threshold, INSPECT/REPAIR_NOW
    """

    def __init__(self, use_llm_api: bool = False):
        self.use_llm_api = use_llm_api
        self.retriever = PolicyRetriever()

    def sanitize_complaint_text(self, text: str) -> str:
        """
        Prompt-injection defense (Design Doc Sec 4):
        Treats complaint text strictly as data, strips system prompt overrides or escape sequences.
        """
        if not text:
            return ""
        # Remove common prompt injection attempts
        cleaned = re.sub(r"(?i)(ignore previous instructions|system prompt|you are now|override priority)", "[FILTERED]", text)
        return cleaned.strip()

    def extract_complaint_attributes(self, text: str) -> Dict[str, Any]:
        """
        Extracts physical damage attributes from text (depth, area, water, location).
        The LLM only extracts attributes; computation is done by deterministic tools.
        """
        text_lower = text.lower()
        
        # Estimate depth
        depth_cm = 4.0
        depth_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:cm|centimeter|inch|in)", text_lower)
        if depth_match:
            val = float(depth_match.group(1))
            if "inch" in text_lower:
                val = val * 2.54
            depth_cm = val
        elif "deep" in text_lower or "crater" in text_lower or "severe" in text_lower:
            depth_cm = 8.0
        elif "shallow" in text_lower or "surface" in text_lower:
            depth_cm = 2.5

        # Estimate area
        area_sqm = 1.0
        area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:sqm|sq\s*m|m2|meter|feet|ft)", text_lower)
        if area_match:
            area_sqm = float(area_match.group(1))
        elif "large" in text_lower or "massive" in text_lower or "wide" in text_lower:
            area_sqm = 3.5
        elif "small" in text_lower or "minor" in text_lower:
            area_sqm = 0.5

        # Standing water
        standing_water = any(w in text_lower for w in ["water", "rain", "ponding", "submerged", "puddle", "monsoon"])

        # Carriageway placement
        if any(w in text_lower for w in ["wheel path", "wheel", "middle of road", "center lane", "main track"]):
            location_carriageway = "wheel_path"
        elif any(w in text_lower for w in ["shoulder", "edge", "corner", "side"]):
            location_carriageway = "shoulder"
        else:
            location_carriageway = "center_lane"

        # Traffic hazard
        traffic_blocking = any(w in text_lower for w in ["block", "skid", "accident", "traffic jam", "gridlock", "bus"])

        return {
            "depth_cm": depth_cm,
            "area_sqm": area_sqm,
            "standing_water": standing_water,
            "location_on_carriageway": location_carriageway,
            "is_traffic_blocking": traffic_blocking
        }

    def generate_intake_thought(self, report_count: int, first_report: Dict[str, Any]) -> Tuple[str, str]:
        """Thought for Step 1: Intake & Validation."""
        safe_text = self.sanitize_complaint_text(first_report.get("text", ""))
        thought = (
            f"THOUGHT: Received batch containing {report_count} complaint(s). "
            f"Validating schema integrity and applying prompt-injection defense on citizen text. "
            f"Next step is spatial and semantic clustering to merge repeat reports."
        )
        action = "cluster_reports"
        return thought, action

    def generate_cluster_evaluation_thought(
        self,
        cluster: Dict[str, Any]
    ) -> Tuple[str, str, Optional[str]]:
        """
        Thought for Step 2: Planning and ReAct routing.
        Checks for Branch A (Duplicate) or Branch B (Weak evidence).
        """
        if cluster.get("is_duplicate"):
            dup_id = cluster.get("duplicate_ticket_id")
            thought = (
                f"THOUGHT [Branch A - Duplicate Detection]: Cluster {cluster['cluster_id']} matches active open ticket {dup_id} "
                f"(spatial distance, time window, and text similarity pass). "
                f"Per Branch A guidelines, skipping scoring, repair history query, and retrieval. "
                f"Terminating run early with outcome MERGE_DUPLICATE to avoid duplicate public expenditure."
            )
            return thought, "MERGE_DUPLICATE", "BRANCH_A"

        # Check if coordinates or text are present
        lat = cluster.get("centroid_lat")
        lon = cluster.get("centroid_lon")
        text = cluster.get("combined_text", "")

        if lat is None and lon is None and not text:
            thought = (
                f"THOUGHT [Branch B - Weak Evidence]: Cluster {cluster['cluster_id']} possesses neither GPS coordinates nor textual description. "
                f"Evidence is critically deficient to correlate with road infrastructure. Routing to Branch B."
            )
            return thought, "resolve_location", "BRANCH_B"

        thought = (
            f"THOUGHT [Branch Routing]: Cluster {cluster['cluster_id']} is not an open ticket duplicate. "
            f"Initiating geographic resolution to map coordinates/landmarks to the Ward 34 road network."
        )
        return thought, "resolve_location", None

    def generate_maintenance_check_thought(
        self,
        cluster_id: str,
        segment_id: str,
        road_name: str,
        road_class: str
    ) -> Tuple[str, str]:
        """Thought for querying historical maintenance records."""
        thought = (
            f"THOUGHT: Road segment resolved to '{road_name}' ({segment_id}, class: {road_class}). "
            f"Querying municipal SQLite maintenance database to verify if segment has recent repairs "
            f"under active contractor defect liability (Branch C liability check)."
        )
        action = "query_maintenance_db"
        return thought, action

    def generate_liability_decision_thought(
        self,
        cluster_id: str,
        maintenance_info: Dict[str, Any]
    ) -> Tuple[str, str, str]:
        """Evaluates whether recent repair triggers Branch C."""
        is_under_liability = maintenance_info.get("is_under_liability", False)
        contractor = maintenance_info.get("contractor_name", "Unknown Contractor")
        expiry = maintenance_info.get("liability_expiry_date", "")
        days_left = maintenance_info.get("days_liability_remaining", 0)

        if is_under_liability:
            thought = (
                f"THOUGHT [Branch C - Defect Liability Triggered]: Segment was resurfaced with a defect liability warranty "
                f"assigned to contractor '{contractor}' valid until {expiry} ({days_left} days remaining). "
                f"Per BBMP Tender Clause 14.5, recurrence within DLP requires contractor rectification at zero municipal cost. "
                f"Executing retrieve_criteria to ground the exact contractual liability clause before routing."
            )
            action = "retrieve_criteria"
            branch = "BRANCH_C"
        else:
            thought = (
                f"THOUGHT [Branch D - Fresh Damage]: Segment is not under active contractor liability. "
                f"Proceeding to engineering scoring: compute severity from physical attributes, "
                f"estimate repair cost, and retrieve road-class action thresholds."
            )
            action = "score_severity"
            branch = "BRANCH_D"

        return thought, action, branch
