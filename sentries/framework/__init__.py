"""
Reusable Agentic Framework extracted from CAMEL implementation.

This framework provides abstract base classes and patterns for building
multi-agent workflows for any domain, not just test fixing.
"""

from .agents import AgentConfig, AgentRole, BaseAgent
from .coordinators import BaseCoordinator, WorkflowConfig, WorkflowStep
from .error_recovery import ErrorCategory, ErrorRecoverySystem
from .llm import BaseLLMWrapper, LLMConfig
from .observability import AgentLogger, WorkflowObserver
from .tools import BaseTool, ToolRegistry
from .workflows import WorkflowBuilder, WorkflowEngine

__version__ = "0.1.0"

__all__ = [
    # Core abstractions
    "BaseAgent",
    "BaseCoordinator",
    "BaseTool",
    "BaseLLMWrapper",
    # Configuration
    "AgentConfig",
    "WorkflowConfig",
    "LLMConfig",
    "AgentRole",
    "WorkflowStep",
    # Systems
    "ToolRegistry",
    "ErrorRecoverySystem",
    "ErrorCategory",
    "WorkflowObserver",
    "AgentLogger",
    # Workflow engine
    "WorkflowBuilder",
    "WorkflowEngine",
    # Metadata
    "__version__",
]
