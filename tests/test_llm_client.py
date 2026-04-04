"""Tests for embedding-based LLM client behavior."""

import sys
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_client import LLMClient
from src.schemas import DocumentType


def _client_without_model() -> LLMClient:
    client = LLMClient()
    client.embedder = None
    client.model = "test-model"
    return client


def test_llm_client_init():
    client = _client_without_model()
    assert client.model == "test-model"
    assert client.confidence_threshold == 0.75
    assert client.search_calls == 0
    assert client.total_results == 0


def test_confidence_routing_high():
    client = _client_without_model()
    assert client.should_use_llm(0.85) is False


def test_confidence_routing_low():
    client = _client_without_model()
    assert client.should_use_llm(0.50) is True


def test_extract_with_fallback_tier_1_returns_deterministic():
    client = _client_without_model()
    deterministic_result = {"challan_number": "CH123", "amount_due": 1000}

    result, confidence, tokens = client.extract_with_fallback(
        text="Sample text",
        doc_type=DocumentType.ECHALLAN,
        deterministic_result=deterministic_result,
        deterministic_confidence=0.86,
    )

    assert result == deterministic_result
    assert confidence == 0.86
    assert tokens == 0


def test_extract_with_fallback_low_confidence_uses_semantic_echallan():
    client = _client_without_model()

    def fake_matches(query, candidates, top_k=None):
        if "ticket" in query:
            return [("Challan No 12345", 0.9)]
        if "fine" in query or "amount" in query:
            return [("Fine amount 2500", 0.9)]
        return []

    with patch.object(client, "get_semantic_matches", side_effect=fake_matches):
        result, confidence, tokens = client.extract_with_fallback(
            text="Challan No 12345\nFine amount 2500",
            doc_type=DocumentType.ECHALLAN,
            deterministic_result={},
            deterministic_confidence=0.40,
        )

    assert result.get("challan_number") == "12345"
    assert result.get("amount_due") == 2500.0
    assert tokens > 0
    assert confidence > 0.40


def test_extract_with_fallback_low_confidence_uses_semantic_na_permission():
    client = _client_without_model()

    def fake_matches(query, candidates, top_k=None):
        if "owner" in query:
            return [("Owner Name John Doe", 0.92)]
        if "survey" in query or "plot" in query:
            return [("Survey No 456", 0.88)]
        return []

    with patch.object(client, "get_semantic_matches", side_effect=fake_matches):
        result, confidence, tokens = client.extract_with_fallback(
            text="Owner Name John Doe\nSurvey No 456",
            doc_type=DocumentType.NA_PERMISSION,
            deterministic_result={},
            deterministic_confidence=0.35,
        )

    assert result.get("owner_name") == "Owner Name John Doe"
    assert result.get("plot_number") == "456"
    assert tokens > 0
    assert confidence > 0


def test_get_token_summary_reports_search_stats():
    client = _client_without_model()
    client.search_calls = 3
    client.total_results = 9

    summary = client.get_token_summary()

    assert summary["search_calls"] == 3
    assert summary["total_results_found"] == 9
    assert summary["avg_results_per_call"] == 3


def test_reset_tracking():
    client = _client_without_model()
    client.search_calls = 5
    client.total_results = 11

    client.reset_tracking()

    assert client.search_calls == 0
    assert client.total_results == 0


def test_schema_enforcement_on_echallan_drops_unknown_fields():
    client = _client_without_model()
    payload = {
        "challan_number": "CH-789",
        "amount_due": 999,
        "unknown": "value",
    }

    result = client._enforce_schema(DocumentType.ECHALLAN, payload)
    assert result["challan_number"] == "CH-789"
    assert result["amount_due"] == 999
    assert "unknown" not in result
