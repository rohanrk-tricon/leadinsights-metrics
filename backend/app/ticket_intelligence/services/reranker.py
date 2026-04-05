import logging
from typing import List, Any
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

class RerankerService:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        logger.info("Initializing CrossEncoder reranker model: %s", model_name)
        # Load the model with sequence truncation enabled to prevent context errors
        self.encoder = CrossEncoder(model_name, max_length=512)

    def rerank(self, query: str, candidates: List[Any], top_k: int = 5) -> List[Any]:
        if not candidates:
            return []
            
        logger.info("Reranking %d candidates with CrossEncoder", len(candidates))
        
        pairs = []
        for c in candidates:
            # Safely extract text from DB tuple (id, subject, structured_description)
            subject = c[1] if len(c) > 1 and c[1] else ""
            desc = c[2] if len(c) > 2 and c[2] else ""
            text = f"{subject} - {desc}"
            pairs.append((query, text))
            
        scores = self.encoder.predict(pairs)
        
        # Zip scores and candidates, sort by score descending
        scored = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        
        # Return only the bounded candidate objects
        return [candidate for score, candidate in scored[:top_k]]

_reranker_instance = None

def get_reranker() -> RerankerService:
    """Lazy loads a singleton instance of the reranker to avoid reloading models on every API request."""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = RerankerService()
    return _reranker_instance