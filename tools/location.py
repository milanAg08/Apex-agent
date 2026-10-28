"""
Tool 1: resolve_location
Resolves text complaint description or GPS coordinates (lat/lon) to a specific
road segment and road class using the cached OpenStreetMap extract of Ward 34.
"""

import json
import math
import os
import re
from typing import Dict, Any, Optional, Tuple, Union

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "osm_ward34.json")

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class LocationResolver:
    def __init__(self, osm_path: str = DATA_PATH):
        with open(osm_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.segments = self.data.get("segments", [])
        self.landmarks = self.data.get("ward_info", {}).get("landmarks", {})

    def resolve(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolves location to road segment, road class, and c_road multiplier.
        Returns resolution status, segment details, or 'UNRESOLVED'.
        """
        # 1. Coordinate-based resolution
        if lat is not None and lon is not None:
            best_segment = None
            min_dist = float("inf")

            for seg in self.segments:
                s_lat, s_lon = seg["start_coord"]
                e_lat, e_lon = seg["end_coord"]
                mid_lat = (s_lat + e_lat) / 2.0
                mid_lon = (s_lon + e_lon) / 2.0
                
                # Check bounding box
                min_b_lat, min_b_lon, max_b_lat, max_b_lon = seg["bounding_box"]
                in_bbox = (min_b_lat <= lat <= max_b_lat) and (min_b_lon <= lon <= max_b_lon)

                dist = haversine_distance_meters(lat, lon, mid_lat, mid_lon)
                if in_bbox and dist < min_dist:
                    min_dist = dist
                    best_segment = seg
                elif dist < 350.0 and dist < min_dist:
                    min_dist = dist
                    best_segment = seg

            if best_segment and min_dist <= 400.0:
                return {
                    "status": "RESOLVED",
                    "method": "GPS_COORDINATES",
                    "segment_id": best_segment["segment_id"],
                    "road_name": best_segment["name"],
                    "road_class": best_segment["road_class"],
                    "c_road": best_segment["c_road"],
                    "traffic_index": best_segment["traffic_index"],
                    "distance_meters": round(min_dist, 1),
                    "confidence": 0.95 if min_dist < 50 else 0.85
                }

        # 2. Text / Landmark / Street Name matching
        if text and text.strip():
            clean_text = text.lower()
            
            # Check for vague / ambiguous phrases
            vague_phrases = ["somewhere", "near a tree", "around bangalore", "unknown street", "pothole on road", "near shop"]
            if any(phrase in clean_text for phrase in vague_phrases) and len(clean_text.split()) < 7:
                # Check if an explicit street name is also present
                has_street = any(alias in clean_text for s in self.segments for alias in s.get("aliases", []))
                if not has_street:
                    return {
                        "status": "UNRESOLVED",
                        "method": "TEXT_VAGUE",
                        "error": "Location text is too vague to resolve to a specific road segment without coordinates",
                        "confidence": 0.1
                    }

            # Match segment aliases
            for seg in self.segments:
                for alias in seg.get("aliases", []):
                    if alias in clean_text:
                        return {
                            "status": "RESOLVED",
                            "method": "TEXT_STREET_ALIAS",
                            "segment_id": seg["segment_id"],
                            "road_name": seg["name"],
                            "road_class": seg["road_class"],
                            "c_road": seg["c_road"],
                            "traffic_index": seg["traffic_index"],
                            "matched_alias": alias,
                            "confidence": 0.90
                        }

            # Match landmarks
            if "bms" in clean_text or "bmsce" in clean_text or "bull temple" in clean_text:
                seg = next(s for s in self.segments if s["segment_id"] == "SEG_BULL_001")
                return {
                    "status": "RESOLVED",
                    "method": "LANDMARK_BMSCE",
                    "segment_id": seg["segment_id"],
                    "road_name": seg["name"],
                    "road_class": seg["road_class"],
                    "c_road": seg["c_road"],
                    "traffic_index": seg["traffic_index"],
                    "confidence": 0.92
                }

            if "dvg" in clean_text or "gundappa" in clean_text:
                seg = next(s for s in self.segments if s["segment_id"] == "SEG_DVG_001")
                return {
                    "status": "RESOLVED",
                    "method": "LANDMARK_DVG",
                    "segment_id": seg["segment_id"],
                    "road_name": seg["name"],
                    "road_class": seg["road_class"],
                    "c_road": seg["c_road"],
                    "traffic_index": seg["traffic_index"],
                    "confidence": 0.88
                }

            if "gandhi bazaar" in clean_text or "market" in clean_text:
                seg = next(s for s in self.segments if s["segment_id"] == "SEG_GANDHI_001")
                return {
                    "status": "RESOLVED",
                    "method": "LANDMARK_GANDHI_BAZAAR",
                    "segment_id": seg["segment_id"],
                    "road_name": seg["name"],
                    "road_class": seg["road_class"],
                    "c_road": seg["c_road"],
                    "traffic_index": seg["traffic_index"],
                    "confidence": 0.85
                }

        return {
            "status": "UNRESOLVED",
            "method": "NONE",
            "error": "Could not correlate coordinates or text description with any known Ward 34 road segment",
            "confidence": 0.0
        }

_resolver_instance = None

def resolve_location(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    text: Optional[str] = None
) -> Dict[str, Any]:
    """Public tool function to resolve location."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = LocationResolver()
    return _resolver_instance.resolve(lat=lat, lon=lon, text=text)
