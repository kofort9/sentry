"""
Shared utilities for Sentries runners.
"""
import os
import logging
import sys
from typing import Optional

# Constants
TESTS_ALLOWLIST = ["tests/"]
DOCS_ALLOWLIST = ["README.md", "docs/", "CHANGELOG.md", "ARCHITECTURE.md", "ADR/", "openapi.yaml"]

# Environment variables
LLM_BASE = os.getenv("LLM_BASE", "http://127.0.0.1:11434")
MODEL_PLAN = os.getenv("MODEL_PLAN", "llama3.1:8b-instruct-q4_K_M")
MODEL_PATCH = os.getenv("MODEL_PATCH", "deepseek-coder:6.7b-instruct-q5_K_M")

# GitHub environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_REF = os.getenv("GITHUB_REF")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")

# Limits
MAX_TEST_FILES = 5
MAX_TEST_LINES = 200
MAX_DOC_FILES = 5
MAX_DOC_LINES = 300

def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

def validate_environment() -> bool:
    """Validate required environment variables."""
    if not GITHUB_TOKEN:
        logging.error("GITHUB_TOKEN environment variable is required")
        return False

    if not GITHUB_REPOSITORY:
        logging.error("GITHUB_REPOSITORY environment variable is required")
        return False

    return True

def get_short_sha() -> Optional[str]:
    """Extract short SHA from GITHUB_REF."""
    if not GITHUB_REF:
        return None

    # GITHUB_REF format: refs/heads/branch-name or refs/pull/123/merge
    if GITHUB_REF.startswith("refs/pull/"):
        # For pull requests, we'll use the event payload
        return None

    # For branches, extract the branch name and use as identifier
    return GITHUB_REF.replace("refs/heads/", "")[:8]

def exit_success(message: str = "Success") -> None:
    """Exit with success code and message."""
    print(f"✅ {message}")
    sys.exit(0)

def exit_noop(reason: str) -> None:
    """Exit with noop status."""
    print(f"⏭️  No-op: {reason}")
    sys.exit(0)

def exit_failure(message: str, exit_code: int = 1) -> None:
    """Exit with failure code and message."""
    print(f"❌ {message}")
    sys.exit(exit_code)
