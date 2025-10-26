"""Support tools for CAMEL planner and patcher agents."""

import json
from typing import Any, Dict, List, Optional

from ..intelligent_analysis import create_smart_context
from ..patch_engine import create_patch_engine
from ..git_utils import (
    create_branch,
    commit_all,
    open_pull_request,
    get_base_branch,
    tag_branch_with_sentries_metadata,
)
from ..runner_common import get_logger

logger = get_logger(__name__)


class TestAnalysisTool:
    """Tool for intelligent test failure analysis."""

    @staticmethod
    def analyze_failures(test_output: str) -> Dict[str, Any]:
        """
        Analyze test failures and create smart context packs.

        Args:
            test_output: Raw pytest output with failures

        Returns:
            Analysis results with context packs
        """
        try:
            logger.info("🧠 Running intelligent test analysis...")
            context_packs = create_smart_context(test_output)

            result: Dict[str, Any] = {
                "success": True,
                "context_packs": [],
                "summary": f"Analyzed {len(context_packs)} test failures",
            }

            for pack in context_packs:
                result["context_packs"].append(
                    {
                        "test_function": pack.failure_info.test_function,
                        "test_file": pack.failure_info.test_file,
                        "failure_type": pack.failure_info.failure_type.value,
                        "error_message": pack.failure_info.error_message,
                        "context_size": pack.context_size,
                        "context_parts": pack.context_parts,
                        "find_candidates": pack.find_candidates,
                    }
                )

            return result

        except Exception as exc:
            logger.error(f"Error in test analysis: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "context_packs": [],
                "summary": "Analysis failed",
            }


class PatchGenerationTool:
    """Tool for generating unified diffs from JSON operations."""

    @staticmethod
    def generate_patch(json_operations: str) -> Dict[str, Any]:
        """
        Convert JSON operations to unified diff using patch engine.

        Args:
            json_operations: JSON string with find/replace operations

        Returns:
            Patch generation results
        """
        try:
            logger.info("🔧 Converting JSON operations to unified diff...")
            engine = create_patch_engine()
            unified_diff = engine.process_operations(json_operations)

            return {
                "success": True,
                "unified_diff": unified_diff,
                "message": f"Generated diff ({len(unified_diff)} characters)",
            }

        except Exception as exc:
            logger.error(f"Error in patch generation: {exc}")
            return {
                "success": False,
                "unified_diff": "",
                "error": str(exc),
                "message": f"Patch generation failed: {exc}",
            }


class PatchValidationTool:
    """Tool for validating JSON operations before patch generation."""

    @staticmethod
    def validate_operations(json_operations: str) -> Dict[str, Any]:
        """
        Validate JSON operations for correctness and safety.

        Args:
            json_operations: JSON string with operations to validate

        Returns:
            Validation results
        """
        try:
            data = json.loads(json_operations)

            validation_result = {"valid": True, "issues": [], "suggestions": []}

            if "ops" not in data:
                validation_result["valid"] = False
                validation_result["issues"].append("Missing 'ops' key in JSON")
                return validation_result

            ops = data["ops"]
            if not isinstance(ops, list):
                validation_result["valid"] = False
                validation_result["issues"].append("'ops' must be a list")
                return validation_result

            for idx, op in enumerate(ops):
                if not isinstance(op, dict):
                    validation_result["issues"].append(
                        f"Operation {idx} is not a dictionary"
                    )
                    continue

                required_keys = {"file", "find", "replace"}
                missing_keys = required_keys - set(op.keys())
                if missing_keys:
                    validation_result["issues"].append(
                        f"Operation {idx} missing keys: {missing_keys}"
                    )

                file_path = op.get("file", "")
                if not file_path.startswith("tests/"):
                    validation_result["issues"].append(
                        f"Operation {idx} targets non-test file: {file_path}"
                    )

            if validation_result["issues"]:
                validation_result["valid"] = False

            return validation_result

        except json.JSONDecodeError as exc:
            return {
                "valid": False,
                "issues": [f"Invalid JSON format: {exc}"],
                "suggestions": ["Ensure JSON is properly formatted"],
            }
        except Exception as exc:  # pragma: no cover - unexpected validation failure
            return {
                "valid": False,
                "issues": [f"Validation error: {exc}"],
                "suggestions": [],
            }


class GitOperationsTool:
    """
    Phase 2: Git operations tool for branch management and PR creation.
    
    Provides agents with the ability to perform Git operations safely
    and with proper metadata tracking.
    """

    @staticmethod
    def create_feature_branch(
        branch_name: str, sentry_type: str = "testsentry"
    ) -> Dict[str, Any]:
        """
        Create a new feature branch for fixes.

        Args:
            branch_name: Name for the new branch
            sentry_type: Type of sentry creating the branch

        Returns:
            Branch creation results
        """
        try:
            logger.info(f"🌿 Creating feature branch: {branch_name}")
            
            # Create branch and tag with metadata
            actual_branch = create_branch(branch_name, sentry_type)
            tag_branch_with_sentries_metadata(actual_branch, sentry_type)
            
            return {
                "success": True,
                "branch_name": actual_branch,
                "message": f"Created and tagged branch: {actual_branch}",
            }

        except Exception as exc:
            logger.error(f"Error creating branch {branch_name}: {exc}")
            return {
                "success": False,
                "branch_name": branch_name,
                "error": str(exc),
                "message": f"Failed to create branch: {exc}",
            }

    @staticmethod
    def commit_changes(
        message: str, files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Commit changes with proper message formatting.

        Args:
            message: Commit message
            files: Optional list of specific files to commit

        Returns:
            Commit results
        """
        try:
            logger.info(f"📝 Committing changes: {message[:50]}...")
            
            if files:
                # Commit specific files (would need git_utils enhancement)
                logger.info(f"Committing specific files: {files}")
                # For now, use commit_all since git_utils doesn't have file-specific commit
                commit_all(message)
            else:
                # Commit all staged changes
                commit_all(message)
            
            return {
                "success": True,
                "message": "Changes committed successfully",
                "commit_message": message,
            }

        except Exception as exc:
            logger.error(f"Error committing changes: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "message": f"Failed to commit: {exc}",
            }

    @staticmethod
    def create_pull_request(
        title: str, 
        body: str, 
        head_branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a pull request with the changes.

        Args:
            title: PR title
            body: PR description body
            head_branch: Source branch (current if None)

        Returns:
            PR creation results
        """
        try:
            logger.info(f"🚀 Creating PR: {title}")
            
            base_branch = get_base_branch()
            
            # Use git_utils to create PR
            pr_result = open_pull_request(
                title=title,
                body=body,
                base=base_branch,
                head=head_branch,
            )
            
            return {
                "success": True,
                "pr_url": pr_result.get("url", "PR created"),
                "title": title,
                "base_branch": base_branch,
                "head_branch": head_branch or "current",
                "message": "PR created successfully",
            }

        except Exception as exc:
            logger.error(f"Error creating PR: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "message": f"Failed to create PR: {exc}",
            }

    @staticmethod
    def get_repository_info() -> Dict[str, Any]:
        """
        Get current repository information.

        Returns:
            Repository status and branch information
        """
        try:
            base_branch = get_base_branch()
            
            return {
                "success": True,
                "base_branch": base_branch,
                "message": "Repository info retrieved",
            }

        except Exception as exc:
            logger.error(f"Error getting repository info: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "message": f"Failed to get repo info: {exc}",
            }
