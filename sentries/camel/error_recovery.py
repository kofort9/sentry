#!/usr/bin/env python3
"""
Enhanced Error Recovery System for CAMEL Multi-Agent Workflow.

Provides intelligent error recovery, retry mechanisms, and user-friendly
error reporting for the Streamlit dashboard.
"""

import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..runner_common import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better classification and recovery."""

    NETWORK = "network"
    MODEL = "model"
    VALIDATION = "validation"
    PARSING = "parsing"
    CONFIGURATION = "configuration"
    WORKFLOW = "workflow"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """Structured error information for tracking and recovery."""

    timestamp: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: str
    context: Dict[str, Any]
    recovery_attempted: bool = False
    recovery_successful: bool = False
    retry_count: int = 0
    max_retries: int = 3


class ErrorRecoverySystem:
    """
    Enhanced error recovery system with intelligent retry logic,
    error classification, and user-friendly reporting.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_history: List[ErrorInfo] = []
        self.recovery_strategies: Dict[ErrorCategory, Callable] = {
            ErrorCategory.NETWORK: self._recover_network_error,
            ErrorCategory.MODEL: self._recover_model_error,
            ErrorCategory.VALIDATION: self._recover_validation_error,
            ErrorCategory.PARSING: self._recover_parsing_error,
            ErrorCategory.CONFIGURATION: self._recover_configuration_error,
            ErrorCategory.WORKFLOW: self._recover_workflow_error,
            ErrorCategory.RESOURCE: self._recover_resource_error,
        }

    def classify_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        Classify an error and determine its category and severity.

        Args:
            error: The exception that occurred
            context: Additional context about when/where the error occurred

        Returns:
            ErrorInfo object with classification details
        """
        context = context or {}
        error_message = str(error)
        error_type = type(error).__name__

        # Classify by error patterns
        category = ErrorCategory.UNKNOWN
        severity = ErrorSeverity.MEDIUM

        # Network-related errors
        if any(
            keyword in error_message.lower()
            for keyword in ["connection", "timeout", "network", "unreachable", "dns"]
        ):
            category = ErrorCategory.NETWORK
            severity = ErrorSeverity.HIGH

        # Model/LLM-related errors
        elif any(
            keyword in error_message.lower()
            for keyword in ["model", "llm", "api", "openai", "anthropic", "groq", "ollama"]
        ):
            category = ErrorCategory.MODEL
            severity = ErrorSeverity.HIGH

        # Validation errors
        elif any(
            keyword in error_message.lower()
            for keyword in ["validation", "invalid", "format", "schema"]
        ):
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.MEDIUM

        # Parsing errors
        elif any(
            keyword in error_type.lower() for keyword in ["json", "parse", "decode", "syntax"]
        ):
            category = ErrorCategory.PARSING
            severity = ErrorSeverity.MEDIUM

        # Configuration errors
        elif any(
            keyword in error_message.lower()
            for keyword in ["config", "environment", "missing", "not found"]
        ):
            category = ErrorCategory.CONFIGURATION
            severity = ErrorSeverity.HIGH

        # Resource errors
        elif any(
            keyword in error_message.lower()
            for keyword in ["memory", "disk", "resource", "limit", "quota"]
        ):
            category = ErrorCategory.RESOURCE
            severity = ErrorSeverity.HIGH

        # Workflow-specific errors
        elif "camel" in error_message.lower() or "workflow" in error_message.lower():
            category = ErrorCategory.WORKFLOW
            severity = ErrorSeverity.MEDIUM

        error_info = ErrorInfo(
            timestamp=datetime.now().isoformat(),
            category=category,
            severity=severity,
            message=error_message,
            details=traceback.format_exc(),
            context=context,
        )

        self.error_history.append(error_info)
        logger.error(f"Classified error: {category.value} ({severity.value}) - {error_message}")

        return error_info

    def attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """
        Attempt to recover from an error using category-specific strategies.

        Args:
            error_info: The error information to recover from

        Returns:
            True if recovery was successful, False otherwise
        """
        if error_info.retry_count >= self.max_retries:
            logger.warning(
                f"Max retries ({self.max_retries}) reached for error: {error_info.message}"
            )
            return False

        error_info.recovery_attempted = True
        error_info.retry_count += 1

        attempt_msg = (
            f"Attempting recovery for {error_info.category.value} error "
            f"(attempt {error_info.retry_count})"
        )
        logger.info(attempt_msg)

        # Get recovery strategy for this error category
        recovery_func = self.recovery_strategies.get(
            error_info.category, self._recover_generic_error
        )

        try:
            success = recovery_func(error_info)
            error_info.recovery_successful = success

            if success:
                logger.info(f"✅ Recovery successful for {error_info.category.value} error")
            else:
                logger.warning(f"❌ Recovery failed for {error_info.category.value} error")

            return success

        except Exception as recovery_error:
            logger.error(f"Recovery attempt itself failed: {recovery_error}")
            return False

    def _recover_network_error(self, error_info: ErrorInfo) -> bool:
        """Recover from network-related errors."""
        logger.info("🌐 Attempting network error recovery...")

        # Wait longer for network issues
        time.sleep(self.retry_delay * 2)

        # For network errors, we mostly just retry with exponential backoff
        if error_info.retry_count > 1:
            backoff_delay = self.retry_delay * (2 ** (error_info.retry_count - 1))
            logger.info(f"Network retry with backoff delay: {backoff_delay}s")
            time.sleep(backoff_delay)

        return True  # Network issues are often transient

    def _recover_model_error(self, error_info: ErrorInfo) -> bool:
        """Recover from model/LLM-related errors."""
        logger.info("🤖 Attempting model error recovery...")

        # Check if it's a rate limiting issue
        if "rate" in error_info.message.lower() or "limit" in error_info.message.lower():
            wait_time = min(30, self.retry_delay * (2**error_info.retry_count))
            logger.info(f"Rate limit detected, waiting {wait_time}s")
            time.sleep(wait_time)
            return True

        # Check if it's a context length issue
        if "context" in error_info.message.lower() or "length" in error_info.message.lower():
            logger.info("Context length issue detected - this may require input truncation")
            # In a real implementation, we'd signal to truncate the input
            return False

        # For other model errors, try a simple retry
        time.sleep(self.retry_delay)
        return True

    def _recover_validation_error(self, error_info: ErrorInfo) -> bool:
        """Recover from validation errors."""
        logger.info("✅ Attempting validation error recovery...")

        # Validation errors might be recoverable if the agent can self-correct
        # This is handled by the PatcherAgent's iterative validation loop
        return True

    def _recover_parsing_error(self, error_info: ErrorInfo) -> bool:
        """Recover from parsing errors."""
        logger.info("📝 Attempting parsing error recovery...")

        # JSON parsing errors might be recoverable with prompt improvements
        # The PatcherAgent has robust JSON extraction logic for this
        return True

    def _recover_configuration_error(self, error_info: ErrorInfo) -> bool:
        """Recover from configuration errors."""
        logger.info("⚙️ Attempting configuration error recovery...")

        # Configuration errors usually require user intervention
        return False

    def _recover_workflow_error(self, error_info: ErrorInfo) -> bool:
        """Recover from workflow-specific errors."""
        logger.info("🔄 Attempting workflow error recovery...")

        # Workflow errors might be recoverable depending on the specific issue
        time.sleep(self.retry_delay)
        return True

    def _recover_resource_error(self, error_info: ErrorInfo) -> bool:
        """Recover from resource-related errors."""
        logger.info("💾 Attempting resource error recovery...")

        # Resource errors usually require waiting or cleanup
        time.sleep(self.retry_delay * 3)  # Wait longer for resources
        return True

    def _recover_generic_error(self, error_info: ErrorInfo) -> bool:
        """Generic recovery strategy for unknown errors."""
        logger.info("🔧 Attempting generic error recovery...")

        # Simple retry with delay
        time.sleep(self.retry_delay)
        return True

    def with_recovery(
        self,
        operation: Callable,
        context: Dict[str, Any] = None,
        custom_max_retries: Optional[int] = None,
    ) -> Any:
        """
        Execute an operation with automatic error recovery.

        Args:
            operation: The operation to execute
            context: Additional context for error classification
            custom_max_retries: Override the default max retries for this operation

        Returns:
            The result of the operation if successful

        Raises:
            The last exception if all recovery attempts fail
        """
        max_retries = custom_max_retries or self.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return operation()
            except Exception as e:
                last_error = e

                if attempt == max_retries:
                    # Final attempt failed
                    error_info = self.classify_error(e, context)
                    logger.error(f"Operation failed after {max_retries + 1} attempts: {e}")
                    raise e

                # Classify and attempt recovery
                error_info = self.classify_error(e, context)

                if not self.attempt_recovery(error_info):
                    # Recovery not possible or failed
                    logger.error(f"Recovery not possible for error: {e}")
                    raise e

                logger.info(f"Retrying operation (attempt {attempt + 2}/{max_retries + 1})")

        # This should never be reached, but just in case
        if last_error:
            raise last_error

    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get a summary of error history for dashboard display.

        Returns:
            Dictionary with error statistics and recent errors
        """
        if not self.error_history:
            return {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "recent_errors": [],
                "recovery_rate": 0.0,
            }

        # Count by category
        by_category: Dict[str, int] = {}
        for error in self.error_history:
            category = error.category.value
            by_category[category] = by_category.get(category, 0) + 1

        # Count by severity
        by_severity: Dict[str, int] = {}
        for error in self.error_history:
            severity = error.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # Calculate recovery rate
        recovery_attempts = sum(1 for e in self.error_history if e.recovery_attempted)
        successful_recoveries = sum(1 for e in self.error_history if e.recovery_successful)
        recovery_rate = (
            (successful_recoveries / recovery_attempts) if recovery_attempts > 0 else 0.0
        )

        # Get recent errors (last 10)
        recent_errors = [asdict(error) for error in self.error_history[-10:]]

        return {
            "total_errors": len(self.error_history),
            "by_category": by_category,
            "by_severity": by_severity,
            "recent_errors": recent_errors,
            "recovery_rate": recovery_rate,
            "recovery_attempts": recovery_attempts,
            "successful_recoveries": successful_recoveries,
        }

    def clear_history(self):
        """Clear the error history."""
        self.error_history.clear()
        logger.info("Error history cleared")


# Global error recovery instance
global_error_recovery = ErrorRecoverySystem()


def with_error_recovery(context: Dict[str, Any] = None):
    """
    Decorator for adding error recovery to functions.

    Args:
        context: Additional context for error classification
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            return global_error_recovery.with_recovery(lambda: func(*args, **kwargs), context)

        return wrapper

    return decorator
