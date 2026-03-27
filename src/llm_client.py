"""
LLM Client for Groq API integration with 6-tier token optimization.

Token strategy:
- Tier 1 (0 tokens): Deterministic extraction (use if confidence >= 0.75)
- Tier 2 (50 tokens): OCR + lightweight validation
- Tier 3 (150 tokens): Classification support
- Tier 4 (100 tokens): Route-specific extraction
- Tier 5 (1000 tokens): Full fallback extraction
- Tier 6 (500 tokens): Summary generation
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple
from groq import Groq
from src import config
from src.schemas import DocumentType, EchallanData, NAPermissionData

logger = logging.getLogger(__name__)


class LLMClient:
    """Groq API client with confidence-based routing and token optimization."""

    def __init__(self):
        """Initialize Groq client with API key from environment."""
        try:
            # Try initializing Groq with just the API key (newer versions don't accept proxies param)
            self.client = Groq(api_key=config.GROQ_API_KEY)
        except TypeError as e:
            if "proxies" in str(e):
                # If proxies error, try alternative initialization
                logger.debug(f"Groq initialization error (proxies): {e}, retrying...")
                import os
                os.environ["GROQ_API_KEY"] = config.GROQ_API_KEY
                from groq import Groq as GroqClient
                self.client = GroqClient()
            else:
                raise
        
        self.model = config.LLM_MODEL
        self.confidence_threshold = config.CONFIDENCE_THRESHOLD  # 0.75
        self.token_usage = {
            "tier_1": 0,
            "tier_2": 0,
            "tier_3": 0,
            "tier_4": 0,
            "tier_5": 0,
            "tier_6": 0,
            "total": 0,
        }
        self.calls_made = 0
        logger.info(
            f"Initialized LLM Client with model: {self.model}, "
            f"confidence threshold: {self.confidence_threshold}"
        )

    def should_use_llm(self, confidence: float) -> bool:
        """
        Route decision: use LLM only if deterministic confidence is below threshold.

        Args:
            confidence: Float from 0.0 to 1.0 from deterministic extraction

        Returns:
            True if LLM should be called, False if skip
        """
        return confidence < self.confidence_threshold

    def extract_with_fallback(
        self,
        text: str,
        doc_type: DocumentType,
        deterministic_result: Optional[Dict[str, Any]] = None,
        deterministic_confidence: float = 0.0,
    ) -> Tuple[Dict[str, Any], float, int]:
        """
        Extract fields using LLM if deterministic confidence is insufficient.

        Args:
            text: Page text content
            doc_type: DocumentType (ECHALLAN or NA_PERMISSION)
            deterministic_result: Result from deterministic extractor (if available)
            deterministic_confidence: Confidence from deterministic extraction

        Returns:
            Tuple of (extraction_dict, overall_confidence, tokens_used)
        """
        # Tier 1: Skip LLM if deterministic confidence is high enough
        if not self.should_use_llm(deterministic_confidence):
            logger.info(
                f"Tier 1: Skipping LLM (confidence {deterministic_confidence:.2f} "
                f">= threshold {self.confidence_threshold})"
            )
            self.token_usage["tier_1"] += 0
            return (
                deterministic_result or {},
                deterministic_confidence,
                0,
            )

        # Tier 3/4: Use LLM for extraction
        logger.info(
            f"Tier 3-4: Calling LLM for {doc_type.value} extraction "
            f"(confidence {deterministic_confidence:.2f} < {self.confidence_threshold})"
        )

        if doc_type == DocumentType.ECHALLAN:
            result, tokens = self._extract_echallan_llm(text)
        elif doc_type == DocumentType.NA_PERMISSION:
            result, tokens = self._extract_na_llm(text)
        else:
            result, tokens = self._extract_unknown_llm(text)

        # Merge with deterministic result if available
        if deterministic_result:
            result = {**deterministic_result, **result}

        # Combine confidences (average with slight LLM preference for low-conf cases)
        combined_confidence = (deterministic_confidence + 0.85) / 2

        self.calls_made += 1
        self.token_usage["tier_4"] += tokens
        self.token_usage["total"] += tokens

        logger.info(
            f"LLM extraction complete - tokens: {tokens}, "
            f"combined confidence: {combined_confidence:.2f}"
        )

        return result, combined_confidence, tokens

    def _extract_echallan_llm(self, text: str) -> Tuple[Dict[str, Any], int]:
        """
        Extract eChallan fields using LLM.

        Expected fields:
        challan_number, vehicle_reg_number, violation_code, violation_description,
        amount_due, payment_status, payment_due_date, officer_id, issuing_date

        Args:
            text: Page text content

        Returns:
            Tuple of (extraction_dict, tokens_used)
        """
        prompt = f"""Extract traffic challan (eChallan) information from this text. 
Return ONLY valid JSON with these keys (null if not found):
- challan_number
- vehicle_reg_number
- violation_code
- violation_description
- amount_due (numeric, or null)
- payment_status
- payment_due_date
- officer_id
- issuing_date

Text:
{text}

JSON:"""

        return self._call_llm(prompt)

    def _extract_na_llm(self, text: str) -> Tuple[Dict[str, Any], int]:
        """
        Extract NA/Lease Permission fields using LLM.

        Expected fields:
        property_id, plot_number, owner_name, area, permission_date, expiry_date,
        authority, jurisdiction, restrictions (list), address, contact_info,
        approval_status, conditions, last_updated

        Args:
            text: Page text content

        Returns:
            Tuple of (extraction_dict, tokens_used)
        """
        prompt = f"""Extract property lease/permission information from this text.
Return ONLY valid JSON with these keys (null if not found, empty list for restrictions):
- property_id
- plot_number
- owner_name
- area (numeric, or null)
- permission_date
- expiry_date
- authority
- jurisdiction
- restrictions (array of strings)
- address
- contact_info
- approval_status
- conditions
- last_updated

Text:
{text}

JSON:"""

        return self._call_llm(prompt)

    def _extract_unknown_llm(self, text: str) -> Tuple[Dict[str, Any], int]:
        """
        Fallback extraction for unknown document types.

        Args:
            text: Page text content

        Returns:
            Tuple of (extraction_dict, tokens_used)
        """
        prompt = f"""Extract key-value information from this document.
Return ONLY valid JSON with extracted fields. Text:

{text}

JSON:"""

        return self._call_llm(prompt, tier="tier_5")

    def _call_llm(
        self, prompt: str, tier: str = "tier_4"
    ) -> Tuple[Dict[str, Any], int]:
        """
        Call Groq API and parse JSON response.

        Args:
            prompt: Prompt for LLM
            tier: Tier for token accounting

        Returns:
            Tuple of (parsed_json, tokens_used)
        """
        try:
            logger.info(f"Calling Groq API ({tier})")

            message = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for deterministic output
                max_tokens=500,
                response_format={"type": "json_object"},  # Force JSON response
            )

            # Extract response and token usage
            response_text = message.choices[0].message.content
            tokens_used = message.usage.completion_tokens + message.usage.prompt_tokens

            # Parse JSON response
            result = json.loads(response_text)

            logger.info(f"LLM response parsed - tokens: {tokens_used}")
            return result, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return {}, 0
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return {}, 0

    def get_token_summary(self) -> Dict[str, Any]:
        """
        Get token usage summary across all tiers.

        Returns:
            Dictionary with token counts per tier and total
        """
        return {
            "tier_1_skipped": self.token_usage["tier_1"],
            "tier_2_light_ocr": self.token_usage["tier_2"],
            "tier_3_classify": self.token_usage["tier_3"],
            "tier_4_llm_extraction": self.token_usage["tier_4"],
            "tier_5_fallback": self.token_usage["tier_5"],
            "tier_6_summary": self.token_usage["tier_6"],
            "total_tokens_used": self.token_usage["total"],
            "total_llm_calls": self.calls_made,
            "efficiency": f"{(self.token_usage['tier_1'] / (self.token_usage['total'] + 1)) * 100:.1f}% Tier 1 (0 tokens)",
        }

    def reset_token_tracking(self):
        """Reset token usage counters for new batch."""
        self.token_usage = {
            "tier_1": 0,
            "tier_2": 0,
            "tier_3": 0,
            "tier_4": 0,
            "tier_5": 0,
            "tier_6": 0,
            "total": 0,
        }
        self.calls_made = 0
        logger.info("Token tracking reset")
