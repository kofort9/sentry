#!/usr/bin/env python3
"""
TestSentry: Keeps tests/** green by proposing test-only patches.

This version uses a robust patch engine that eliminates reliance on model-generated line numbers.
Instead, it uses JSON find/replace operations that are converted to unified diffs locally.
"""

import os
import subprocess
from typing import Optional, Tuple

from .chat import chat, get_default_params
from .diff_utils import apply_unified_diff, extract_diff_summary
from .git_utils import (
    commit_all,
    create_branch,
    get_base_branch,
    label_pull_request,
    open_pull_request,
)
from .patch_engine import (
    NoEffectiveChangeError,
    ValidationError,
    create_patch_engine,
)
from .prompts import PATCHER_TESTS, PLANNER_TESTS
from .runner_common import (
    MODEL_PATCH,
    MODEL_PLAN,
    exit_failure,
    exit_noop,
    exit_success,
    get_logger,
    get_short_sha,
    setup_logging,
    validate_environment,
)

logger = get_logger(__name__)


def discover_test_failures() -> Optional[str]:
    """
    Discover failing tests by running pytest or using pre-captured output.

    Returns:
        pytest output if there are failures, None if all tests pass
    """
    # Check if we have pre-captured test failure output from CI
    if os.path.exists("pytest-output.txt"):
        logger.info("Using pre-captured test failure output from CI")
        try:
            with open("pytest-output.txt", "r") as f:
                output = f.read()

            if "FAILED" in output or "ERROR" in output or "AssertionError" in output:
                logger.info("Found test failures in pre-captured output")
                return output
            else:
                logger.info("No test failures found in pre-captured output")
                return None
        except Exception as e:
            logger.warning(f"Error reading pre-captured output: {e}, falling back to pytest")

    # Fall back to running pytest directly
    try:
        logger.info("Running pytest to discover test failures...")
        result = subprocess.run(
            ["pytest", "sentries/", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )

        if result.returncode == 0:
            logger.info("All tests are passing")
            return None

        # Check if there are actual test failures (not just collection errors)
        output = result.stdout + result.stderr
        if "FAILED" in output or "ERROR" in output or "AssertionError" in output:
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


def get_test_context_with_excerpts(failing_tests_output: str) -> Tuple[str, str]:
    """
    Extract relevant test context and create minimal excerpts for the patcher.

    Returns:
        Tuple of (full_context, minimal_excerpts)
    """
    # Extract test file paths from pytest output
    lines = failing_tests_output.split("\n")
    test_files = set()

    for line in lines:
        if "::" in line and ".py::" in line:
            # Extract file path from test identifier
            parts = line.split("::")
            if len(parts) >= 2:
                file_path = parts[0]
                # Include test files from tests/ directory or sentries/test_*.py
                if file_path.startswith("tests/") or (
                    file_path.startswith("sentries/") and "test_" in file_path
                ):
                    test_files.add(file_path)

    full_context = f"Test failures detected:\n\n{failing_tests_output}\n\n"

    # Create minimal excerpts for the patcher
    minimal_excerpts = ""
    if test_files:
        minimal_excerpts += "File excerpts for patcher (copy exact text from these):\n\n"
        for file_path in sorted(test_files):
            try:
                with open(file_path, "r") as f:
                    file_content = f.read()

                # Find failing test functions and create minimal excerpts
                lines = file_content.split("\n")
                excerpt_lines = []

                for i, line in enumerate(lines):
                    # Look for test functions and failing assertions
                    if line.strip().startswith("def test_") or "assert" in line:
                        # Include function header and assertion line with minimal context
                        start = max(0, i - 1)
                        end = min(len(lines), i + 2)
                        excerpt_lines.extend(lines[start:end])
                        excerpt_lines.append("")  # Empty line for separation

                if excerpt_lines:
                    minimal_excerpts += f"=== {file_path} ===\n"
                    minimal_excerpts += "\n".join(excerpt_lines)
                    minimal_excerpts += "\n\n"
                else:
                    # Fallback: include first 20 lines
                    minimal_excerpts += f"=== {file_path} ===\n"
                    minimal_excerpts += "\n".join(lines[:20])
                    minimal_excerpts += "\n\n"

            except Exception as e:
                minimal_excerpts += f"=== {file_path} ===\n[Error reading file: {e}]\n\n"

    return full_context, minimal_excerpts


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
            {"role": "user", "content": context},
        ]

        logger.info("Planning test fixes with LLM...")

        # Log context size
        logger.info(f"Context size: {len(context)} chars")

        logger.info(f"Sending context to LLM planner (length: {len(context)}):")
        logger.info("=" * 50)
        logger.info(context)
        logger.info("=" * 50)

        # Try primary model first
        logger.info(f"Trying primary model: {MODEL_PLAN}")
        response = chat(
            model=MODEL_PLAN,
            messages=messages,
            temperature=params["temperature"],
            max_tokens=int(params["max_tokens"]),
        )

        # If primary model fails, try fallback model
        if not response or len(response.strip()) == 0:
            logger.warning("Primary model returned empty response, trying fallback model...")
            fallback_model = (
                "deepseek-coder:6.7b-instruct-q5_K_M"  # Use the patcher model as fallback
            )
            logger.info(f"Trying fallback model: {fallback_model}")
            try:
                response = chat(
                    model=fallback_model,
                    messages=messages,
                    temperature=params["temperature"],
                    max_tokens=int(params["max_tokens"]),
                )
            except Exception as e:
                logger.error(f"Fallback model also failed: {e}")
                response = ""

        # Log the full LLM response for debugging
        logger.info(f"LLM Planner Response (length: {len(response)}):")
        logger.info("=" * 50)
        logger.info(response)
        logger.info("=" * 50)

        # Log the LLM's reasoning and decision-making
        logger.info("🤖 LLM Planner Reasoning:")
        logger.info("-" * 30)
        if "ABORT" in response.upper():
            logger.info("❌ LLM decided to ABORT - no fixes needed")
        elif "NO-OP" in response.upper():
            logger.info("⏭️ LLM decided NO-OP - no action required")
        else:
            logger.info("✅ LLM decided to proceed with test fixes")
            logger.info(f"📝 Planning response: {response[:200]}...")
        logger.info("-" * 30)

        # Handle empty or invalid responses
        if not response or len(response.strip()) == 0:
            logger.error("LLM planner returned empty response - this indicates a model issue")
            logger.error("Empty responses are treated as ABORT to prevent invalid fixes")
            return None

        if "ABORT" in response.upper():
            logger.info("LLM planner returned ABORT - non-test code changes required")
            logger.info("This suggests the LLM thinks production code needs to change")
            return None

        logger.info("Planning completed successfully")
        return response

    except Exception as e:
        logger.error(f"Error during planning: {e}")
        return None


def generate_test_patch_json(plan: str, excerpts: str) -> Optional[str]:
    """
    Use the patcher model to generate JSON operations for test fixes.

    Args:
        plan: The planning response
        excerpts: Minimal file excerpts for the patcher

    Returns:
        JSON string with operations or None if ABORT
    """
    try:
        # Create focused context for the patcher
        patcher_context = f"""Plan: {plan}

{excerpts}

Generate JSON operations to fix the failing tests. Copy exact text from the excerpts above."""

        messages = [
            {"role": "system", "content": PATCHER_TESTS},
            {"role": "user", "content": patcher_context},
        ]

        logger.info("Generating test patch JSON with LLM...")

        # Use tighter generation limits for JSON output
        response = chat(
            model=MODEL_PATCH,
            messages=messages,
            temperature=0.1,  # Lower temperature for more precise output
            max_tokens=600,  # Keep JSON output compact
        )

        # Log the full LLM patch response for debugging
        logger.info(f"LLM Patcher Response (length: {len(response)}):")
        logger.info("=" * 50)
        logger.info(response)
        logger.info("=" * 50)

        # Log the LLM's reasoning and decision-making
        logger.info("🤖 LLM Patcher Reasoning:")
        logger.info("-" * 30)
        if "ABORT" in response.upper():
            logger.info("❌ LLM decided to ABORT - no patch generated")
        else:
            logger.info("✅ LLM decided to generate JSON operations")
            logger.info(f"📝 Response preview: {response[:200]}...")
        logger.info("-" * 30)

        if "ABORT" in response.upper():
            logger.info("LLM patcher returned ABORT")
            return None

        # Clean up the response - remove any markdown or prose
        cleaned_response = response.strip()

        # Try to extract JSON if it's wrapped in markdown
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]  # Remove ```json
        elif cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove ending ```

        cleaned_response = cleaned_response.strip()

        logger.info("JSON patch generation completed")
        logger.info(f"Cleaned response (length: {len(cleaned_response)}):")
        logger.info("=" * 50)
        logger.info(cleaned_response)
        logger.info("=" * 50)

        return cleaned_response

    except Exception as e:
        logger.error(f"Error during JSON patch generation: {e}")
        return None


def apply_and_test_patch_with_engine(
    json_operations: str, original_context: str, plan: str, max_attempts: int = 3
) -> Tuple[bool, str]:
    """
    Apply patch using the patch engine with feedback loop for validation failures.

    Args:
        json_operations: JSON string with find/replace operations
        original_context: Original test failure context
        plan: The test fix plan
        max_attempts: Maximum number of correction attempts (default: 3)

    Returns:
        (success, final_diff) tuple
    """
    current_json = json_operations
    patch_engine = create_patch_engine()

    for attempt in range(max_attempts):
        logger.info(f"🔄 Patch attempt {attempt + 1}/{max_attempts}")

        try:
            # Use the patch engine to convert JSON to unified diff
            logger.info("🔧 Converting JSON operations to unified diff...")
            unified_diff = patch_engine.process_operations(current_json)

            logger.info("✅ Patch engine generated valid unified diff")
            logger.info(f"📝 Diff length: {len(unified_diff)} characters")

            # Try to apply the diff
            if apply_unified_diff(".", unified_diff):
                logger.info("✅ Patch applied successfully")

                # CRITICAL: Run pytest to verify the fix actually works
                logger.info("🧪 Running pytest to verify the fix...")
                result = subprocess.run(
                    ["pytest", "sentries/", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    logger.info("🎉 Tests are now passing! Fix verified.")
                    return True, unified_diff
                else:
                    logger.error("❌ Tests still failing after patch - fix didn't work")
                    # Generate feedback for the LLM
                    feedback = (
                        f"Patch applied but tests still fail. Test output:\n"
                        f"{result.stdout}\n{result.stderr}"
                    )
            else:
                feedback = "Patch failed to apply due to git apply error"

        except (ValidationError, NoEffectiveChangeError) as e:
            logger.warning(f"⚠️ Patch engine validation failed: {e}")
            feedback = f"Patch engine validation failed: {e}"
        except Exception as e:
            logger.error(f"❌ Unexpected error in patch engine: {e}")
            feedback = f"Patch engine error: {e}"

        # If we're not on the last attempt, try to get the LLM to fix it
        if attempt < max_attempts - 1:
            logger.info("🔄 Asking LLM to correct the JSON operations...")

            # Create feedback context
            feedback_context = f"""
{original_context}

PATCH ENGINE FEEDBACK (Attempt {attempt + 1}):
Your previous JSON operations failed: {feedback}

Please generate corrected JSON operations that address these issues.
Make sure to:
1. Only reference allowed file paths
2. Use exact text from the provided excerpts
3. Generate valid JSON format
4. Stay within size limits (max 5 ops, max 200 lines)

PREVIOUS FAILED JSON:
{current_json}
"""

            # Get corrected JSON from LLM
            corrected_json = generate_test_patch_json(
                f"CORRECTION NEEDED: {feedback}", feedback_context
            )

            if corrected_json:
                current_json = corrected_json
                logger.info("🔄 LLM generated corrected JSON, retrying...")
                continue
            else:
                logger.error("❌ LLM failed to generate corrected JSON")
                break
        else:
            logger.error(f"❌ Max attempts ({max_attempts}) reached, giving up")
            logger.error(f"Final failure reason: {feedback}")
            break

    return False, ""


def apply_and_test_patch(diff_str: str) -> bool:
    """
    Apply the patch and re-run tests to verify it works.

    Args:
        diff_str: The unified diff to apply

    Returns:
        True if tests pass after applying the patch
    """
    try:
        # Apply the diff
        if not apply_unified_diff(".", diff_str):
            logger.error("Failed to apply diff")
            return False

        # Re-run tests to verify the fix
        logger.info("Re-running tests to verify the fix...")
        result = subprocess.run(["pytest", "-q"], capture_output=True, text=True, timeout=300)

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

**Generated by:** TestSentry AI (Patch Engine v2)
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


def show_sentries_banner() -> None:
    """Display the Sentry ASCII art banner."""
    from sentries.banner import show_sentry_banner

    show_sentry_banner()
    print("🧪 TestSentry v2 - AI-Powered Test Fixing (Patch Engine)")
    print("=" * 60)
    print()


def main() -> None:
    """Main entry point for TestSentry."""
    show_sentries_banner()
    setup_logging()
    logger.info("TestSentry v2 starting with Patch Engine...")

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

    # Get test context with minimal excerpts for the patcher
    context, excerpts = get_test_context_with_excerpts(failing_tests)

    # Plan test fixes
    plan = plan_test_fixes(context)
    if not plan:
        exit_noop("Non-test code changes required to fix tests")

    # Generate test patch JSON with feedback loop
    diff_str = generate_test_patch_json(plan, excerpts)
    if not diff_str:
        exit_noop("Could not generate test patch JSON")

    # Apply and test with patch engine (max 3 attempts)
    logger.info("🔄 Starting patch application with Patch Engine...")
    success, final_diff = apply_and_test_patch_with_engine(diff_str, context, plan, max_attempts=3)

    if not success:
        exit_noop("Patch application or testing failed after 3 attempts")

    # Create PR only if we have a working fix
    diff_summary = extract_diff_summary(final_diff)
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
