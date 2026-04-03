"""
LLM Client for semantic text processing and extraction.

Using sentence transformers for embedding-based similarity and context retrieval.
No external API dependency - runs locally.
"""

import json
import logging
import torch
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
        Find semantic matches for a query among candidates using embeddings.

        Args:
            query: Search query text
            candidates: List of candidate texts
            top_k: Number of top results (uses self.top_k if None)

        Returns:
            List of (text, similarity_score) tuples, sorted by score descending
        """
        if not self.embedder or not candidates:
            return []
        
        try:
            if top_k is None:
                top_k = self.top_k
            
            top_k = min(top_k, len(candidates))
            
            # Encode query and candidates
            query_embedding = self.embedder.encode(query, convert_to_tensor=True)
            candidate_embeddings = self.embedder.encode(candidates, convert_to_tensor=True)
            
            # Compute similarity scores
            cos_scores = util.pytorch_cos_sim(query_embedding, candidate_embeddings)[0]
            
            # Get top-k results
            top_results = torch.topk(cos_scores, k=top_k)
            
            results = [
                (candidates[idx], float(score))
                for idx, score in zip(top_results.indices, top_results.values)
            ]
            
            self.search_calls += 1
            self.total_results += len(results)
            
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
        force_extraction: bool = False,
    ) -> Tuple[Dict[str, Any], float, int]:
        """
        Extract fields using semantic search if deterministic confidence is insufficient.
        
        REAL EXTRACTION: Uses embedding similarity to find key information from text.

        Args:
            text: Page text content
            doc_type: DocumentType (ECHALLAN or NA_PERMISSION)
            deterministic_result: Result from deterministic extractor (if available)
            deterministic_confidence: Confidence from deterministic extraction
            force_extraction: If True, always perform semantic extraction (e.g., for image-only pages)

        Returns:
            Tuple of (extraction_dict, overall_confidence, tokens_used)
        """
        # Skip if deterministic confidence is high enough (unless forced)
        if not force_extraction and not self.should_use_llm(deterministic_confidence):
            return (
                deterministic_result or {},
                deterministic_confidence,
                0,
            )

        # Use semantic search for low confidence
        logger.info(
            f"Using semantic extraction for {doc_type.value} "
            f"(deterministic confidence {deterministic_confidence:.2f} < {self.confidence_threshold})"
        )

        result = deterministic_result.copy() if deterministic_result else {}
        tokens_used = 0
        field_scores = []
        
        try:
            if doc_type == DocumentType.ECHALLAN:
                # eChallan field names to search for
                field_queries = {
                    "challan_number": "challan ticket number id",
                    "vehicle_reg_number": "vehicle registration plate number reg",
                    "violation_code": "violation code section offence",
                    "violation_description": "violation description offence fine reason",
                    "amount_due": "amount fine penalty due rupees rs",
                    "payment_status": "payment status paid pending dispute",
                    "payment_due_date": "payment due date deadline",
                    "officer_id": "officer id constable badge number",
                    "issuing_date": "issued date issue on when"
                }
                
                # Extract each field using semantic search
                text_lines = text.split('\n')
                text_chunks = [line for line in text_lines if line.strip()]
                
                if text_chunks:
                    for field_name, query in field_queries.items():
                        # Skip if already extracted with high confidence
                        if field_name in result and result[field_name]:
                            field_scores.append(0.95)  # Trust deterministic
                            continue
                        
                        # Semantic search for this field
                        matches = self.get_semantic_matches(query, text_chunks, top_k=2)
                        
                        if matches:
                            best_match, similarity = matches[0]
                            tokens_used += len(best_match.split()) + len(query.split())
                            
                            # Extract value from best match using simple heuristics
                            extracted_value = self._extract_value_from_match(
                                best_match, field_name, similarity
                            )
                            
                            if extracted_value:
                                result[field_name] = extracted_value
                                field_scores.append(min(0.85, 0.5 + similarity))
                            else:
                                field_scores.append(0.3)
                        else:
                            field_scores.append(0.2)
                
                # Calculate semantic confidence
                if field_scores:
                    semantic_confidence = sum(field_scores) / len(field_scores)
                else:
                    semantic_confidence = deterministic_confidence
                
                # Blend with deterministic confidence
                blended_confidence = (deterministic_confidence * 0.3) + (semantic_confidence * 0.7)
                
            elif doc_type == DocumentType.NA_PERMISSION:
                # NA_PERMISSION field names
                field_queries = {
                    "property_owner_name": "property owner name person",
                    "property_address": "property address location area street",
                    "survey_number": "survey number plot id sno",
                    "area": "area sq ft size square meter",
                    "permission_type": "permission type approval kind class",
                    "permission_date": "permission date issued when",
                    "authority": "authority issued by department office",
                    "permission_number": "permission number id reference",
                    "notes": "notes remarks remarks conditions"
                }
                
                text_lines = text.split('\n')
                text_chunks = [line for line in text_lines if line.strip()]
                
                if text_chunks:
                    for field_name, query in field_queries.items():
                        if field_name in result and result[field_name]:
                            field_scores.append(0.95)
                            continue
                        
                        matches = self.get_semantic_matches(query, text_chunks, top_k=2)
                        
                        if matches:
                            best_match, similarity = matches[0]
                            tokens_used += len(best_match.split()) + len(query.split())
                            
                            extracted_value = self._extract_value_from_match(
                                best_match, field_name, similarity
                            )
                            
                            if extracted_value:
                                result[field_name] = extracted_value
                                field_scores.append(min(0.85, 0.5 + similarity))
                            else:
                                field_scores.append(0.3)
                        else:
                            field_scores.append(0.2)
                
                if field_scores:
                    semantic_confidence = sum(field_scores) / len(field_scores)
                else:
                    semantic_confidence = deterministic_confidence
                
                blended_confidence = (deterministic_confidence * 0.3) + (semantic_confidence * 0.7)
            else:
                blended_confidence = deterministic_confidence

        except Exception as e:
            logger.error(f"Semantic extraction failed: {e}, using deterministic result")
            blended_confidence = deterministic_confidence
            tokens_used = 0

        logger.info(
            f"Semantic extraction complete - "
            f"confidence: {blended_confidence:.3f}, tokens: {tokens_used}"
        )

        return result, blended_confidence, tokens_used

    def _extract_value_from_match(self, text: str, field_name: str, similarity: float) -> Optional[str]:
        """
        Extract likely value from matched text chunk using field-specific logic.
        
        Args:
            text: Text chunk that matched
            field_name: Name of field being extracted
            similarity: Embedding similarity score
            
        Returns:
            Extracted value or None
        """
        text = text.strip()
        if not text or len(text) < 2:
            return None
        
        # For numeric fields, extract numbers
        if "number" in field_name or "amount" in field_name or "area" in field_name:
            import re
            numbers = re.findall(r'\d+(?:\.\d+)?', text)
            if numbers:
                return numbers[0]
        
        # For date fields
        if "date" in field_name:
            import re
            dates = re.findall(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', text)
            if dates:
                return dates[0]
        
        # For status/category fields, return the whole text if similarity is high
        if similarity > 0.6:
            return text[:100]  # Limit length
        
        return None

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
