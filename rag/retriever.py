"""
Semantic and Keyword Policy Corpus Retriever.
Retrieves cited policy chunks from IRC:82, BBMP Tender 2021, and municipal standards.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rag.corpus import POLICY_CHUNKS

class PolicyRetriever:
    """Retrieves policy chunks using TF-IDF vectorization and keyword boosting."""

    def __init__(self, chunks: Optional[List[Dict[str, Any]]] = None):
        self.chunks = chunks or POLICY_CHUNKS
        self.corpus_texts = [
            f"{c['doc_name']} {c['clause']} {c['text']} {' '.join(c.get('keywords', []))}"
            for c in self.chunks
        ]
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(self.corpus_texts)

    def retrieve(self, query: str, top_k: int = 2, category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves top-k chunks matching the query.
        Returns chunks with 'confidence_score' and formatted 'citation'.
        """
        if not query or not query.strip():
            return []

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Calculate keyword boost
        query_lower = query.lower()
        scored_chunks = []

        for idx, chunk in enumerate(self.chunks):
            if category_filter and chunk.get("category") != category_filter:
                continue

            base_score = float(similarities[idx])
            # Keyword overlap boost
            keyword_hits = sum(1 for kw in chunk.get("keywords", []) if kw.lower() in query_lower)
            boost = min(0.35, keyword_hits * 0.10)
            final_score = min(1.0, base_score + boost)

            citation = f"[{chunk['doc_name']} - {chunk['clause']}]"
            scored_chunks.append({
                "chunk_id": chunk["chunk_id"],
                "doc_name": chunk["doc_name"],
                "clause": chunk["clause"],
                "category": chunk["category"],
                "text": chunk["text"],
                "confidence_score": round(final_score, 4),
                "citation": citation
            })

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x["confidence_score"], reverse=True)
        return scored_chunks[:top_k]
