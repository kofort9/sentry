#!/usr/bin/env python3
"""
Compatibility layer for CAMEL multi-agent components.

The actual implementations now live under sentries/camel/*.py to keep the codebase
modular. Importing from sentries.camel_agents continues to work for downstream
callers during the transition period.
"""

from .camel import (
    CAMELCoordinator,
    GitOperationsTool,
    PatcherAgent,
    PatchGenerationTool,
    PatchValidationTool,
    PlannerAgent,
    SentryLLMWrapper,
    TestAnalysisTool,
)

__all__ = [
    "CAMELCoordinator",
    "GitOperationsTool",
    "PatchGenerationTool",
    "PatchValidationTool",
    "PlannerAgent",
    "PatcherAgent",
    "SentryLLMWrapper",
    "TestAnalysisTool",
]
