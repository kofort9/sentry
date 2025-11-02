#!/usr/bin/env python3
"""
Intelligent test failure analysis for smarter TestSentry.

This module provides:
1. Failure classification based on pytest output patterns
2. Smart context extraction tailored to each failure type
3. AST-aware "find" string generation for precise matching
4. Budget-controlled context packs to stay within token limits
"""

import ast
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from .runner_common import get_logger

logger = get_logger(__name__)


class FailureType(Enum):
    """Classification of test failure types."""

    ASSERT_MISMATCH = "assert_mismatch"
    IMPORT_ERROR = "import_error"
    FIXTURE_MISSING = "fixture_missing"
    TYPE_ERROR = "type_error"
    TIMEOUT = "timeout"
    FLAKE = "flake"
    NAME_ERROR = "name_error"
    ATTRIBUTE_ERROR = "attribute_error"
    OTHER = "other"


@dataclass
class FailureInfo:
    """Information about a specific test failure."""

    test_file: str
    test_function: str
    failure_type: FailureType
    error_message: str
    traceback_lines: List[str]
    failing_line: Optional[str] = None
    specific_details: Optional[Dict] = None


@dataclass
class ContextPack:
    """Smart context pack tailored to a specific failure type."""

    failure_info: FailureInfo
    context_size: int
    context_parts: List[str]
    find_candidates: List[str]  # AST-generated find strings


class FailureClassifier:
    """Classifies test failures into specific types for targeted fixes."""

    # Regex patterns for different failure types
    PATTERNS = {
        FailureType.ASSERT_MISMATCH: [
            r"AssertionError",
            r"assert .+ == .+",
            r"assert .+ != .+",
            r"assert .+ is .+",
            r"assert .+ in .+",
            r"assert .+ < .+",
            r"assert .+ > .+",
        ],
        FailureType.IMPORT_ERROR: [
            r"ImportError",
            r"ModuleNotFoundError",
            r"No module named",
            r"cannot import name",
        ],
        FailureType.FIXTURE_MISSING: [
            r"fixture .+ not found",
            r"@pytest\.fixture",
            r"fixture.*undefined",
        ],
        FailureType.TYPE_ERROR: [
            r"TypeError",
            r"'.*' object has no attribute",
            r"unsupported operand type",
        ],
        FailureType.NAME_ERROR: [
            r"NameError",
            r"name .+ is not defined",
        ],
        FailureType.ATTRIBUTE_ERROR: [
            r"AttributeError",
            r"'.*' object has no attribute",
        ],
        FailureType.TIMEOUT: [
            r"TimeoutError",
            r"timeout",
            r"Timeout",
        ],
    }

    def classify_failure(self, pytest_output: str) -> List[FailureInfo]:
        """
        Classify failures from pytest output.

        Args:
            pytest_output: Raw pytest output with failures

        Returns:
            List of classified failure information
        """
        failures = []
        lines = pytest_output.split("\n")

        current_failure = None
        traceback_lines: List[str] = []
        in_traceback = False

        for line in lines:
            # Look for test failure headers like "FAILED tests/test_file.py::test_function"
            if "FAILED " in line and "::" in line:
                # Save previous failure if exists
                if current_failure:
                    current_failure.traceback_lines = traceback_lines
                    failures.append(current_failure)

                # Start new failure
                parts = line.split("FAILED ")[1].split("::")
                if len(parts) >= 2:
                    test_file = parts[0].strip()
                    test_function = parts[1].split(" ")[0].strip()

                    current_failure = FailureInfo(
                        test_file=test_file,
                        test_function=test_function,
                        failure_type=FailureType.OTHER,
                        error_message="",
                        traceback_lines=[],
                    )
                    traceback_lines = []
                    in_traceback = False

            # Look for error messages and classify
            elif current_failure and any(
                keyword in line for keyword in ["Error", "assert", "E   "]
            ):
                if not current_failure.error_message:
                    current_failure.error_message = line.strip()

                # Classify based on error content
                for failure_type, patterns in self.PATTERNS.items():
                    if any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns):
                        current_failure.failure_type = failure_type
                        break

                # Track traceback
                if line.strip().startswith("E   ") or ">" in line:
                    in_traceback = True
                    traceback_lines.append(line.strip())

                    # Extract failing line
                    if ">" in line and not current_failure.failing_line:
                        current_failure.failing_line = line.strip()

            elif in_traceback and line.strip():
                traceback_lines.append(line.strip())
            elif not line.strip():
                in_traceback = False

        # Save last failure
        if current_failure:
            current_failure.traceback_lines = traceback_lines
            failures.append(current_failure)

        logger.info(
            f"Classified {len(failures)} failures: {[f.failure_type.value for f in failures]}"
        )
        return failures


class SmartContextExtractor:
    """Extracts targeted context based on failure type."""

    MAX_CONTEXT_SIZE = 6000  # ~6KB budget

    def __init__(self):
        self.classifier = FailureClassifier()

    def extract_context_pack(self, failure_info: FailureInfo) -> ContextPack:
        """
        Extract smart context pack for a specific failure.

        Args:
            failure_info: Classified failure information

        Returns:
            ContextPack with targeted context and find candidates
        """
        context_parts = []
        find_candidates = []

        # Always include: failing test function + failure message
        test_function_code = self._extract_test_function(
            failure_info.test_file, failure_info.test_function
        )
        if test_function_code:
            context_parts.append(f"=== Test Function: {failure_info.test_function} ===")
            context_parts.append(test_function_code)

            # Generate AST-aware find candidates
            find_candidates.extend(self._generate_find_candidates(test_function_code))

        # Add failure-specific context
        if failure_info.failure_type == FailureType.ASSERT_MISMATCH:
            assert_context = self._extract_assert_context(failure_info)
            if assert_context:
                context_parts.append("=== Assert Context ===")
                context_parts.append(assert_context)

        elif failure_info.failure_type == FailureType.IMPORT_ERROR:
            import_context = self._extract_import_context(failure_info)
            if import_context:
                context_parts.append("=== Import Context ===")
                context_parts.append(import_context)

        elif failure_info.failure_type == FailureType.FIXTURE_MISSING:
            fixture_context = self._extract_fixture_context(failure_info)
            if fixture_context:
                context_parts.append("=== Fixture Context ===")
                context_parts.append(fixture_context)

        # Add minimal failure info
        context_parts.append("=== Failure Info ===")
        context_parts.append(f"Error: {failure_info.error_message}")
        if failure_info.failing_line:
            context_parts.append(f"Failing line: {failure_info.failing_line}")

        # Apply budget control
        context_parts = self._apply_budget_control(context_parts)

        return ContextPack(
            failure_info=failure_info,
            context_size=sum(len(part) for part in context_parts),
            context_parts=context_parts,
            find_candidates=find_candidates,
        )

    def _extract_test_function(self, test_file: str, test_function: str) -> Optional[str]:
        """Extract just the failing test function code."""
        try:
            with open(test_file, "r") as f:
                content = f.read()

            # Parse AST to find the function
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == test_function:
                    # Get the function source
                    lines = content.split("\n")
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line + 10

                    function_lines = lines[start_line:end_line]
                    return "\n".join(function_lines)

        except Exception as e:
            logger.warning(f"Could not extract function {test_function} from {test_file}: {e}")

        return None

    def _extract_assert_context(self, failure_info: FailureInfo) -> Optional[str]:
        """Extract context around assertion failures."""
        if not failure_info.failing_line:
            return None

        try:
            with open(failure_info.test_file, "r") as f:
                lines = f.readlines()

            # Find the assert line
            for i, line in enumerate(lines):
                if "assert" in line and any(
                    part.strip() in line for part in failure_info.failing_line.split()
                ):
                    # Return ±6 lines around the assertion
                    start = max(0, i - 6)
                    end = min(len(lines), i + 7)
                    context_lines = lines[start:end]
                    return "".join(context_lines).strip()

        except Exception as e:
            logger.warning(f"Could not extract assert context: {e}")

        return None

    def _extract_import_context(self, failure_info: FailureInfo) -> Optional[str]:
        """Extract import-related context."""
        try:
            with open(failure_info.test_file, "r") as f:
                content = f.read()

            # Get all import lines from the top of the file
            lines = content.split("\n")
            import_lines = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    import_lines.append(line)
                elif stripped and not stripped.startswith("#") and import_lines:
                    # Stop at first non-import, non-comment line
                    break

            return "\n".join(import_lines) if import_lines else None

        except Exception as e:
            logger.warning(f"Could not extract import context: {e}")

        return None

    def _extract_fixture_context(self, failure_info: FailureInfo) -> Optional[str]:
        """Extract fixture definitions and imports."""
        # This would look for @pytest.fixture definitions in the file or conftest.py
        # For now, return minimal context
        try:
            with open(failure_info.test_file, "r") as f:
                content = f.read()

            # Look for fixture definitions
            lines = content.split("\n")
            fixture_lines = []

            in_fixture = False
            for line in lines:
                if "@pytest.fixture" in line:
                    in_fixture = True
                    fixture_lines.append(line)
                elif in_fixture:
                    fixture_lines.append(line)
                    if line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                        in_fixture = False

            return "\n".join(fixture_lines) if fixture_lines else None

        except Exception as e:
            logger.warning(f"Could not extract fixture context: {e}")

        return None

    def _generate_find_candidates(self, code: str) -> List[str]:
        """Generate AST-aware find candidates with normalized whitespace."""
        candidates = []

        try:
            # Parse the code
            tree = ast.parse(code)

            # Extract assert statements
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    # Get the assert statement text
                    lines = code.split("\n")
                    if hasattr(node, "lineno") and node.lineno <= len(lines):
                        assert_line = lines[node.lineno - 1].strip()
                        # Normalize whitespace
                        normalized = " ".join(assert_line.split())
                        candidates.append(normalized)

        except Exception as e:
            logger.warning(f"Could not generate AST candidates: {e}")

        return candidates

    def _apply_budget_control(self, context_parts: List[str]) -> List[str]:
        """Apply budget control to keep context under size limit."""
        total_size = sum(len(part) for part in context_parts)

        if total_size <= self.MAX_CONTEXT_SIZE:
            return context_parts

        # Trim from the end, keeping essential parts
        logger.info(f"Context too large ({total_size} chars), applying budget control")

        essential_parts = context_parts[:2]  # Keep test function and first context
        optional_parts = context_parts[2:]

        current_size = sum(len(part) for part in essential_parts)

        for part in optional_parts:
            if current_size + len(part) <= self.MAX_CONTEXT_SIZE:
                essential_parts.append(part)
                current_size += len(part)
            else:
                break

        logger.info(f"Trimmed context to {current_size} chars")
        return essential_parts


def create_smart_context(pytest_output: str) -> List[ContextPack]:
    """
    Create smart context packs from pytest output.

    Args:
        pytest_output: Raw pytest output with failures

    Returns:
        List of context packs, one per failure
    """
    extractor = SmartContextExtractor()
    failures = extractor.classifier.classify_failure(pytest_output)

    context_packs = []
    for failure in failures:
        pack = extractor.extract_context_pack(failure)
        context_packs.append(pack)

    return context_packs
