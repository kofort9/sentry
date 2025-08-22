#!/usr/bin/env python3
"""
TestSentry: Keeps tests/** green by proposing test-only patches.
"""
import os
import re
import subprocess
from typing import Optional, Tuple

from .chat import chat, get_default_params
from .diff_utils import apply_unified_diff, extract_diff_summary, validate_unified_diff
from .git_utils import (
    commit_all,
    create_branch,
    get_base_branch,
    label_pull_request,
    open_pull_request,
)
from .prompts import PATCHER_TESTS, PLANNER_TESTS
from .runner_common import (
    MODEL_PATCH,
    MODEL_PLAN,
    TESTS_ALLOWLIST,
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


def get_test_context(failing_tests_output: str) -> str:
    """
    Extract relevant test context from pytest output.

    Args:
        failing_tests_output: Raw pytest output

    Returns:
        Formatted context for the LLM
    """
    # Extract test file paths and line numbers from pytest output
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

    context = f"Test failures detected:\n\n{failing_tests_output}\n\n"

    if test_files:
        context += "Relevant test files and content:\n\n"
        for file_path in sorted(test_files):
            try:
                with open(file_path, "r") as f:
                    file_content = f.read()
                context += f"=== {file_path} ===\n{file_content}\n\n"
            except Exception as e:
                context += f"=== {file_path} ===\n[Error reading file: {e}]\n\n"

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
            {"role": "user", "content": context},
        ]

        logger.info("Planning test fixes with LLM...")

        # Log context size (no compression needed - simple is better)
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
            {"role": "user", "content": f"Plan: {plan}\n\nContext: {context}"},
        ]

        logger.info("Generating test patch with LLM...")
        response = chat(
            model=MODEL_PATCH,
            messages=messages,
            temperature=params["temperature"],
            max_tokens=int(params["max_tokens"]),
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
            logger.info("✅ LLM decided to generate a patch")
            logger.info(f"📝 Patch content preview: {response[:200]}...")
        logger.info("-" * 30)

        if "ABORT" in response.upper():
            logger.info("LLM patcher returned ABORT")
            return None

        # Clean up the response - remove code fences if present
        cleaned_response = response.strip()
        if cleaned_response.startswith("```diff"):
            cleaned_response = cleaned_response[7:]  # Remove ```diff
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove ending ```
        cleaned_response = cleaned_response.strip()

        logger.info("Patch generation completed")
        logger.info(f"Cleaned patch (length: {len(cleaned_response)}):")
        logger.info("=" * 50)
        logger.info(cleaned_response)
        logger.info("=" * 50)

        return cleaned_response

    except Exception as e:
        logger.error(f"Error during patch generation: {e}")
        return None


def validate_patch_line_numbers(diff_str: str, test_file_path: str) -> Tuple[bool, str]:
    """
    Validate that the patch references correct line numbers in the actual file.

    Args:
        diff_str: The unified diff string
        test_file_path: Path to the test file

    Returns:
        (is_valid, reason) tuple
    """
    try:
        # Read the current file content
        with open(test_file_path, "r") as f:
            current_lines = f.readlines()

        logger.info(f"🔍 Validating patch against {test_file_path} ({len(current_lines)} lines)")

        # Extract hunks from the diff
        hunks = []
        diff_lines = diff_str.split("\n")

        for i, line in enumerate(diff_lines):
            if line.startswith("@@"):
                # Parse @@ -old_start,old_count +new_start,new_count @@
                match = re.search(r"@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@", line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1

                    # Extract the old lines for this hunk
                    old_lines = []
                    j = i + 1
                    while j < len(diff_lines) and not diff_lines[j].startswith("@@"):
                        if diff_lines[j].startswith("-"):
                            old_lines.append(diff_lines[j][1:])  # Remove the - prefix
                        elif diff_lines[j].startswith(" "):
                            # Context line, also check it
                            old_lines.append(diff_lines[j][1:])  # Remove the space prefix
                        j += 1

                    hunks.append((old_start, old_count, old_lines))

        logger.info(
            f"📍 Patch references {len(hunks)} hunks: "
            f"{[(start, count) for start, count, _ in hunks]}"
        )

        # Check each hunk
        for old_start, old_count, expected_lines in hunks:
            # Check if the line numbers are within the file bounds
            if old_start < 1 or old_start > len(current_lines):
                return (
                    False,
                    f"Hunk references line {old_start} but file only has "
                    f"{len(current_lines)} lines",
                )

            # Check if the expected lines match the current file content
            file_line_index = old_start - 1  # Convert to 0-based index

            for expected_line in expected_lines:
                if file_line_index >= len(current_lines):
                    return False, f"Hunk extends beyond file end (line {file_line_index + 1})"

                actual_line = current_lines[file_line_index].rstrip("\n")
                if expected_line.strip() != actual_line.strip():
                    logger.error(f"❌ Line {file_line_index + 1} mismatch:")
                    logger.error(f"   Expected: '{expected_line.strip()}'")
                    logger.error(f"   Actual:   '{actual_line.strip()}'")
                    return (
                        False,
                        f"Line {file_line_index + 1} content doesn\'t match: "
                        f"expected \'{expected_line.strip()}\', got \'{actual_line.strip()}\'",
                    )

                file_line_index += 1

        logger.info("✅ Patch line numbers and content are valid")
        return True, "Valid patch"

    except Exception as e:
        logger.error(f"Error validating patch: {e}")
        return False, f"Validation error: {e}"


def apply_and_test_patch_with_feedback(
    diff_str: str, original_context: str, plan: str, max_attempts: int = 3
) -> Tuple[bool, str]:
    """
    Apply patch with feedback loop for validation failures.

    Args:
        diff_str: The unified diff to apply
        original_context: Original test failure context
        plan: The test fix plan
        max_attempts: Maximum number of correction attempts (default: 3)

    Returns:
        (success, final_patch) tuple
    """
    current_patch = diff_str

    for attempt in range(max_attempts):
        logger.info(f"🔄 Patch attempt {attempt + 1}/{max_attempts}")

        # Validate the diff format first
        is_valid, reason = validate_unified_diff(current_patch, TESTS_ALLOWLIST)
        if not is_valid:
            feedback = f"Diff format validation failed: {reason}"
            logger.warning(f"⚠️ {feedback}")
        else:
            # Extract test file path from the diff
            test_file_path = None
            for line in current_patch.split("\n"):
                if line.startswith("--- a/") or line.startswith("+++ b/"):
                    if "test_" in line:
                        # Extract file path
                        if line.startswith("--- a/"):
                            test_file_path = line[6:]  # Remove '--- a/'
                        elif line.startswith("+++ b/"):
                            test_file_path = line[6:]  # Remove '+++ b/'
                        break

            if test_file_path:
                # Validate patch line numbers and content
                logger.info(f"🔍 Validating patch against {test_file_path}")
                is_valid, reason = validate_patch_line_numbers(current_patch, test_file_path)

                if is_valid:
                    logger.info("✅ Patch validation passed")

                    # Try to apply the patch
                    if apply_unified_diff(".", current_patch):
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
                            return True, current_patch
                        else:
                            logger.error("❌ Tests still failing after patch - fix didn't work")
                            # Generate feedback for the LLM
                            feedback = (
                                f"Patch applied but tests still fail. Test output:\n"
                                f"{result.stdout}\n{result.stderr}"
                            )
                    else:
                        feedback = "Patch failed to apply due to git apply error"
                else:
                    logger.warning(f"⚠️ Patch validation failed: {reason}")
                    feedback = f"Patch validation failed: {reason}"
            else:
                feedback = "Could not extract test file path from patch"

        # If we're not on the last attempt, try to get the LLM to fix it
        if attempt < max_attempts - 1:
            logger.info("🔄 Asking LLM to correct the patch...")

            # Create feedback context
            feedback_context = f"""
{original_context}

PATCH VALIDATION FEEDBACK (Attempt {attempt + 1}):
Your previous patch failed: {feedback}

Please generate a corrected patch that addresses these validation issues.
Make sure to:
1. Only reference line numbers that actually exist in the file
2. Match the exact content of the lines you're trying to change
3. Generate a valid unified diff format with a/ and b/ prefixes
4. Focus on fixing the actual failing tests shown in the context

PREVIOUS FAILED PATCH:
{current_patch}
"""

            # Get corrected patch from LLM
            corrected_patch = generate_test_patch(
                f"CORRECTION NEEDED: {feedback}", feedback_context
            )

            if corrected_patch:
                current_patch = corrected_patch
                logger.info("🔄 LLM generated corrected patch, retrying...")
                continue
            else:
                logger.error("❌ LLM failed to generate corrected patch")
                break
        else:
            logger.error(f"❌ Max attempts ({max_attempts}) reached, giving up")
            logger.error(f"Final failure reason: {feedback}")
            break

    return False, current_patch


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


def show_sentries_banner() -> None:
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

    # Generate test patch with feedback loop
    diff_str = generate_test_patch(plan, context)
    if not diff_str:
        exit_noop("Could not generate test patch")

    # Apply and test with feedback loop (max 3 attempts)
    logger.info("🔄 Starting patch application with feedback loop...")
    success, final_patch = apply_and_test_patch_with_feedback(
        diff_str, context, plan, max_attempts=3
    )

    if not success:
        exit_noop("Patch application or testing failed after 3 attempts")

    # Create PR only if we have a working fix
    diff_summary = extract_diff_summary(final_patch)
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
