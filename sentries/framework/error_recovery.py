"""
Error recovery system for the reusable framework.

This is a simplified version adapted from the existing error recovery system
to work with the generic framework.
"""

import datetime
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List


class ErrorCategory(Enum):
    """Categories of errors for classification."""

    NETWORK = "network"
    MODEL = "model"
    VALIDATION = "validation"
    PARSING = "parsing"
    CONFIGURATION = "configuration"
    WORKFLOW = "workflow"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorInfo:
    """Information about an error occurrence."""

    timestamp: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception_type: str
    context: Dict[str, Any]

    recovery_attempted: bool = False
    recovery_successful: bool = False
    retry_count: int = 0
    max_retries: int = 3


class ErrorRecoverySystem:
    """
    Generic error recovery system with classification and retry logic.

    Provides intelligent error handling with category-specific recovery strategies.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_history: List[ErrorInfo] = []

        # Recovery strategies by category
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
        """Classify an error into category and severity."""
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Determine category
        category = ErrorCategory.UNKNOWN
        severity = ErrorSeverity.MEDIUM

        # Network-related errors
        if any(keyword in error_str for keyword in ["connection", "timeout", "network", "http"]):
            category = ErrorCategory.NETWORK
            severity = ErrorSeverity.HIGH

        # Model/LLM-related errors
        elif any(keyword in error_str for keyword in ["model", "api key", "rate limit", "quota"]):
            category = ErrorCategory.MODEL
            severity = ErrorSeverity.HIGH

        # Validation errors
        elif any(keyword in error_str for keyword in ["validation", "invalid", "missing"]):
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.MEDIUM

        # Parsing errors
        elif any(keyword in error_str for keyword in ["json", "parse", "decode", "format"]):
            category = ErrorCategory.PARSING
            severity = ErrorSeverity.MEDIUM

        # Configuration errors
        elif any(keyword in error_str for keyword in ["config", "setting", "parameter"]):
            category = ErrorCategory.CONFIGURATION
            severity = ErrorSeverity.HIGH

        # Resource errors
        elif any(keyword in error_str for keyword in ["memory", "disk", "file not found"]):
            category = ErrorCategory.RESOURCE
            severity = ErrorSeverity.HIGH

        # Workflow errors
        elif any(keyword in error_str for keyword in ["workflow", "step", "agent"]):
            category = ErrorCategory.WORKFLOW
            severity = ErrorSeverity.MEDIUM

        # Critical system errors
        if error_type in ["SystemExit", "KeyboardInterrupt", "MemoryError"]:
            severity = ErrorSeverity.CRITICAL

        return ErrorInfo(
            timestamp=datetime.datetime.now().isoformat(),
            category=category,
            severity=severity,
            message=str(error),
            exception_type=error_type,
            context=context or {},
        )

    def with_recovery(
        self, func: Callable, context: Dict[str, Any] = None, custom_max_retries: int = None
    ) -> Any:
        """
        Execute function with automatic error recovery.

        Args:
            func: Function to execute
            context: Additional context for error handling
            custom_max_retries: Override default max retries

        Returns:
            Result of successful function execution
        """
        max_attempts = custom_max_retries or self.max_retries
        last_error_info = None

        for attempt in range(max_attempts + 1):  # +1 for initial attempt
            try:
                return func()

            except Exception as e:
                error_info = self.classify_error(e, context)
                error_info.retry_count = attempt
                error_info.max_retries = max_attempts

                # Record error
                self.error_history.append(error_info)
                last_error_info = error_info

                # Don't retry critical errors
                if error_info.severity == ErrorSeverity.CRITICAL:
                    break

                # Don't retry on last attempt
                if attempt >= max_attempts:
                    break

                # Attempt recovery
                try:
                    error_info.recovery_attempted = True
                    recovery_strategy = self.recovery_strategies.get(error_info.category)

                    if recovery_strategy:
                        recovery_result = recovery_strategy(error_info, context)
                        error_info.recovery_successful = recovery_result

                        if recovery_result:
                            # Wait before retry
                            time.sleep(self.retry_delay * (2**attempt))  # Exponential backoff
                            continue

                except Exception as recovery_error:
                    # Recovery itself failed
                    error_info.recovery_successful = False
                    error_info.context["recovery_error"] = str(recovery_error)

                # Wait before retry
                time.sleep(self.retry_delay * (2**attempt))

        # All attempts failed
        if last_error_info:
            raise RuntimeError(
                f"Operation failed after {max_attempts + 1} attempts. "
                f"Last error: {last_error_info.message}"
            )
        else:
            raise RuntimeError("Operation failed with unknown error")

    def _recover_network_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """Attempt to recover from network errors."""
        # Simple recovery - just wait and retry
        time.sleep(2.0)
        return True

    def _recover_model_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """Attempt to recover from model/LLM errors."""
        # Could implement fallback to different models, reduced parameters, etc.
        if "rate limit" in error_info.message.lower():
            time.sleep(5.0)  # Wait longer for rate limits
            return True
        return False

    def _recover_validation_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """Attempt to recover from validation errors."""
        # Could implement more lenient validation, default values, etc.
        return False  # Usually can't auto-recover from validation errors

    def _recover_parsing_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """Attempt to recover from parsing errors."""
        # Could implement alternative parsing strategies
        return False

    def _recover_configuration_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """Attempt to recover from configuration errors."""
        # Could implement fallback configurations
        return False

    def _recover_workflow_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """Attempt to recover from workflow errors."""
        # Could implement alternative workflow paths
        return False

    def _recover_resource_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """Attempt to recover from resource errors."""
        # Could implement cleanup, alternative resources, etc.
        return False

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error recovery status."""
        total_errors = len(self.error_history)
        if total_errors == 0:
            return {"total_errors": 0, "recovery_rate": 0.0}

        successful_recoveries = sum(1 for e in self.error_history if e.recovery_successful)
        recovery_attempts = sum(1 for e in self.error_history if e.recovery_attempted)

        # Group by category and severity
        by_category = {}
        by_severity = {}

        for error in self.error_history:
            category = error.category.value
            severity = error.severity.value

            if category not in by_category:
                by_category[category] = 0
            by_category[category] += 1

            if severity not in by_severity:
                by_severity[severity] = 0
            by_severity[severity] += 1

        return {
            "total_errors": total_errors,
            "recovery_attempts": recovery_attempts,
            "successful_recoveries": successful_recoveries,
            "recovery_rate": (
                successful_recoveries / recovery_attempts if recovery_attempts > 0 else 0.0
            ),
            "by_category": by_category,
            "by_severity": by_severity,
            "error_history": [
                {
                    "timestamp": e.timestamp,
                    "category": e.category.value,
                    "severity": e.severity.value,
                    "message": e.message[:100] + "..." if len(e.message) > 100 else e.message,
                    "recovery_attempted": e.recovery_attempted,
                    "recovery_successful": e.recovery_successful,
                    "retry_count": e.retry_count,
                }
                for e in self.error_history[-10:]  # Last 10 errors
            ],
        }

    def clear_history(self):
        """Clear error history."""
        self.error_history.clear()

    def add_recovery_strategy(self, category: ErrorCategory, strategy: Callable):
        """Add custom recovery strategy for an error category."""
        self.recovery_strategies[category] = strategy

    def get_error_stats(self) -> Dict[str, Any]:
        """Get detailed error statistics."""
        if not self.error_history:
            return {"message": "No errors recorded"}

        recent_errors = self.error_history[-5:]

        return {
            "total_errors": len(self.error_history),
            "recent_errors": [
                {
                    "timestamp": e.timestamp,
                    "category": e.category.value,
                    "severity": e.severity.value,
                    "message": e.message,
                    "recovery_attempted": e.recovery_attempted,
                    "recovery_successful": e.recovery_successful,
                }
                for e in recent_errors
            ],
            "summary": self.get_error_summary(),
        }
