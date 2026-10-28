"""
Tool 6: retrieve_criteria
Retrieves cited policy chunks from IRC:82 and BBMP Tender specifications.
Runs through agentic grading, query rewrite (if weak), and fallback rule table.
"""

from typing import Dict, Any, Optional
from rag.grader import AgenticRAGGrader

_grader_instance = None

def get_grader() -> AgenticRAGGrader:
    global _grader_instance
    if _grader_instance is None:
        _grader_instance = AgenticRAGGrader(confidence_threshold=0.40, max_rewrites=2)
    return _grader_instance

def retrieve_criteria(query: str, category: str = "defect_liability") -> Dict[str, Any]:
    """
    Public tool function for agent to query municipal maintenance corpus.
    """
    grader = get_grader()
    result = grader.retrieve_with_grading(query=query, target_category=category)
    return {
        "status": result["status"],
        "citation": result["citation"],
        "text": result["chunk"]["text"],
        "chunk_id": result["chunk"]["chunk_id"],
        "clause": result["chunk"].get("clause", ""),
        "confidence_score": result["confidence_score"],
        "fallback_used": result["fallback_used"],
        "rewrites_attempted": result["rewrites_attempted"]
    }
