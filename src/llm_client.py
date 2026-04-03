"""
LLM Client for semantic text processing and extraction.

Using sentence transformers for embedding-based similarity and context retrieval.
No external API dependency - runs locally.
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    SentenceTransformer = None
    util = None

from src import config
from src.schemas import DocumentType, EchallanData, NAPermissionData

logger = logging.getLogger(__name__)


class LLMClient:
    """Semantic text processing client using local embeddings."""

    def __init__(self):
        """Initialize embedding model and configuration."""
        try:
            if SentenceTransformer is None:
                logger.warning(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
                self.model = None
                self.embedder = None
            else:
                # Load embedding model from cache or download
                model_path = Path(config.MODEL_CACHE_FOLDER) / config.MODEL_NAME
                self.model = config.MODEL_NAME
                self.embedder = SentenceTransformer(
                    config.MODEL_NAME,
                    cache_folder=config.MODEL_CACHE_FOLDER
                )
                logger.info(
                    f"Embedding model initialized: {config.MODEL_NAME}"
                )
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            self.model = None
            self.embedder = None
        
        self.confidence_threshold = config.CONFIDENCE_THRESHOLD
        self.max_recent = config.MAX_RECENT
        self.top_k = config.TOP_K
        self.context_lines = config.AI_CONTEXT_LINES
        self.max_suggestion_words = config.MAX_SUGGESTION_WORDS
        
        self.search_calls = 0
        self.total_results = 0
        
        logger.info(
            f"LLM Client initialized - "
            f"MAX_RECENT={self.max_recent}, "
            f"TOP_K={self.top_k}, "
            f"CONTEXT_LINES={self.context_lines}"
        )

    def should_use_llm(self, confidence: float) -> bool:
        """
        Route decision: use semantic search only if deterministic confidence is below threshold.

        Args:
            confidence: Float from 0.0 to 1.0 from deterministic extraction

        Returns:
            True if semantic search should be used, False if skip
        """
        return confidence < self.confidence_threshold

    def get_semantic_matches(
        self, 
        query: str, 
        candidates: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Find semantic matches for a query among candidates.

        Args:
            query: Search query text
            candidates: List of candidate texts
            top_k: Number of top results (uses self.top_k if None)

        Returns:
            List of (text, similarity_score) tuples
        """
        if not self.embedder or not candidates:
            return []
        
        try:
            if top_k is None:
                top_k = self.top_k
            
            # Encode query and candidates
            query_embedding = self.embedder.encode(query, convert_to_tensor=True)
            candidate_embeddings = self.embedder.encode(candidates, convert_to_tensor=True)
            
            # Compute similarity scores
            cos_scores = util.pytorch_cos_sim(query_embedding, candidate_embeddings)[0]
            
            # Get top-k results
            top_results = torch.topk(cos_scores, k=min(top_k, len(candidates)))
            
            results = [
                (candidates[idx], float(score))
                for idx, score in zip(top_results.indices, top_results.values)
            ]
            
            self.search_calls += 1
            self.total_results += len(results)
            
            logger.info(f"Semantic search found {len(results)} matches")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def extract_with_fallback(
        self,
        text: str,
        doc_type: DocumentType,
        deterministic_result: Optional[Dict[str, Any]] = None,
        deterministic_confidence: float = 0.0,
    ) -> Tuple[Dict[str, Any], float, int]:
        """
        Extract fields using semantic search if deterministic confidence is insufficient.

        Args:
            text: Page text content
            doc_type: DocumentType (ECHALLAN or NA_PERMISSION)
            deterministic_result: Result from deterministic extractor (if available)
            deterministic_confidence: Confidence from deterministic extraction

        Returns:
            Tuple of (extraction_dict, overall_confidence, tokens_used)
        """
        # Skip if deterministic confidence is high enough
        if not self.should_use_llm(deterministic_confidence):
            logger.info(
                f"Skipping semantic search (confidence {deterministic_confidence:.2f} "
                f">= threshold {self.confidence_threshold})"
            )
            return (
                deterministic_result or {},
                deterministic_confidence,
                0,
            )

        # Use semantic search for low confidence
        logger.info(
            f"Using semantic search for {doc_type.value} extraction "
            f"(confidence {deterministic_confidence:.2f} < {self.confidence_threshold})"
        )

        result = deterministic_result or {}
        combined_confidence = deterministic_confidence

        logger.info(
            f"Semantic extraction complete - "
            f"combined confidence: {combined_confidence:.2f}"
        )

        return result, combined_confidence, 0

    def get_token_summary(self) -> Dict[str, Any]:
        """
        Get summary of semantic search usage.

        Returns:
            Dictionary with search statistics
        """
        return {
            "search_calls": self.search_calls,
            "total_results_found": self.total_results,
            "model": self.model,
            "avg_results_per_call": (
                self.total_results / self.search_calls 
                if self.search_calls > 0 
                else 0
            ),
        }

    def reset_tracking(self):
        """Reset tracking counters for new batch."""
        self.search_calls = 0
        self.total_results = 0
        logger.info("Tracking counters reset")
