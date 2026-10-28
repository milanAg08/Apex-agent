"""
Agentic RAG Chunk Grader, Query Rewriter, and Fallback Selector.
Validates whether retrieved policy chunks satisfy the required query criteria.
If confidence is insufficient, attempts query rewriting (capped at max_rewrites).
If still low confidence, falls back gracefully to the default municipal rule table.
"""

from typing import Dict, Any, List, Tuple
from rag.retriever import PolicyRetriever
from rag.fallback_rules import get_fallback_rule

class AgenticRAGGrader:
    def __init__(self, confidence_threshold: float = 0.40, max_rewrites: int = 2):
        self.retriever = PolicyRetriever()
        self.confidence_threshold = confidence_threshold
        self.max_rewrites = max_rewrites

    def grade_chunk(self, chunk: Dict[str, Any], target_category: str) -> Tuple[bool, float, str]:
        """
        Grades an individual chunk against target category and confidence.
        Returns: (is_relevant, score, reason)
        """
        score = chunk.get("confidence_score", 0.0)
        chunk_category = chunk.get("category", "")
        
        # Category alignment
        category_match = (target_category == chunk_category) or (target_category in ["all", ""])
        
        if category_match and score >= self.confidence_threshold:
            return True, score, f"Passed grading: score {score:.2f} >= {self.confidence_threshold} with category '{chunk_category}'"
        elif not category_match and score >= (self.confidence_threshold + 0.15):
            return True, score, f"Accepted cross-category match: score {score:.2f} despite category mismatch ({chunk_category} vs {target_category})"
        else:
            return False, score, f"Failed grading: score {score:.2f} < {self.confidence_threshold} or mismatched intent"

    def rewrite_query(self, query: str, target_category: str, attempt: int) -> str:
        """
        Synthesizes an enriched semantic query if the initial attempt failed.
        Uses standardized municipal terminology.
        """
        expansions = {
            "defect_liability": [
                f"{query} BBMP tender clause defect liability period asphalt thickness years",
                f"Defect liability period warranty 40mm bituminous road surface repair contractor"
            ],
            "action_thresholds": [
                f"{query} IRC:82 severity action threshold arterial collector local inspect repair",
                f"Pothole severity threshold separating inspect from repair_now by road class"
            ],
            "severity_threshold": [
                f"{query} IRC:82 pothole depth water carriageway wheel path classification",
                f"Pothole severity grading criteria depth mm area water ponding"
            ],
            "response_times": [
                f"{query} standard response time hours days P1 P2 P3 P4 emergency routine",
                f"Service charter priority turnaround SLA emergency 24 hours 48 hours"
            ],
            "cost_specification": [
                f"{query} unit rate 1200 rupees per sqm cost threshold 25000",
                f"Schedule of rates cold mix hot mix patch unit rate inr per m2"
            ]
        }
        
        cat_expansions = expansions.get(target_category, [f"{query} standard guidelines", f"{query} municipal criteria"])
        idx = min(attempt - 1, len(cat_expansions) - 1)
        return cat_expansions[idx]

    def retrieve_with_grading(
        self,
        query: str,
        target_category: str = "defect_liability",
        top_k: int = 2
    ) -> Dict[str, Any]:
        """
        Executes the agentic RAG loop:
        1. Retrieve candidates
        2. Grade candidate chunks
        3. If grade fails, rewrite query and re-retrieve (capped)
        4. If still fails, fall back to default rule table
        """
        history = []
        current_query = query
        attempt = 0

        while attempt <= self.max_rewrites:
            candidates = self.retriever.retrieve(current_query, top_k=top_k)
            attempt += 1

            if candidates:
                best_chunk = candidates[0]
                passed, score, reason = self.grade_chunk(best_chunk, target_category)
                history.append({
                    "attempt": attempt,
                    "query": current_query,
                    "best_chunk_id": best_chunk["chunk_id"],
                    "score": score,
                    "passed": passed,
                    "reason": reason
                })

                if passed:
                    return {
                        "status": "SUCCESS",
                        "chunk": best_chunk,
                        "citation": best_chunk["citation"],
                        "confidence_score": score,
                        "fallback_used": False,
                        "rewrites_attempted": attempt - 1,
                        "grading_history": history
                    }
            else:
                history.append({
                    "attempt": attempt,
                    "query": current_query,
                    "best_chunk_id": None,
                    "score": 0.0,
                    "passed": False,
                    "reason": "Zero candidates returned"
                })

            if attempt <= self.max_rewrites:
                current_query = self.rewrite_query(query, target_category, attempt)

        # Fallback triggered
        fallback = get_fallback_rule(target_category)
        return {
            "status": "FALLBACK_TRIGGERED",
            "chunk": {
                "chunk_id": fallback.get("rule_id", "FALLBACK_RULE"),
                "doc_name": fallback.get("source", "Fallback Rule Table"),
                "clause": "Sec 3.4 Municipal Default Rule Table",
                "category": target_category,
                "text": str(fallback),
                "confidence_score": 1.0,
                "citation": fallback.get("citation", "Default Municipal Fallback Rule Table")
            },
            "citation": fallback.get("citation", "Default Municipal Fallback Rule Table"),
            "confidence_score": 1.0,
            "fallback_used": True,
            "rewrites_attempted": attempt - 1,
            "grading_history": history
        }
