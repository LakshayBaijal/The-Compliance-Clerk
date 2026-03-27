"""
Unit tests for config and logger modules.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    GROQ_API_KEY, LOGS_DIR, OUTPUT_DIR, DATA_DIR,
    CONFIDENCE_THRESHOLD, TOKEN_LIMITS, LLM_MODEL
)
from src.logger import get_logger


def test_config_directories():
    """Test that directories are created."""
    assert LOGS_DIR.exists(), "logs/ should exist"
    assert OUTPUT_DIR.exists(), "output/ should exist"
    assert DATA_DIR.exists(), "data/ should exist"
    print("[PASS] Directories created correctly")


def test_config_values():
    """Test that configuration values are set."""
    assert GROQ_API_KEY, "GROQ_API_KEY should be set"
    assert CONFIDENCE_THRESHOLD == 0.75
    # LLM model can be either mixtral or llama3 (both supported)
    assert LLM_MODEL in ["mixtral-8x7b-32768", "llama3-8b-8192"], f"Unexpected LLM model: {LLM_MODEL}"
    assert isinstance(TOKEN_LIMITS, dict)
    assert len(TOKEN_LIMITS) == 6
    print("[PASS] Config values correct")


def test_logger_initialization():
    """Test that logger initializes."""
    logger = get_logger("test_module")
    assert logger is not None
    assert logger.name == "test_module"
    assert len(logger.handlers) > 0
    print("[PASS] Logger initialized")


def test_logger_can_log():
    """Test that logger can write messages."""
    logger = get_logger("test_logging")
    logger.info("Test message")
    logger.debug("Debug message")
    logger.warning("Warning message")
    print("[PASS] Logger can write messages")


if __name__ == "__main__":
    print("Running config and logger tests...\n")
    test_config_directories()
    test_config_values()
    test_logger_initialization()
    test_logger_can_log()
    print("\n[SUCCESS] All tests passed!")
