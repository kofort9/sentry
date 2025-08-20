#!/usr/bin/env python3
"""
TestSentry: Keeps tests/** green by proposing test-only patches.
"""
import os
import sys
import subprocess
import json
from typing import List, Dict, Optional
from .runner_common import (
    setup_logging, get_logger, validate_environment, get_short_sha,
    exit_success, exit_noop, exit_failure, TESTS_ALLOWLIST,
    MODEL_PLAN, MODEL_PATCH
)
from .chat import chat, get_default_params
from .prompts import PLANNER_TESTS, PATCHER_TESTS
from .diff_utils import validate_unified_diff, apply_unified_diff, extract_diff_summary
from .git_utils import (
    create_branch, commit_all, open_pull_request, label_pull_request,
    get_base_branch
)

logger = get_logger(__name__)

def discover_test_failures() -> Optional[str]:
    """
    Discover failing tests by running pytest.

    Returns:
        pytest output if there are failures, None if all tests pass
    """
    try:
        logger.info("Running pytest to discover test failures...")
        result = subprocess.run(
            ['pytest', '-q'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        if result.returncode == 0:
            logger.info("All tests are passing")
            return None

        # Check if there are actual test failures (not just collection errors)
        output = result.stdout + result.stderr
        if "FAILED" in output or "ERROR" in output:
            logger.info(f"Found test failures: {result.returncode} tests failed")
            return output
        else:
            logger.info("No test failures found, only collection issues")
            return None

    except subprocess.TimeoutExpired:
        logger.error("pytest timed out")
        return None
    except Exception as e:
        logger.error(f"Error running pytest: {e}")
        return None

def get_test_context(failing_tests_output: str) -> str:
    """
    Extract relevant test context from pytest output.

    Args:
        failing_tests_output: Raw pytest output

    Returns:
        Formatted context for the LLM
    """
    # Extract test file paths and line numbers from pytest output
    lines = failing_tests_output.split('\n')
    test_files = set()

    for line in lines:
        if '::' in line and '.py::' in line:
            # Extract file path from test identifier
            parts = line.split('::')
            if len(parts) >= 2:
                file_path = parts[0]
                if file_path.startswith('tests/'):
                    test_files.add(file_path)

    context = f"Test failures detected:\n\n{failing_tests_output}\n\n"

    if test_files:
        context += "Relevant test files:\n"
        for file_path in sorted(test_files):
            context += f"- {file_path}\n"

    return context

def plan_test_fixes(context: str) -> Optional[str]:
    """
    Use the planner model to create a plan for fixing tests.

    Args:
        context: Test failure context

    Returns:
        Planning response from the LLM
    """
    try:
        params = get_default_params("planner")

        messages = [
            {"role": "system", "content": PLANNER_TESTS},
            {"role": "user", "content": context}
        ]

        logger.info("Planning test fixes with LLM...")
        response = chat(
            model=MODEL_PLAN,
            messages=messages,
            **params
        )

        if "ABORT" in response.upper():
            logger.info("LLM planner returned ABORT - non-test code changes required")
            return None

        logger.info("Planning completed successfully")
        return response

    except Exception as e:
        logger.error(f"Error during planning: {e}")
        return None

def generate_test_patch(plan: str, context: str) -> Optional[str]:
    """
    Use the patcher model to generate a test patch.

    Args:
        plan: The planning response
        context: Test failure context

    Returns:
        Unified diff string or None if ABORT
    """
    try:
        params = get_default_params("patcher")

        messages = [
            {"role": "system", "content": PATCHER_TESTS},
            {"role": "user", "content": f"Plan: {plan}\n\nContext: {context}"}
        ]

        logger.info("Generating test patch with LLM...")
        response = chat(
            model=MODEL_PATCH,
            messages=messages,
            **params
        )

        if "ABORT" in response.upper():
            logger.info("LLM patcher returned ABORT")
            return None

        logger.info("Patch generation completed")
        return response

    except Exception as e:
        logger.error(f"Error during patch generation: {e}")
        return None

def apply_and_test_patch(diff_str: str) -> bool:
    """
    Apply the patch and re-run tests to verify it works.

    Args:
        diff_str: The unified diff to apply

    Returns:
        True if tests pass after applying the patch
    """
    try:
        # Validate the diff
        is_valid, reason = validate_unified_diff(diff_str, TESTS_ALLOWLIST)
        if not is_valid:
            logger.error(f"Invalid diff: {reason}")
            return False

        # Apply the diff
        if not apply_unified_diff(".", diff_str):
            logger.error("Failed to apply diff")
            return False

        # Re-run tests to verify the fix
        logger.info("Re-running tests to verify the fix...")
        result = subprocess.run(
            ['pytest', '-q'],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            logger.info("Tests are now passing!")
            return True
        else:
            logger.error("Tests still failing after applying patch")
            return False

    except Exception as e:
        logger.error(f"Error during patch application and testing: {e}")
        return False

def create_test_fix_pr(plan: str, diff_summary: str) -> Optional[int]:
    """
    Create a pull request for the test fixes.

    Args:
        plan: The planning response
        diff_summary: Summary of what the diff changes

    Returns:
        PR number if successful, None otherwise
    """
    try:
        short_sha = get_short_sha()
        base_branch = get_base_branch()

        # Create branch
        branch_name = create_branch("ai-test-fixes", sentry_type="testsentry")

        # Commit changes
        commit_message = f"TestSentry: fix tests for {short_sha}\n\n{plan}"
        if not commit_all(commit_message):
            raise RuntimeError("Failed to commit changes")

        # Create PR
        title = f"TestSentry: fix tests for {short_sha}"
        body = f"""## Test Fixes

**Plan:**
{plan}

**Changes:**
{diff_summary}

**Generated by:** TestSentry AI
**Branch:** {branch_name}
"""

        pr_number = open_pull_request(base_branch, branch_name, title, body, "testsentry")
        if pr_number:
            logger.info(f"Created PR #{pr_number} for test fixes")
            return pr_number
        else:
            raise RuntimeError("Failed to create PR")

    except Exception as e:
        logger.error(f"Error creating test fix PR: {e}")
        return None

def label_feature_pr(pr_number: int, success: bool = True) -> None:
    """
    Label the feature PR that triggered this action.

    Args:
        pr_number: PR number to label
        success: Whether the test fixes were successful
    """
    try:
        label = "tests-sentry:done" if success else "tests-sentry:noop"
        if label_pull_request(pr_number, [label]):
            logger.info(f"Labeled feature PR with: {label}")
        else:
            logger.warning(f"Failed to label feature PR with: {label}")
    except Exception as e:
        logger.error(f"Error labeling feature PR: {e}")

def show_sentries_banner():
    """Display the Sentry ASCII art banner."""
    from sentries.banner import show_sentry_banner
    show_sentry_banner()
    print("🧪 TestSentry - AI-Powered Test Fixing")
    print("=" * 50)
    print()

def main() -> None:
    """Main entry point for TestSentry."""
    show_sentries_banner()
    setup_logging()
    logger.info("TestSentry starting...")

    # Validate environment
    if not validate_environment():
        exit_failure("Environment validation failed")

    # Check if we're in a git repository
    if not os.path.exists(".git"):
        exit_failure("Not in a git repository")

    # Discover test failures
    failing_tests = discover_test_failures()
    if not failing_tests:
        exit_noop("No test failures found")

    # Get test context
    context = get_test_context(failing_tests)

    # Plan test fixes
    plan = plan_test_fixes(context)
    if not plan:
        exit_noop("Non-test code changes required to fix tests")

    # Generate test patch
    diff_str = generate_test_patch(plan, context)
    if not diff_str:
        exit_noop("Could not generate test patch")

    # Apply and test the patch
    if not apply_and_test_patch(diff_str):
        exit_noop("Patch application or testing failed")

    # Create PR
    diff_summary = extract_diff_summary(diff_str)
    pr_number = create_test_fix_pr(plan, diff_summary)

    if pr_number:
        # Try to label the feature PR if we can determine its number
        try:
            # This would need to be determined from the GitHub context
            # For now, we'll just log success
            logger.info("Test fixes completed successfully")
        except Exception as e:
            logger.warning(f"Could not label feature PR: {e}")

        exit_success(f"Created PR #{pr_number} for test fixes")
    else:
        exit_failure("Failed to create PR for test fixes")

if __name__ == "__main__":
    main()
