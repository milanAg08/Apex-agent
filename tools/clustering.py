"""
Tool 2: cluster_reports
Clusters multiple citizen complaint reports based on:
1. Haversine distance (spatial proximity, <= 35 meters)
2. Time window delta (temporal proximity, <= 7 days)
3. Text similarity (TF-IDF cosine similarity, >= 0.55)
Also cross-references merged clusters against active open tickets in the maintenance database
to identify duplicates (Branch A trigger).
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tools.location import haversine_distance_meters

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "maintenance_db.sqlite")

class ReportClusterer:
    def __init__(
        self,
        max_distance_meters: float = 35.0,
        max_time_days: int = 7,
        min_text_similarity: float = 0.45,
        db_path: str = DB_PATH
    ):
        self.max_distance = max_distance_meters
        self.max_time_days = max_time_days
        self.min_text_similarity = min_text_similarity
        self.db_path = db_path

    def compute_text_similarity(self, text1: str, text2: str) -> float:
        """Calculates cosine similarity between two report text descriptions."""
        if not text1.strip() or not text2.strip():
            return 0.0
        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform([text1, text2])
            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            return float(sim)
        except Exception:
            # Fallback simple word overlap Jaccard
            w1 = set(text1.lower().split())
            w2 = set(text2.lower().split())
            intersection = len(w1 & w2)
            union = len(w1 | w2)
            return intersection / union if union > 0 else 0.0

    def parse_date(self, date_str: str) -> datetime:
        """Parses common ISO date strings."""
        try:
            return datetime.fromisoformat(date_str.split("T")[0])
        except Exception:
            return datetime(2026, 10, 25)

    def fetch_open_tickets(self) -> List[Dict[str, Any]]:
        """Queries active open tickets from SQLite database."""
        if not os.path.exists(self.db_path):
            return []
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT ticket_id, segment_id, lat, lon, reported_date, description, status, priority FROM open_tickets;")
        rows = cur.fetchall()
        conn.close()

        return [
            {
                "ticket_id": r[0],
                "segment_id": r[1],
                "lat": float(r[2]),
                "lon": float(r[3]),
                "reported_date": r[4],
                "description": r[5],
                "status": r[6],
                "priority": r[7]
            }
            for r in rows
        ]

    def check_duplicate_open_ticket(
        self,
        cluster_lat: float,
        cluster_lon: float,
        cluster_text: str,
        cluster_date: str,
        cluster_segment_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Checks if a cluster matches an existing active ticket.
        Returns matching ticket dict if duplicate condition holds.
        """
        open_tickets = self.fetch_open_tickets()
        c_date = self.parse_date(cluster_date)

        for ticket in open_tickets:
            # Distance check
            dist = haversine_distance_meters(cluster_lat, cluster_lon, ticket["lat"], ticket["lon"])
            t_date = self.parse_date(ticket["reported_date"])
            days_diff = abs((c_date - t_date).days)
            text_sim = self.compute_text_similarity(cluster_text, ticket["description"])

            # High confidence duplicate match
            same_segment = (cluster_segment_id == ticket["segment_id"]) if cluster_segment_id else False
            
            if (dist <= 45.0 or same_segment) and days_diff <= 14 and (text_sim >= 0.40 or dist <= 20.0):
                return {
                    "matched_ticket_id": ticket["ticket_id"],
                    "status": ticket["status"],
                    "ticket_description": ticket["description"],
                    "distance_meters": round(dist, 1),
                    "days_apart": days_diff,
                    "text_similarity": round(text_sim, 2),
                    "is_duplicate": True
                }

        return None

    def cluster(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Groups list of incoming reports into deduplicated clusters and checks against open tickets.
        """
        if not reports:
            return []

        clusters: List[Dict[str, Any]] = []

        for report in reports:
            rep_lat = report.get("lat")
            rep_lon = report.get("lon")
            rep_text = report.get("text", "")
            rep_date_str = report.get("reported_date", "2026-10-26")
            rep_date = self.parse_date(rep_date_str)
            rep_id = report.get("report_id", f"REP_{len(clusters)+1}")

            matched_cluster = None

            for cluster in clusters:
                c_lat = cluster["centroid_lat"]
                c_lon = cluster["centroid_lon"]
                
                # Check spatial distance if coordinates available
                if rep_lat is not None and rep_lon is not None and c_lat is not None and c_lon is not None:
                    dist = haversine_distance_meters(rep_lat, rep_lon, c_lat, c_lon)
                else:
                    dist = 0.0 if report.get("segment_id") == cluster.get("segment_id") else 999.0

                # Check temporal window
                c_date = self.parse_date(cluster["latest_date"])
                time_diff = abs((rep_date - c_date).days)

                # Check text similarity
                sim = self.compute_text_similarity(rep_text, cluster["combined_text"])

                if dist <= self.max_distance and time_diff <= self.max_time_days and (sim >= self.min_text_similarity or dist <= 15.0):
                    matched_cluster = cluster
                    break

            if matched_cluster:
                matched_cluster["reports"].append(report)
                matched_cluster["report_count"] += 1
                matched_cluster["combined_text"] += f" | {rep_text}"
                if rep_lat and rep_lon:
                    # Update centroid
                    n = matched_cluster["report_count"]
                    matched_cluster["centroid_lat"] = ((matched_cluster["centroid_lat"] * (n - 1)) + rep_lat) / n
                    matched_cluster["centroid_lon"] = ((matched_cluster["centroid_lon"] * (n - 1)) + rep_lon) / n
                if rep_date > self.parse_date(matched_cluster["latest_date"]):
                    matched_cluster["latest_date"] = rep_date_str
            else:
                new_cluster = {
                    "cluster_id": f"CLUST_{len(clusters)+1:03d}",
                    "reports": [report],
                    "report_count": 1,
                    "centroid_lat": rep_lat,
                    "centroid_lon": rep_lon,
                    "segment_id": report.get("segment_id"),
                    "combined_text": rep_text,
                    "latest_date": rep_date_str,
                    "is_duplicate": False,
                    "duplicate_ticket_id": None
                }
                clusters.append(new_cluster)

        # Cross-reference every cluster with open tickets in database
        for cluster in clusters:
            if cluster["centroid_lat"] and cluster["centroid_lon"]:
                dup_match = self.check_duplicate_open_ticket(
                    cluster["centroid_lat"],
                    cluster["centroid_lon"],
                    cluster["combined_text"],
                    cluster["latest_date"],
                    cluster.get("segment_id")
                )
                if dup_match:
                    cluster["is_duplicate"] = True
                    cluster["duplicate_ticket_id"] = dup_match["matched_ticket_id"]
                    cluster["duplicate_info"] = dup_match

        return clusters

def cluster_reports(reports: List[Dict[str, Any]], open_tickets: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Public tool function to cluster incoming reports."""
    clusterer = ReportClusterer()
    return clusterer.cluster(reports)
