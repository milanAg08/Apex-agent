"""
Visible Reasoning Engine & ReAct Planner for Road Repair Prioritization.
Emits structured 'Thought', 'Action', 'Action Input', and 'Observation' traces.
Treats complaint text strictly as data, defending against prompt injections.
Provides a dual-mode system:
1. 100% Offline Deterministic Rule-Based Engine (Default, fast, zero cost).
2. Live Multi-Provider Agentic LLM (Google Gemini, OpenAI, Anthropic via API keys).
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
load_dotenv()

logger = logging.getLogger("APEX.ReActReasoner")

class ReActReasoner:
    """
    Reasoner implementing the visible ReAct loop and dynamic branch routing.
    Emits structured thoughts and determines branch steps:
    - Branch A: Duplicate detection -> MERGE_DUPLICATE
    - Branch B: Weak/Unresolved evidence -> REQUEST_EVIDENCE / NEEDS_REVIEW
    - Branch C: Recent repair inside defect liability -> ROUTE_TO_CONTRACTOR
    - Branch D: Fresh damage -> Score severity, cost, retrieve threshold, INSPECT/REPAIR_NOW
    """

    def __init__(
        self,
        use_llm_api: Optional[bool] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        # 1. Determine whether to use Live LLM or Offline Deterministic mode
        if use_llm_api is None:
            env_val = os.getenv("USE_REAL_LLM", "false").strip().lower()
            self.use_llm_api = env_val in ("true", "1", "yes")
        else:
            self.use_llm_api = use_llm_api

        # 2. Configure provider & keys
        self.provider = (provider or os.getenv("LLM_PROVIDER", "auto")).lower()
        self.api_key = api_key
        self.model_name = model_name
        self.session = None
        self._detect_and_configure_provider()

    def _detect_and_configure_provider(self):
        """Auto-detects active provider and API key if set to auto."""
        google_key = self.api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        openai_key = self.api_key or os.getenv("OPENAI_API_KEY")
        anthropic_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")

        if self.provider == "auto":
            if google_key:
                self.active_provider = "google"
                self.active_key = google_key
                self.active_model = self.model_name or os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite")
            elif openai_key:
                self.active_provider = "openai"
                self.active_key = openai_key
                self.active_model = self.model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            elif anthropic_key:
                self.active_provider = "anthropic"
                self.active_key = anthropic_key
                self.active_model = self.model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
            else:
                self.active_provider = "none"
                self.active_key = None
                self.active_model = None
        elif self.provider in ("google", "gemini"):
            self.active_provider = "google"
            self.active_key = google_key
            self.active_model = self.model_name or os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite")
        elif self.provider == "openai":
            self.active_provider = "openai"
            self.active_key = openai_key
            self.active_model = self.model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        elif self.provider == "anthropic":
            self.active_provider = "anthropic"
            self.active_key = anthropic_key
            self.active_model = self.model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
        else:
            self.active_provider = "none"
            self.active_key = None
            self.active_model = None

    def get_status(self) -> Dict[str, Any]:
        """Returns the current operational mode and provider status."""
        has_key = bool(self.active_key)
        return {
            "use_llm_api": self.use_llm_api and has_key,
            "mode": "Live LLM API" if (self.use_llm_api and has_key) else "Offline Deterministic",
            "provider": self.active_provider,
            "model": self.active_model,
            "has_api_key": has_key
        }

    def _parse_api_error(self, resp) -> str:
        """Parses meaningful error message from JSON response."""
        try:
            data = resp.json()
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    return err.get("message", json.dumps(err))
                return str(err)
            return resp.text[:200]
        except Exception:
            return resp.text[:200]

    # ==========================================
    # UNIVERSAL REST API CALLER (Zero extra pip deps)
    # ==========================================
    def _call_live_llm(self, prompt: str, system_prompt: str = "", json_mode: bool = False) -> Optional[str]:
        """
        Executes a direct HTTPS request to Google Gemini, OpenAI, or Anthropic.
        Returns the text response or None on failure.
        """
        if not self.use_llm_api or not self.active_key or self.active_provider == "none":
            return None

        import requests
        if getattr(self, "session", None) is None:
            self.session = requests.Session()
        timeout_sec = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

        try:
            if self.active_provider == "google":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.active_model}:generateContent?key={self.active_key}"
                headers = {"Content-Type": "application/json"}
                full_prompt = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt
                payload: Dict[str, Any] = {
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 600 if json_mode else 250}
                }
                if json_mode:
                    payload["generationConfig"]["responseMimeType"] = "application/json"

                resp = self.session.post(url, headers=headers, json=payload, timeout=timeout_sec)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                else:
                    err_msg = self._parse_api_error(resp)
                    print(f"\n[Live LLM Warning - Google HTTP {resp.status_code}]: {err_msg}")
                    print("   -> Falling back to offline deterministic engine.")

            elif self.active_provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.active_key}",
                    "Content-Type": "application/json"
                }
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": self.active_model,
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 300
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}

                resp = self.session.post(url, headers=headers, json=payload, timeout=timeout_sec)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                else:
                    err_msg = self._parse_api_error(resp)
                    print(f"\n[Live LLM Warning - OpenAI HTTP {resp.status_code}]: {err_msg}")
                    print("   -> Falling back to offline deterministic engine.")

            elif self.active_provider == "anthropic":
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": self.active_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.active_model,
                    "max_tokens": 300,
                    "temperature": 0.1,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}]
                }
                resp = self.session.post(url, headers=headers, json=payload, timeout=timeout_sec)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content", [])
                    if content:
                        return content[0].get("text", "").strip()
                else:
                    err_msg = self._parse_api_error(resp)
                    print(f"\n[Live LLM Warning - Anthropic HTTP {resp.status_code}]: {err_msg}")
                    print("   -> Falling back to offline deterministic engine.")

        except Exception as e:
            print(f"\n[Live LLM Connection Error ({self.active_provider.upper()})]: {e}")
            print("   -> Falling back to offline deterministic engine.")
            return None

        return None

    # ==========================================
    # SANITIZATION & ATTRIBUTE EXTRACTION
    # ==========================================
    def sanitize_complaint_text(self, text: str) -> str:
        """
        Prompt-injection defense (Design Doc Sec 4):
        Treats complaint text strictly as data, strips system prompt overrides or escape sequences.
        """
        if not text:
            return ""
        cleaned = re.sub(r"(?i)(ignore previous instructions|system prompt|you are now|override priority)", "[FILTERED]", text)
        return cleaned.strip()

    def extract_complaint_attributes(self, text: str) -> Dict[str, Any]:
        """
        Extracts physical damage attributes from text (depth, area, water, location).
        Dual-mode: Uses Live LLM if enabled, otherwise executes deterministic regex.
        The LLM only extracts attributes; computation is done by deterministic tools.
        """
        # Attempt Live LLM extraction if enabled
        if self.use_llm_api and self.active_key:
            system_prompt = (
                "You are an expert civic infrastructure inspection assistant. Extract physical attributes "
                "from citizen pothole/road damage complaints into a JSON object.\n"
                "Return strictly valid JSON with these keys:\n"
                "- depth_cm (float): estimated depth in cm. If unspecified: default 4.0, or 8.0 for 'crater'/'deep', 2.0 for 'shallow'\n"
                "- area_sqm (float): estimated patch area in square meters. If unspecified: default 1.0, 3.5 for 'large'/'massive', 0.5 for 'minor'\n"
                "- standing_water (bool): true if water, rain, puddle, ponding, or submerged is mentioned\n"
                "- location_on_carriageway (str): 'wheel_path', 'center_lane', or 'shoulder'\n"
                "- is_traffic_blocking (bool): true if traffic jams, skids, bus swerving, or accidents mentioned\n"
                "- observation_notes (str): brief summary of qualitative nuances or local landmarks"
            )
            raw_response = self._call_live_llm(
                prompt=f"Citizen Complaint Text: \"{self.sanitize_complaint_text(text)}\"",
                system_prompt=system_prompt,
                json_mode=True
            )
            if raw_response:
                try:
                    # Clean markdown codeblocks if returned
                    clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response.strip(), flags=re.MULTILINE)
                    parsed = json.loads(clean_json)
                    return {
                        "depth_cm": float(parsed.get("depth_cm", 4.0)),
                        "area_sqm": float(parsed.get("area_sqm", 1.0)),
                        "standing_water": bool(parsed.get("standing_water", False)),
                        "location_on_carriageway": str(parsed.get("location_on_carriageway", "center_lane")),
                        "is_traffic_blocking": bool(parsed.get("is_traffic_blocking", False)),
                        "observation_notes": str(parsed.get("observation_notes", "Extracted via Live LLM")),
                        "extraction_mode": f"Live LLM ({self.active_provider}:{self.active_model})"
                    }
                except Exception as e:
                    logger.warning(f"Failed to parse LLM extraction JSON: {e}. Falling back to regex.")

        # Deterministic Offline Regex Extractor (Default / Fallback)
        text_lower = text.lower() if text else ""
        
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
            "is_traffic_blocking": traffic_blocking,
            "observation_notes": "Extracted via offline deterministic regex",
            "extraction_mode": "Offline Deterministic"
        }

    # ==========================================
    # REACT THOUGHT GENERATION
    # ==========================================
    def generate_intake_thought(self, report_count: int, first_report: Dict[str, Any]) -> Tuple[str, str]:
        """Thought for Step 1: Intake & Validation."""
        safe_text = self.sanitize_complaint_text(first_report.get("text", ""))

        if self.use_llm_api and self.active_key:
            prompt = (
                f"You are the Road Repair Prioritization Agent. We received a batch of {report_count} complaint(s).\n"
                f"Sample complaint: \"{safe_text}\"\n"
                "Write a concise, professional engineering 'THOUGHT' explaining input validation, prompt-injection defense, "
                "and planning the spatial/temporal clustering step."
            )
            llm_thought = self._call_live_llm(prompt=prompt, system_prompt="Keep the thought under 45 words starting with 'THOUGHT:'.")
            if llm_thought:
                return llm_thought, "cluster_reports"

        thought = (
            f"THOUGHT: Received batch containing {report_count} complaint(s). "
            f"Validating schema integrity and applying prompt-injection defense on citizen text. "
            f"Next step is spatial and semantic clustering to merge repeat reports."
        )
        return thought, "cluster_reports"

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
            if self.use_llm_api and self.active_key:
                prompt = (
                    f"Cluster {cluster['cluster_id']} matches open ticket {dup_id}. "
                    "Write a professional ReAct thought explaining why we skip downstream tools and merge to prevent municipal double-spend."
                )
                llm_thought = self._call_live_llm(prompt=prompt, system_prompt="Start with 'THOUGHT [Branch A - Duplicate Detection]:' and keep under 50 words.")
                if llm_thought:
                    return llm_thought, "MERGE_DUPLICATE", "BRANCH_A"

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

        if self.use_llm_api and self.active_key:
            prompt = (
                f"Cluster {cluster['cluster_id']} is a fresh, non-duplicate complaint at ({lat}, {lon}) with text '{text[:60]}'. "
                "Write a concise thought initiating geographic resolution on Ward 34 road network."
            )
            llm_thought = self._call_live_llm(prompt=prompt, system_prompt="Start with 'THOUGHT [Branch Routing]:' and keep under 40 words.")
            if llm_thought:
                return llm_thought, "resolve_location", None

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
        if self.use_llm_api and self.active_key:
            prompt = (
                f"Road segment resolved to '{road_name}' ({segment_id}, class: {road_class}). "
                "Write a thought explaining that we will query the SQLite database to check statutory defect liability period."
            )
            llm_thought = self._call_live_llm(prompt=prompt, system_prompt="Start with 'THOUGHT:' and keep under 40 words.")
            if llm_thought:
                return llm_thought, "query_maintenance_db"

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
            if self.use_llm_api and self.active_key:
                prompt = (
                    f"Segment is under warranty by contractor '{contractor}' until {expiry} ({days_left} days left). "
                    "Write a ReAct thought citing BBMP Tender Clause 14.5 requiring contractor rectification at zero city cost."
                )
                llm_thought = self._call_live_llm(prompt=prompt, system_prompt="Start with 'THOUGHT [Branch C - Defect Liability Triggered]:' and keep under 50 words.")
                if llm_thought:
                    return llm_thought, "retrieve_criteria", "BRANCH_C"

            thought = (
                f"THOUGHT [Branch C - Defect Liability Triggered]: Segment was resurfaced with a defect liability warranty "
                f"assigned to contractor '{contractor}' valid until {expiry} ({days_left} days remaining). "
                f"Per BBMP Tender Clause 14.5, recurrence within DLP requires contractor rectification at zero municipal cost. "
                f"Executing retrieve_criteria to ground the exact contractual liability clause before routing."
            )
            action = "retrieve_criteria"
            branch = "BRANCH_C"
        else:
            if self.use_llm_api and self.active_key:
                prompt = (
                    "Segment warranty is expired or not under defect liability. "
                    "Write a thought explaining that we will score severity using IRC:82 and estimate repair cost."
                )
                llm_thought = self._call_live_llm(prompt=prompt, system_prompt="Start with 'THOUGHT [Branch D - Fresh Damage]:' and keep under 40 words.")
                if llm_thought:
                    return llm_thought, "score_severity", "BRANCH_D"

            thought = (
                f"THOUGHT [Branch D - Fresh Damage]: Segment is not under active contractor liability. "
                f"Proceeding to engineering scoring: compute severity from physical attributes, "
                f"estimate repair cost, and retrieve road-class action thresholds."
            )
            action = "score_severity"
            branch = "BRANCH_D"

        return thought, action, branch
