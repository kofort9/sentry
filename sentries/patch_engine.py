#!/usr/bin/env python3
"""
Patch Engine: Converts JSON find/replace operations to unified diffs.

This module eliminates reliance on model-generated line numbers by:
1. Accepting position-independent find/replace operations
2. Building unified diffs locally using stdlib difflib
3. Enforcing strict guardrails and validation
4. Only allowing changes to tests/docs allowlist paths
"""

import json
import logging
from dataclasses import dataclass
from difflib import unified_diff
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Allowed paths for modifications (tests/, docs/, README.md)
ALLOWED_PATHS = {
    "tests/",
    "docs/",
    "README.md",
    "sentries/test_",
    "sentries/docsentry.py",
}

# Guardrails
MAX_FILES_CHANGED = 5
MAX_TOTAL_CHANGED_LINES = 200


@dataclass
class PatchOperation:
    """A single find/replace operation."""

    file: str
    find: str
    replace: str

    def __post_init__(self) -> None:
        """Validate operation data."""
        if not self.file or not isinstance(self.file, str):
            raise ValueError("file must be a non-empty string")
        if not self.find or not isinstance(self.find, str):
            raise ValueError("find must be a non-empty string")
        if not isinstance(self.replace, str):
            raise ValueError("replace must be a string")


class PatchEngineError(Exception):
    """Base exception for patch engine errors."""

    pass


class ValidationError(PatchEngineError):
    """Raised when patch operations fail validation."""

    pass


class NoEffectiveChangeError(PatchEngineError):
    """Raised when operations would make no effective change."""

    pass


class PatchEngine:
    """
    Converts JSON find/replace operations to unified diffs.

    This engine ensures:
    - Only allowed paths are modified
    - Operations are applied in order
    - Exact substring matching (no regex, no line numbers)
    - Size limits are enforced
    - Valid unified diffs are generated
    """

    def __init__(self, allowed_paths: set[str] = None) -> None:
        """
        Initialize the patch engine.

        Args:
            allowed_paths: Set of allowed file paths/patterns
        """
        self.allowed_paths = allowed_paths or ALLOWED_PATHS

    def validate_operations(self, operations: List[PatchOperation]) -> None:
        """
        Validate patch operations against guardrails.

        Args:
            operations: List of patch operations to validate

        Raises:
            ValidationError: If any validation fails
        """
        if not operations:
            raise ValidationError("No operations provided")

        if len(operations) > MAX_FILES_CHANGED:
            raise ValidationError(f"Too many operations: {len(operations)} > {MAX_FILES_CHANGED}")

        # Group by file and check total changes
        files_changed = set()
        total_changed_lines = 0

        for op in operations:
            # Check if file is allowed
            if not self._is_path_allowed(op.file):
                raise ValidationError(f"File not in allowlist: {op.file}")

            files_changed.add(op.file)

            # Estimate changed lines (rough count)
            find_lines = op.find.count("\n") + 1
            replace_lines = op.replace.count("\n") + 1
            total_changed_lines += max(find_lines, replace_lines)

        if len(files_changed) > MAX_FILES_CHANGED:
            raise ValidationError(
                f"Too many files changed: {len(files_changed)} > {MAX_FILES_CHANGED}"
            )

        if total_changed_lines > MAX_TOTAL_CHANGED_LINES:
            raise ValidationError(
                f"Too many lines changed: {total_changed_lines} > {MAX_TOTAL_CHANGED_LINES}"
            )

        logger.info(
            f"✅ Operations validated: {len(operations)} ops, "
            f"{len(files_changed)} files, ~{total_changed_lines} lines"
        )

    def _is_path_allowed(self, file_path: str) -> bool:
        """
        Check if a file path is allowed for modification.

        Args:
            file_path: Relative file path to check

        Returns:
            True if path is allowed
        """
        for allowed_pattern in self.allowed_paths:
            if file_path.startswith(allowed_pattern):
                return True
        return False

    def apply_operations_to_file(
        self, file_path: str, operations: List[PatchOperation]
    ) -> Tuple[str, str]:
        """
        Apply operations to a single file and return before/after content.

        Args:
            file_path: Path to the file to modify
            operations: Operations to apply to this file

        Returns:
            Tuple of (original_content, modified_content)

        Raises:
            ValidationError: If operations cannot be applied
        """
        # Read current file content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()
        except FileNotFoundError:
            raise ValidationError(f"File not found: {file_path}")
        except Exception as e:
            raise ValidationError(f"Error reading {file_path}: {e}")

        # Apply operations in order
        modified_content = original_content
        applied_ops = 0

        for op in operations:
            if op.file != file_path:
                continue

            # Find the exact substring
            if op.find not in modified_content:
                raise ValidationError(f"Find text not found in {file_path}: {repr(op.find[:100])}")

            # Apply the replacement
            modified_content = modified_content.replace(op.find, op.replace, 1)
            applied_ops += 1

        if applied_ops == 0:
            raise ValidationError(f"No operations applied to {file_path}")

        logger.info(f"✅ Applied {applied_ops} operations to {file_path}")
        return original_content, modified_content

    def build_unified_diff(
        self, file_path: str, original_content: str, modified_content: str
    ) -> str:
        """
        Build a unified diff string for a file.

        Args:
            file_path: Path to the file
            original_content: Original file content
            modified_content: Modified file content

        Returns:
            Unified diff string with a/ and b/ prefixes
        """
        # Generate unified diff with minimal context
        diff_lines = list(
            unified_diff(
                original_content.splitlines(keepends=True),
                modified_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
                n=3,  # 3 lines of context
            )
        )

        # Join lines and ensure proper diff format
        diff_content = "".join(diff_lines)

        # Add newline at end if missing
        if not diff_content.endswith("\n"):
            diff_content += "\n"

        return diff_content

    def process_operations(self, operations_json: str) -> str:
        """
        Process JSON operations and return a unified diff string.

        Args:
            operations_json: JSON string containing operations

        Returns:
            Unified diff string ready for git apply

        Raises:
            ValidationError: If operations are invalid
            NoEffectiveChangeError: If no effective changes would be made
        """
        try:
            # Parse JSON
            data = json.loads(operations_json)

            if not isinstance(data, dict) or "ops" not in data:
                raise ValidationError("JSON must contain 'ops' key")

            ops_data = data["ops"]
            if not isinstance(ops_data, list) or not ops_data:
                raise ValidationError("'ops' must be a non-empty list")

            # Convert to PatchOperation objects
            operations = []
            for i, op_data in enumerate(ops_data):
                try:
                    if not isinstance(op_data, dict):
                        raise ValueError("Each operation must be an object")

                    required_keys = {"file", "find", "replace"}
                    if not all(key in op_data for key in required_keys):
                        raise ValueError(f"Missing required keys: {required_keys}")

                    operation = PatchOperation(
                        file=op_data["file"], find=op_data["find"], replace=op_data["replace"]
                    )
                    operations.append(operation)

                except Exception as e:
                    raise ValidationError(f"Invalid operation {i}: {e}")

        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")
        except Exception as e:
            raise ValidationError(f"Error processing operations: {e}")

        # Validate operations
        self.validate_operations(operations)

        # Group operations by file
        file_ops: Dict[str, List[PatchOperation]] = {}
        for op in operations:
            if op.file not in file_ops:
                file_ops[op.file] = []
            file_ops[op.file].append(op)

        # Process each file and build diffs
        all_diffs = []
        total_changes = 0

        for file_path, file_operations in file_ops.items():
            try:
                original_content, modified_content = self.apply_operations_to_file(
                    file_path, file_operations
                )

                # Check if there are actual changes
                if original_content == modified_content:
                    logger.warning(f"⚠️ No effective change in {file_path}")
                    continue

                # Build unified diff
                diff_content = self.build_unified_diff(
                    file_path, original_content, modified_content
                )
                all_diffs.append(diff_content)

                # Count changed lines
                original_lines = original_content.splitlines()
                modified_lines = modified_content.splitlines()
                changed_lines = len(original_lines) + len(modified_lines)
                total_changes += changed_lines

                logger.info(f"📝 Generated diff for {file_path}: {changed_lines} lines")

            except Exception as e:
                raise ValidationError(f"Error processing {file_path}: {e}")

        if not all_diffs:
            raise NoEffectiveChangeError("No effective changes would be made")

        # Concatenate all diffs
        final_diff = "".join(all_diffs)

        logger.info(
            f"🎯 Patch engine completed: {len(file_ops)} files, " f"~{total_changes} lines changed"
        )

        return final_diff


def create_patch_engine() -> PatchEngine:
    """Create a patch engine instance with default settings."""
    return PatchEngine()
