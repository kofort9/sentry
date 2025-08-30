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
from .intelligent_analysis import create_smart_context
from .patch_engine import create_patch_engine
from .prompts import PATCHER_TESTS
from .runner_common import (
    MODEL_PATCH,
    MODEL_PLAN,
    exit_noop,
    exit_success,
    get_logger,
    validate_environment,
)
from .smart_prompts import SmartPrompts

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


def get_smart_context_packs(test_output: str) -> list:
    """
    Get smart context packs with intelligent failure analysis.

    Args:
        test_output: pytest output with failures

    Returns:
        List of ContextPack objects with targeted context for each failure
    """
    logger.info("🧠 Creating smart context packs with failure classification...")

    context_packs = create_smart_context(test_output)

    logger.info(f"📦 Generated {len(context_packs)} smart context packs")
    for pack in context_packs:
        logger.info(
            f"  - {pack.failure_info.test_function}: {pack.failure_info.failure_type.value} "
            f"({pack.context_size} chars)"
        )

    return context_packs


def generate_smart_patch_json(context_pack, plan: str) -> Optional[str]:
    """
    Generate test patch using smart prompts and targeted context.

    Args:
        context_pack: ContextPack with failure-specific information
        plan: Plan for fixing tests

    Returns:
        Generated patch string or None if failed
    """
    logger.info(f"🔧 Generating smart patch for {context_pack.failure_info.failure_type.value}...")

    # Get failure-type-specific patcher prompt
    patcher_prompt_template = SmartPrompts.get_patcher_prompt(
        context_pack.failure_info.failure_type
    )

    # Format context with failure-type-specific guidance
    formatted_context = SmartPrompts.format_context_for_failure(
        context_pack.context_parts, context_pack.failure_info.failure_type
    )

    # Add find candidates if available
    if context_pack.find_candidates:
        formatted_context += "\n\n=== Suggested Find Candidates (AST-normalized) ==="
        for candidate in context_pack.find_candidates:
            formatted_context += f"\n- {candidate}"

    patcher_prompt = f"""Plan: {plan}

CRITICAL INSTRUCTION: Copy text ONLY from the source code sections below.
DO NOT copy from pytest error messages or failure summaries.
Pay extreme attention to whitespace - spaces, tabs, and newlines must match exactly.

{formatted_context}

Generate JSON operations to fix the failing tests.
COPY EXACT TEXT (including all whitespace) from the source code sections above."""

    patcher_response = chat(
        model=str(MODEL_PATCH),
        messages=[
            {"role": "system", "content": patcher_prompt_template},
            {"role": "user", "content": patcher_prompt},
        ],
        temperature=0.1,
        max_tokens=int(get_default_params("patcher")["max_tokens"]),
    )

    logger.info(
        f"🔧 Smart Patcher Response "
        f"({context_pack.failure_info.failure_type.value}):\n{patcher_response}"
    )

    # Try to process the response (same validation as before)
    try:
        # Try to parse as JSON first
        data = json.loads(patcher_response)

        # Check for abort responses (new consistent format)
        if "abort" in data:
            abort_reason = data["abort"]
            if abort_reason in ["out_of_scope", "cannot_comply", "exact_match_not_found"]:
                logger.warning(f"⚠️ Smart patcher aborted: {abort_reason}")
                return None
            else:
                logger.warning(f"⚠️ Smart patcher aborted with invalid reason: {abort_reason}")
                return None

        # Check for valid operations
        if "ops" in data and isinstance(data["ops"], list):
            logger.info("✅ Smart patcher generated valid JSON operations")
            return patcher_response

        logger.warning("⚠️ Smart patcher response missing 'ops' key")

    except json.JSONDecodeError:
        logger.warning("⚠️ Smart patcher response is not valid JSON")

    # Retry with smaller context and explicit JSON requirement
    logger.info("🔄 Retrying smart patcher with minimal context...")

    # Use only the test function and error for retry
    minimal_context = "\n".join(context_pack.context_parts[:2])  # Test function + failure info

    retry_prompt = f"""Plan: {plan}

CRITICAL: You MUST respond with ONLY valid JSON.

Source code excerpt (copy exact text from the source code, NOT pytest output):

{minimal_context}

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
            {"role": "system", "content": patcher_prompt_template},
            {"role": "user", "content": retry_prompt},
        ],
        temperature=0.1,
        max_tokens=int(get_default_params("patcher")["max_tokens"]),
    )

    logger.info(f"🔧 Smart Patcher Retry Response:\n{retry_response}")

    # Try to process retry response
    try:
        # Try to parse as JSON first
        data = json.loads(retry_response)

        # Check for abort responses
        if "abort" in data:
            abort_reason = data["abort"]
            if abort_reason in ["out_of_scope", "cannot_comply", "exact_match_not_found"]:
                logger.warning(f"⚠️ Smart patcher retry aborted: {abort_reason}")
                return None
            else:
                reason_msg = f"⚠️ Smart patcher retry aborted with invalid reason: {abort_reason}"
                logger.warning(reason_msg)
            return None

        # Check for valid operations
        if "ops" in data and isinstance(data["ops"], list):
            logger.info("✅ Smart patcher retry generated valid JSON operations")
            return retry_response

        logger.warning("⚠️ Smart patcher retry response missing 'ops' key")
        return None

    except json.JSONDecodeError:
        logger.warning("⚠️ Smart patcher retry response is not valid JSON")
        return None


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
    logger.info("🧪 TestSentry v3 starting with Smart Analysis + Patch Engine...")

    # Validate environment
    if not validate_environment():
        exit_noop("Environment validation failed")

    # Discover test failures
    failing_tests = discover_test_failures()
    if not failing_tests:
        exit_success("No test failures detected")

    logger.info("❌ Test failures detected, starting AI-powered fix process...")

    # Get smart context packs with failure classification
    context_packs = get_smart_context_packs(failing_tests)
    if not context_packs:
        exit_noop("No failures could be classified for smart processing")

    # Process each failure type separately for optimal results
    successful_fixes = 0

    for i, context_pack in enumerate(context_packs, 1):
        failure_info = context_pack.failure_info
        logger.info(
            f"🎯 Processing failure {i}/{len(context_packs)}: "
            f"{failure_info.test_function} ({failure_info.failure_type.value})"
        )

        # Get failure-type-specific planner prompt
        planner_prompt_template = SmartPrompts.get_planner_prompt(failure_info.failure_type)

        # Format context for this specific failure
        formatted_context = SmartPrompts.format_context_for_failure(
            context_pack.context_parts, failure_info.failure_type
        )

        failure_type = failure_info.failure_type.value
        planner_prompt = f"""Analyze this {failure_type} failure and plan minimal fixes:

{formatted_context}

Focus on fixing: {failure_info.test_function} in {failure_info.test_file}
Error: {failure_info.error_message}

Remember: ONLY modify files under tests/** (and sentries/test_*.py).
NEVER edit configs, allowlists, or non-test modules.
If fix requires non-test changes, reply: {{"abort": "out_of_scope"}}"""

        logger.info(f"🤖 Calling Smart LLM Planner for {failure_info.failure_type.value}...")

        planner_response = chat(
            model=str(MODEL_PLAN),
            messages=[
                {"role": "system", "content": planner_prompt_template},
                {"role": "user", "content": planner_prompt},
            ],
            temperature=0.1,
            max_tokens=int(get_default_params("planner")["max_tokens"]),
        )

        logger.info(
            f"🧠 Smart Planner Response ({failure_info.failure_type.value}):\n{planner_response}"
        )

        # Validate planner scope
        is_valid, reason = validate_planner_scope(planner_response)
        if not is_valid:
            logger.warning(
                f"⚠️ Planner scope validation failed for {failure_info.test_function}: {reason}"
            )
            continue  # Skip this failure, try next one

        # Extract plan from valid response
        try:
            plan_data = json.loads(planner_response)
            plan = plan_data.get("plan", "Fix failing tests")
        except json.JSONDecodeError:
            plan = "Fix failing tests"
            logger.warning("Could not parse planner response, using default plan")

        # Generate patch using smart prompts and targeted context
        patch_json = generate_smart_patch_json(context_pack, plan)
        if not patch_json:
            logger.warning(f"⚠️ Failed to generate patch for {failure_info.test_function}")
            continue  # Skip this failure, try next one

        # Apply patch using patch engine
        logger.info(f"🔨 Applying smart patch for {failure_info.test_function}...")
        success, feedback = apply_and_test_patch_with_engine(patch_json, failure_info.test_file)

        if success:
            logger.info(
                f"✅ Smart fix applied successfully for {failure_info.test_function}: {feedback}"
            )
            successful_fixes += 1
            # For now, process one fix at a time to avoid conflicts
            break
        else:
            logger.warning(f"❌ Smart patch failed for {failure_info.test_function}: {feedback}")
            continue

    # Report results
    if successful_fixes == 0:
        exit_noop(f"No fixes could be applied. Processed {len(context_packs)} classified failures.")

    logger.info("✅ Smart fixes applied successfully!")
    success = True
    feedback = (
        f"Smart TestSentry successfully fixed {successful_fixes}/{len(context_packs)} failures"
    )

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
        # Get the test file that was actually fixed
        try:
            data = json.loads(patch_json)
            test_files = [op.get("file", "") for op in data.get("ops", [])]
            if test_files:
                test_file_path = test_files[0]
            else:
                test_file_path = "tests/"
        except Exception:
            test_file_path = "tests/"

        subprocess.run(["git", "add", test_file_path], cwd=".")
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"fix: {plan}\n\nApplied by TestSentry using Smart Analysis + Patch Engine v3",
            ],
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
