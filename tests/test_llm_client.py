"""
Tests for LLM Client with mocked Groq API responses.
All tests use mocks to avoid consuming real API tokens.
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_client import LLMClient
from src.schemas import DocumentType


def test_llm_client_init():
    """Test LLM client initialization."""
    print("Running LLM Client tests...\n")

    with patch("src.llm_client.Groq"):
        client = LLMClient()
        assert client.model is not None
        assert client.confidence_threshold == 0.75
        assert client.calls_made == 0
        assert client.token_usage["total"] == 0
        print("[PASS] LLM Client initialized with correct settings")


def test_confidence_routing_high():
    """Test that LLM is skipped for high confidence."""
    with patch("src.llm_client.Groq"):
        client = LLMClient()

        # High confidence (0.85) should skip LLM
        should_call = client.should_use_llm(0.85)
        assert should_call is False
        print("[PASS] High confidence (0.85) routes to Tier 1 (no LLM)")


def test_confidence_routing_low():
    """Test that LLM is called for low confidence."""
    with patch("src.llm_client.Groq"):
        client = LLMClient()

        # Low confidence (0.50) should call LLM
        should_call = client.should_use_llm(0.50)
        assert should_call is True
        print("[PASS] Low confidence (0.50) routes to Tier 3-4 (LLM)")


def test_extract_with_fallback_tier_1():
    """Test Tier 1 path: deterministic result used, LLM skipped."""
    with patch("src.llm_client.Groq"):
        client = LLMClient()

        deterministic_result = {"challan_number": "CH123", "amount_due": 1000}
        text = "Sample text"

        result, confidence, tokens = client.extract_with_fallback(
            text=text,
            doc_type=DocumentType.ECHALLAN,
            deterministic_result=deterministic_result,
            deterministic_confidence=0.86,  # High confidence
        )

        assert result == deterministic_result
        assert confidence == 0.86
        assert tokens == 0
        assert client.calls_made == 0
        print("[PASS] Tier 1: Deterministic result used, 0 tokens, no LLM call")


def test_extract_with_fallback_tier_3_4_echallan():
    """Test Tier 3-4 path: LLM called for eChallan with low confidence."""
    mock_response = {
        "challan_number": "CH456",
        "amount_due": 2000,
        "payment_status": "pending",
    }

    with patch("src.llm_client.Groq") as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        # Mock Groq response
        mock_message = MagicMock()
        mock_message.choices[0].message.content = json.dumps(mock_response)
        mock_message.usage.completion_tokens = 45
        mock_message.usage.prompt_tokens = 80
        mock_client.chat.completions.create.return_value = mock_message

        client = LLMClient()
        client.client = mock_client

        text = "Low confidence text"
        result, confidence, tokens = client.extract_with_fallback(
            text=text,
            doc_type=DocumentType.ECHALLAN,
            deterministic_result={},
            deterministic_confidence=0.50,  # Low confidence
        )

        assert result["challan_number"] == "CH456"
        assert tokens == 125  # 45 + 80
        assert client.calls_made == 1
        assert client.token_usage["tier_4"] == 125
        print("[PASS] Tier 3-4: LLM called for eChallan, 125 tokens used, confidence combined")


def test_extract_with_fallback_tier_3_4_na_permission():
    """Test Tier 3-4 path: LLM called for NA Permission with low confidence."""
    mock_response = {
        "property_id": "PROP789",
        "owner_name": "John Doe",
        "area": 5000,
        "restrictions": ["No commercial use"],
    }

    with patch("src.llm_client.Groq") as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        mock_message = MagicMock()
        mock_message.choices[0].message.content = json.dumps(mock_response)
        mock_message.usage.completion_tokens = 60
        mock_message.usage.prompt_tokens = 110
        mock_client.chat.completions.create.return_value = mock_message

        client = LLMClient()
        client.client = mock_client

        text = "Low confidence NA permission text"
        result, confidence, tokens = client.extract_with_fallback(
            text=text,
            doc_type=DocumentType.NA_PERMISSION,
            deterministic_result={},
            deterministic_confidence=0.40,  # Low confidence
        )

        assert result["property_id"] == "PROP789"
        assert result["restrictions"] == ["No commercial use"]
        assert tokens == 170  # 60 + 110
        assert client.calls_made == 1
        print("[PASS] Tier 3-4: LLM called for NA Permission, 170 tokens used")


def test_token_summary():
    """Test token usage summary generation."""
    with patch("src.llm_client.Groq") as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        mock_message = MagicMock()
        mock_message.choices[0].message.content = json.dumps({"test": "data"})
        mock_message.usage.completion_tokens = 30
        mock_message.usage.prompt_tokens = 70
        mock_client.chat.completions.create.return_value = mock_message

        client = LLMClient()
        client.client = mock_client

        # Call LLM once
        client.extract_with_fallback(
            text="Test",
            doc_type=DocumentType.ECHALLAN,
            deterministic_result={},
            deterministic_confidence=0.40,
        )

        summary = client.get_token_summary()

        assert summary["total_tokens_used"] == 100
        assert summary["total_llm_calls"] == 1
        assert summary["tier_4_llm_extraction"] == 100
        assert "efficiency" in summary
        print(f"[PASS] Token summary: {summary['total_tokens_used']} tokens, "
              f"{summary['total_llm_calls']} calls")


def test_token_tracking_multiple_calls():
    """Test token tracking across multiple LLM calls."""
    with patch("src.llm_client.Groq") as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        mock_message = MagicMock()
        mock_message.choices[0].message.content = json.dumps({"test": "data"})
        mock_message.usage.completion_tokens = 50
        mock_message.usage.prompt_tokens = 100
        mock_client.chat.completions.create.return_value = mock_message

        client = LLMClient()
        client.client = mock_client

        # Simulate 3 Tier 1 (no LLM) calls
        for i in range(3):
            client.extract_with_fallback(
                text=f"Text {i}",
                doc_type=DocumentType.ECHALLAN,
                deterministic_result={},
                deterministic_confidence=0.80,  # High, skip LLM
            )

        # Simulate 2 Tier 3-4 (LLM) calls
        for i in range(2):
            client.extract_with_fallback(
                text=f"Text {i}",
                doc_type=DocumentType.ECHALLAN,
                deterministic_result={},
                deterministic_confidence=0.40,  # Low, use LLM
            )

        summary = client.get_token_summary()

        assert summary["total_llm_calls"] == 2
        assert summary["tier_4_llm_extraction"] == 300  # 2 calls * 150 tokens
        assert summary["total_tokens_used"] == 300
        print(f"[PASS] Token tracking across mixed calls: {summary['total_llm_calls']} LLM calls, "
              f"{summary['tier_4_llm_extraction']} tier-4 tokens")


def test_reset_token_tracking():
    """Test token tracking reset."""
    with patch("src.llm_client.Groq"):
        client = LLMClient()
        client.token_usage["tier_4"] = 500
        client.token_usage["total"] = 500
        client.calls_made = 5

        client.reset_token_tracking()

        assert client.token_usage["total"] == 0
        assert client.calls_made == 0
        print("[PASS] Token tracking reset successful")


def test_confidence_merging():
    """Test confidence merging between deterministic and LLM results."""
    with patch("src.llm_client.Groq") as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        mock_message = MagicMock()
        mock_message.choices[0].message.content = json.dumps({"field": "value"})
        mock_message.usage.completion_tokens = 40
        mock_message.usage.prompt_tokens = 90
        mock_client.chat.completions.create.return_value = mock_message

        client = LLMClient()
        client.client = mock_client

        # Low deterministic confidence (0.50) + LLM (0.85) = avg 0.675
        _, combined_confidence, _ = client.extract_with_fallback(
            text="Test",
            doc_type=DocumentType.ECHALLAN,
            deterministic_result={},
            deterministic_confidence=0.50,
        )

        expected = (0.50 + 0.85) / 2
        assert abs(combined_confidence - expected) < 0.01
        print(f"[PASS] Confidence merging: 0.50 + 0.85 → {combined_confidence:.2f}")


def test_json_parse_error_handling():
    """Test graceful handling of malformed JSON from LLM."""
    with patch("src.llm_client.Groq") as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        mock_message = MagicMock()
        mock_message.choices[0].message.content = "Invalid JSON {corrupted"
        mock_message.usage.completion_tokens = 30
        mock_message.usage.prompt_tokens = 80
        mock_client.chat.completions.create.return_value = mock_message

        client = LLMClient()
        client.client = mock_client

        result, confidence, tokens = client.extract_with_fallback(
            text="Test",
            doc_type=DocumentType.ECHALLAN,
            deterministic_result={},
            deterministic_confidence=0.40,
        )

        assert result == {}  # Empty result on parse error
        assert tokens == 0  # Tokens not counted on error
        print("[PASS] Malformed JSON handled gracefully, returns empty result")


if __name__ == "__main__":
    test_llm_client_init()
    test_confidence_routing_high()
    test_confidence_routing_low()
    test_extract_with_fallback_tier_1()
    test_extract_with_fallback_tier_3_4_echallan()
    test_extract_with_fallback_tier_3_4_na_permission()
    test_token_summary()
    test_token_tracking_multiple_calls()
    test_reset_token_tracking()
    test_confidence_merging()
    test_json_parse_error_handling()

    print("\n[SUCCESS] All LLM Client tests passed!")
