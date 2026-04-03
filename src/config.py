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

# API Configuration (optional Groq for backup)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "compliance_clerk.log"

# Processing
CONFIDENCE_THRESHOLD = 0.75  # Skip LLM if confidence >= this
PDF_PAGE_TIMEOUT = 60  # seconds

# Context and Caching Configuration (from previous project)
MAX_RECENT = int(os.environ.get("MAX_RECENT", 200))
TOP_K = int(os.environ.get("TOP_K", 3))
AI_CONTEXT_LINES = int(os.environ.get("AI_CONTEXT_LINES", 8))
MAX_SUGGESTION_WORDS = int(os.environ.get("MAX_SUGGESTION_WORDS", 12))

# Model Configuration
MODEL_NAME = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
MODEL_CACHE_FOLDER = os.environ.get("MODEL_CACHE_FOLDER", "./models")

# Create model cache directory
Model_Cache_Dir = Path(MODEL_CACHE_FOLDER)
Model_Cache_Dir.mkdir(exist_ok=True)

# Token Limits (simplified)
TOKEN_LIMITS = {
    "tier1_deterministic": 0,      # No tokens (pattern matching)
    "tier2_semantic": 100,         # Semantic search
    "tier3_summary": 200,          # Summary generation
}
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 1024

# Database
SQLITE_DB = LOGS_DIR / "audit.db"
