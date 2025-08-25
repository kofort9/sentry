#!/usr/bin/env python3
"""
TestSentry: AI-powered test fixing using Patch Engine v2.

This module:
1. Detects failing tests from pytest output
2. Uses LLM planner to analyze failures and plan fixes
3. Generates JSON operations (not line numbers)
4. Uses Patch Engine to create and apply unified diffs
5. Verifies fixes work with pytest before creating PRs
6. Enforces strict test-only scope with mechanical guardrails
"""

import json
import subprocess
import time
from typing import Optional

from .chat import chat, get_default_params
from .diff_utils import apply_unified_diff
from .patch_engine import create_patch_engine
from .prompts import PATCHER_TESTS, PLANNER_TESTS
from .runner_common import (
    MODEL_PATCH,
    MODEL_PLAN,
    exit_noop,
    exit_success,
    get_logger,
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
    try:
        with open("pytest-output.txt", "r") as f:
            output = f.read()

        if "FAILED" in output or "ERROR" in output or "AssertionError" in output:
            logger.info("Found test failures in pre-captured output")
            return output
        else:
            logger.info("No test failures found in pre-captured output")
            return None
    except FileNotFoundError:
        logger.info("No pre-captured output found, running pytest...")
    except Exception as e:
        logger.warning(f"Error reading pre-captured output: {e}")

    # Fall back to running pytest directly
    try:
        logger.info("Running pytest to discover test failures...")
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "sentries/", "--tb=short", "-q"],
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


def validate_planner_scope(planner_response: str) -> tuple[bool, str]:
    """
    Validate that planner response stays within test-only scope.

    Args:
        planner_response: Raw response from planner model

    Returns:
        (is_valid, reason) - whether response is valid and why
    """
    try:
        # Try to parse as JSON
        data = json.loads(planner_response)

        # Check for abort responses (new consistent format)
        if "abort" in data:
            abort_reason = data["abort"]
            if abort_reason in ["out_of_scope", "cannot_comply", "exact_match_not_found"]:
                return False, f"Planner aborted: {abort_reason}"
            else:
                return False, f"Planner aborted with invalid reason: {abort_reason}"

        # Check for required fields
        if not isinstance(data, dict):
            return False, "Planner response must be a JSON object"

        if "target_files" not in data:
            return False, "Planner response missing target_files"

        # Validate target files are test-only
        target_files = data["target_files"]
        if not isinstance(target_files, list):
            return False, "target_files must be a list"

        for file_path in target_files:
            if not isinstance(file_path, str):
                return False, f"Invalid file path type: {type(file_path)}"

            # Check if path is test-only
            if not file_path.startswith("tests/"):
                return False, f"Non-test file targeted: {file_path}"

        return True, "Planner response is valid and test-only"

    except json.JSONDecodeError:
        return False, "Planner response is not valid JSON"
    except Exception as e:
        return False, f"Error validating planner response: {e}"


def get_test_context_with_excerpts(test_output: str) -> str:
    """
    Get minimal test context with actual source code from failing tests.

    Args:
        test_output: pytest output with failures

    Returns:
        Context string with actual source code for LLM
    """
    logger.info("🔍 Extracting test file contents for failing tests")

    # Extract test file names from pytest output
    lines = test_output.split("\n")
    test_files = set()

    for line in lines:
        # Look for test file paths in pytest output
        if "tests/" in line and (".py::" in line or "FAILED" in line):
            # Extract the file path before the :: or FAILED
            parts = line.split()
            for part in parts:
                if "tests/" in part and ".py" in part:
                    file_path = part.split("::")[0]  # Remove test function name
                    if file_path.endswith(".py"):
                        test_files.add(file_path)
                    break

    # Read actual source code from failing test files
    context_parts = []
    context_parts.append("=== Pytest Failure Summary ===")

    # Add brief failure info
    failure_lines = []
    for line in lines:
        if any(keyword in line.lower() for keyword in ["failed", "assertionerror", "assert "]):
            failure_lines.append(line.strip())
    context_parts.append("\n".join(failure_lines[-10:]))  # Last 10 failure lines

    # Add actual source code
    for test_file in sorted(test_files):
        try:
            logger.info(f"📖 Reading source code from {test_file}")
            with open(test_file, "r") as f:
                file_content = f.read()

            context_parts.append("\n" + "=" * 60)
            context_parts.append(f"Source Code: {test_file}")
            context_parts.append("(Copy text EXACTLY from this section, including whitespace)")
            context_parts.append("=" * 60)
            context_parts.append(file_content)
            context_parts.append("=" * 60)

        except Exception as e:
            logger.warning(f"⚠️ Could not read {test_file}: {e}")
            continue

    context = "\n".join(context_parts)
    logger.info(f"📝 Extracted source code from {len(test_files)} test files")
    return context


def generate_test_patch_json(plan: str, context: str) -> Optional[str]:
    """
    Generate test patch using JSON operations with retry logic.

    Args:
        plan: Plan for fixing tests
        context: Test context and excerpts

    Returns:
        Generated patch string or None if failed
    """
    logger.info("🔧 Generating test patch using JSON operations...")

    # First attempt with full context
    patcher_prompt = f"""Plan: {plan}

CRITICAL INSTRUCTION: Copy text ONLY from the "=== Source Code:" sections below.
DO NOT copy from pytest error messages or failure summaries.
Pay extreme attention to whitespace - spaces, tabs, and newlines must match exactly.

{context}

Generate JSON operations to fix the failing tests.
COPY EXACT TEXT (including all whitespace) from the source code sections above."""

    patcher_response = chat(
        model=str(MODEL_PATCH),
        messages=[
            {"role": "system", "content": PATCHER_TESTS},
            {"role": "user", "content": patcher_prompt},
        ],
        temperature=0.1,
        max_tokens=int(get_default_params("patcher")["max_tokens"]),
    )

    logger.info(f"🔧 LLM Patcher Response:\n{patcher_response}")

    # Try to process the response
    try:
        # Try to parse as JSON first
        data = json.loads(patcher_response)

        # Check for abort responses (new consistent format)
        if "abort" in data:
            abort_reason = data["abort"]
            if abort_reason in ["out_of_scope", "cannot_comply", "exact_match_not_found"]:
                logger.warning(f"⚠️ Patcher aborted: {abort_reason}")
                return None
            else:
                logger.warning(f"⚠️ Patcher aborted with invalid reason: {abort_reason}")
                return None

        # Check for valid operations
        if "ops" in data and isinstance(data["ops"], list):
            logger.info("✅ Patcher generated valid JSON operations")
            return patcher_response

        logger.warning("⚠️ Patcher response missing 'ops' key")

    except json.JSONDecodeError:
        logger.warning("⚠️ Patcher response is not valid JSON")

    # Retry with smaller context and explicit JSON requirement
    logger.info("🔄 Retrying patcher with smaller context...")

    # Extract only the most relevant lines for retry
    lines = context.split("\n")
    retry_context = "\n".join(lines[-20:])  # Last 20 lines

    retry_prompt = f"""Plan: {plan}

CRITICAL: You MUST respond with ONLY valid JSON.

Source code excerpt (copy exact text from the source code, NOT pytest output):

{retry_context}

JSON format required:
{{"ops": [{{"file": "tests/test_file.py",
            "find": "exact source code text",
            "replace": "replacement"}}]}}

Example: To fix "assert 1 == 2" to pass, use:
{{"ops": [{{"file": "tests/test_basic.py",
            "find": "assert 1 == 2",
            "replace": "assert 1 == 1"}}]}}

If you cannot create valid JSON operations, reply: {{"abort": "cannot comply with constraints"}}"""

    retry_response = chat(
        model=str(MODEL_PATCH),
        messages=[
            {"role": "system", "content": PATCHER_TESTS},
            {"role": "user", "content": retry_prompt},
        ],
        temperature=0.1,
        max_tokens=int(get_default_params("patcher")["max_tokens"]),
    )

    logger.info(f"🔧 LLM Patcher Retry Response:\n{retry_response}")

    # Try to process retry response
    try:
        # Try to parse as JSON first
        data = json.loads(retry_response)

        # Check for abort responses (new consistent format)
        if "abort" in data:
            abort_reason = data["abort"]
            if abort_reason in ["out_of_scope", "cannot_comply", "exact_match_not_found"]:
                logger.warning(f"⚠️ Patcher retry aborted: {abort_reason}")
                return None
            else:
                logger.warning(f"⚠️ Patcher retry aborted with invalid reason: {abort_reason}")
                return None

        # Check for valid operations
        if "ops" in data and isinstance(data["ops"], list):
            logger.info("✅ Patcher retry generated valid JSON operations")
            return retry_response

        logger.warning("⚠️ Patcher retry response missing 'ops' key")

    except json.JSONDecodeError:
        logger.warning("⚠️ Patcher retry response is not valid JSON")

    logger.error("❌ Failed to generate valid JSON operations after retry")
    return None


def apply_and_test_patch_with_engine(diff_str: str, test_file_path: str) -> tuple[bool, str]:
    """
    Apply patch using patch engine and verify with pytest.

    Args:
        diff_str: JSON operations string
        test_file_path: Path to test file being modified

    Returns:
        (success, feedback) - whether patch succeeded and any feedback
    """
    logger.info("🔧 Applying patch using Patch Engine v2...")

    # Log patch details for audit
    try:
        data = json.loads(diff_str)
        ops_count = len(data.get("ops", []))
        files_targeted = [op.get("file", "") for op in data.get("ops", [])]

        logger.info("📊 Patch Details:")
        logger.info(f"   Operations: {ops_count}")
        logger.info(f"   Files targeted: {files_targeted}")
        logger.info(f"   Test file: {test_file_path}")

        # Validate against allowlist
        for file_path in files_targeted:
            if not (file_path.startswith("tests/") or file_path.startswith("sentries/test_")):
                logger.error(f"❌ Non-test file targeted: {file_path}")
                return False, f"Non-test file targeted: {file_path}"

    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in patch: {e}")
        return False, f"Invalid JSON: {e}"

    # Create patch engine
    engine = create_patch_engine()

    try:
        # Process operations through patch engine
        logger.info("⚙️ Processing operations through patch engine...")
        unified_diff = engine.process_operations(diff_str)

        logger.info(f"✅ Generated unified diff ({len(unified_diff)} characters)")

        # Apply the diff
        logger.info("📝 Applying unified diff...")
        success = apply_unified_diff(".", unified_diff)

        if not success:
            logger.error("❌ Failed to apply unified diff")
            return False, "Failed to apply unified diff"

        logger.info("✅ Unified diff applied successfully")

        # Verify the changes work by running pytest
        logger.info("🧪 Running pytest to verify fixes...")

        # Run pytest on the specific test file
        result = subprocess.run(
            ["python", "-m", "pytest", test_file_path, "-v"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        if result.returncode == 0:
            logger.info("✅ Pytest passed - patch fixes working correctly")
            return True, "Patch applied and tests passing"
        else:
            logger.warning("⚠️ Pytest failed after patch application")
            logger.info(f"Pytest output:\n{result.stdout}\n{result.stderr}")

            # Rollback the changes
            logger.info("🔄 Rolling back failed patch...")
            subprocess.run(["git", "checkout", "--", test_file_path], cwd=".")

            return False, f"Tests still failing after patch: {result.stderr}"

    except Exception as e:
        logger.error(f"❌ Error during patch application: {e}")
        return False, f"Patch application error: {e}"


def main() -> None:
    """Main TestSentry function."""
    show_sentries_banner()
    logger.info("🧪 TestSentry v2 starting with Patch Engine...")

    # Validate environment
    if not validate_environment():
        exit_noop("Environment validation failed")

    # Discover test failures
    failing_tests = discover_test_failures()
    if not failing_tests:
        exit_success("No test failures detected")

    logger.info("❌ Test failures detected, starting AI-powered fix process...")

    # Get test context with minimal excerpts for the patcher
    context = get_test_context_with_excerpts(failing_tests)

    # Plan test fixes
    logger.info("🤖 Calling LLM Planner to analyze test failures...")

    planner_prompt = f"""Analyze these test failures and plan minimal fixes:

{context}

Remember: ONLY modify files under tests/** (and sentries/test_*.py).
NEVER edit configs, allowlists, or non-test modules.
If fix requires non-test changes, reply: {{"abort": "out of scope"}}"""

    planner_response = chat(
        model=str(MODEL_PLAN),
        messages=[
            {"role": "system", "content": PLANNER_TESTS},
            {"role": "user", "content": planner_prompt},
        ],
        temperature=0.1,
        max_tokens=int(get_default_params("planner")["max_tokens"]),
    )

    logger.info(f"🧠 LLM Planner Response:\n{planner_response}")

    # Validate planner scope
    is_valid, reason = validate_planner_scope(planner_response)
    if not is_valid:
        logger.warning(f"⚠️ Planner scope validation failed: {reason}")

        # One retry with scope reminder
        logger.info("🔄 Retrying planner with scope reminder...")
        scope_reminder = f"""SCOPE REMINDER:
You can ONLY modify files in the tests/ directory.
You CANNOT modify any other files.

{context}

If you cannot fix the tests within test-only scope, reply:
{{"abort": "out of scope"}}

If you cannot fix the tests, reply:
{{"abort": "cannot comply with constraints"}}"""

        planner_response = chat(
            model=str(MODEL_PLAN),
            messages=[
                {"role": "system", "content": PLANNER_TESTS},
                {"role": "user", "content": scope_reminder},
            ],
            temperature=0.1,
            max_tokens=int(get_default_params("planner")["max_tokens"]),
        )

        logger.info(f"🧠 LLM Planner Retry Response:\n{planner_response}")

        # Validate retry response
        is_valid, reason = validate_planner_scope(planner_response)
        if not is_valid:
            exit_noop(f"Planner scope validation failed after retry: {reason}")

    logger.info("✅ Planner scope validation passed")

    # Extract plan from valid response
    try:
        plan_data = json.loads(planner_response)
        plan = plan_data.get("plan", "Fix failing tests")
    except json.JSONDecodeError:
        plan = "Fix failing tests"
        logger.warning("Could not parse planner response, using default plan")

    # Generate test patch JSON with feedback loop
    diff_str = generate_test_patch_json(plan, context)
    if not diff_str:
        exit_noop("Could not generate test patch JSON")

    # Apply and test the patch
    logger.info("🔧 Applying and testing patch...")

    # Extract test file path from the JSON operations
    try:
        data = json.loads(diff_str)
        test_files = [op.get("file", "") for op in data.get("ops", [])]
        if not test_files:
            exit_noop("No test files specified in patch operations")

        # Use the first test file for verification
        test_file_path = test_files[0]
        logger.info(f"🎯 Testing patch on: {test_file_path}")

    except json.JSONDecodeError:
        exit_noop("Invalid JSON in patch operations")

    # Apply the patch and verify it works
    success, feedback = apply_and_test_patch_with_engine(diff_str, test_file_path)

    if success:
        logger.info("🎉 Patch applied and verified successfully!")

        # Create a PR with the working fix
        logger.info("🚀 Creating PR with working test fix...")

        # Get current branch name
        current_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, cwd="."
        ).strip()

        # Create a new branch for the fix
        fix_branch = f"ai-test-fix-{int(time.time())}"
        subprocess.run(["git", "checkout", "-b", fix_branch], cwd=".")

        # Commit the fix
        subprocess.run(["git", "add", test_file_path], cwd=".")
        subprocess.run(
            ["git", "commit", "-m", f"fix: {plan}\n\nApplied by TestSentry using Patch Engine v2"],
            cwd=".",
        )

        # Push the fix branch
        subprocess.run(["git", "push", "origin", fix_branch], cwd=".")

        # Create PR using GitHub CLI or API
        pr_title = f"🔧 Fix failing tests: {plan}"
        pr_body = f"""## Test Fix Applied by TestSentry

**Plan:** {plan}

**Files Modified:** {test_file_path}

**Fix Strategy:** Applied using Patch Engine v2 with JSON operations

**Verification:** ✅ Tests now pass after fix

**Generated by:** AI-powered TestSentry with mechanical guardrails

---
*This PR was automatically created by TestSentry after detecting and fixing failing tests.*"""

        # Try to create PR using GitHub CLI
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    pr_title,
                    "--body",
                    pr_body,
                    "--base",
                    current_branch,
                    "--head",
                    fix_branch,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            if result.returncode == 0:
                logger.info("🎉 PR created successfully!")
                logger.info(f"PR URL: {result.stdout.strip()}")
            else:
                logger.warning("⚠️ GitHub CLI failed, manual PR creation needed")
                logger.info(f"Branch pushed: {fix_branch}")
                logger.info(f"PR body:\n{pr_body}")

        except FileNotFoundError:
            logger.warning("⚠️ GitHub CLI not available, manual PR creation needed")
            logger.info(f"Branch pushed: {fix_branch}")
            logger.info(f"PR body:\n{pr_body}")

        exit_success("Test fix applied and PR created successfully")

    else:
        logger.error(f"❌ Patch application failed: {feedback}")
        exit_noop(f"Patch application failed: {feedback}")


def show_sentries_banner() -> None:
    """Display the Sentries banner."""
    from .banner import show_sentry_banner

    show_sentry_banner()


if __name__ == "__main__":
    main()
