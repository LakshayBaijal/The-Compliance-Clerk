"""
Configuration management for The Compliance Clerk.
Loads environment variables and manages system-wide settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Directories
LOGS_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"

# Create directories
LOGS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set in .env file")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "compliance_clerk.log"

# Processing
CONFIDENCE_THRESHOLD = 0.75  # Skip LLM if confidence >= this
PDF_PAGE_TIMEOUT = 60  # seconds

# Token Limits (6-tier strategy)
TOKEN_LIMITS = {
    "tier1_deterministic": 0,      # No tokens (pattern matching)
    "tier2_ocr": 200,              # OCR + simple validation
    "tier3_classifier": 150,       # Classification
    "tier4_routing": 100,          # Route-specific extraction
    "tier5_fallback": 1000,        # Full extraction
    "tier6_summary": 500,          # Summary generation
}

# LLM Configuration
LLM_MODEL = "llama3-8b-8192"  # Standard model available on Groq
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 1024

# Database
SQLITE_DB = LOGS_DIR / "audit.db"
