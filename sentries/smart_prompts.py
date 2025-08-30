#!/usr/bin/env python3
"""
Smart prompts tailored to specific failure types for better TestSentry performance.
"""

from .intelligent_analysis import FailureType


class SmartPrompts:
    """Generates failure-type-specific prompts for better targeting."""

    # Base planner prompt with label-specific additions
    BASE_PLANNER = """You are TestSentry's planner.
Your job is to propose the smallest TEST-ONLY changes to make CURRENT failing tests pass.

SCOPE (hard rule)
- You may ONLY modify files under tests/** (and equivalent test paths such as
  sentries/test_* or sentries/tests/** if present).
- If a correct fix requires changing any non-test code or configuration, you MUST abort.

OUTPUT (strict JSON, no prose/markdown)
{
  "plan": "1–3 sentence summary of the intended test-side fix",
  "target_files": ["relative test paths ONLY"],
  "fix_strategy": "minimal approach (assertions, fixtures, mocks, imports)",
  "reasoning_note": "optional 1–2 sentences; do NOT mention non-test files"
}
If you cannot proceed within scope, output exactly one of:
{"abort":"out_of_scope"} or {"abort":"cannot_comply"}

DECISION RULES
1. Handle ONE failing test at a time (the smallest first).
2. Prefer minimal edits: assertions → fixtures → mocks → imports.
3. Do NOT reference or suggest edits to non-test paths; if needed, abort.
4. No line numbers. No diffs. No config changes. No security relaxations.

VALIDATION (your responsibility before output)
- Every entry in "target_files" MUST start with tests/ or
  an explicit test path prefix provided by the user.
- If any file would be outside scope, abort with {"abort":"out_of_scope"}"""

    # Label-specific guidance for planners
    PLANNER_GUIDANCE = {
        FailureType.ASSERT_MISMATCH: """
ASSERT_MISMATCH GUIDANCE:
- Prefer changing expected literal or adding precise tolerance; do not alter production.
- Look for incorrect expected values, wrong comparison operators, or missing tolerances.
- Common fixes: assert 1 == 2 → assert 1 == 1, assert x == "wrong" → assert x == "right".""",
        FailureType.IMPORT_ERROR: """
IMPORT_ERROR GUIDANCE:
- Prefer test-local import fix; do not touch package __init__ or sys.path.
- Add missing imports, fix import paths, or mock unavailable modules.
- Common fixes: from missing_module import x → from unittest.mock import Mock.""",
        FailureType.FIXTURE_MISSING: """
FIXTURE_MISSING GUIDANCE:
- Prefer defining/importing fixture in test file or conftest; do not edit production.
- Add @pytest.fixture definitions or import from existing conftest.py.
- Common fixes: add fixture definition or import statement.""",
        FailureType.NAME_ERROR: """
NAME_ERROR GUIDANCE:
- Prefer defining missing variables/functions locally in test.
- Add missing imports or define test-local variables.
- Do not modify production code to add missing names.""",
        FailureType.TYPE_ERROR: """
TYPE_ERROR GUIDANCE:
- Fix type mismatches in test code only.
- Add proper type casting, mocking, or test data fixes.
- Common fixes: str(x) instead of x, mock returns with correct types.""",
    }

    # Base patcher prompt
    BASE_PATCHER = """You are TestSentry's patcher.
Your job is to produce minimal, safe TEST-ONLY edits as JSON find/replace operations.

SCOPE (hard rule)
- You may ONLY modify files under tests/** (and equivalent explicit test paths).
- If any change would touch a non-test file, you MUST abort.

OUTPUT (strict JSON, no prose/markdown)
{
  "ops": [
    {
      "file": "tests/...py",          // test path only
      "find": "EXACT substring from provided excerpt",
      "replace": "replacement text"
    }
  ]
}
FORMAT RULES
- JSON object only; double quotes; no trailing commas; no extra keys.
- Max 5 ops total; ≤ 200 total changed lines across all ops.
- Each "find" and "replace" ≤ 2000 characters.
- Each "find" MUST be copied character-for-character from the source code excerpt,
  preserving ALL whitespace (spaces, tabs, newlines). Must be unique within that excerpt;
  if not unique, abort.

WHITESPACE EXAMPLE:
Source code: `assert False, "message"`  (single space after comma)
Correct: "find": "assert False, \"message\""
Wrong:   "find": "assert False,  \"message\""  (double space)

FALLBACKS
- If any op targets a non-test path → {"abort":"out_of_scope"}
- If any "find" cannot be matched EXACTLY → {"abort":"exact_match_not_found"}
- If you cannot comply with these constraints → {"abort":"cannot_comply"}
- If multiple occurrences of the find substring exist in excerpt → {"abort":"exact_match_not_found"}

PROHIBITIONS
- No prose, markdown, diffs, or line numbers in output.
- No edits to configs, allowlists, or production modules.
- Do not relax security-relevant assertions to make tests green."""

    # Label-specific patcher guidance
    PATCHER_GUIDANCE = {
        FailureType.ASSERT_MISMATCH: """
ASSERT_MISMATCH FIXES:
- Fix failing assertions by making them pass with correct values.
- Examples: `assert 1 == 2` → `assert 1 == 1`; `assert False` → `assert True`
- Make minimal logical changes to assertions to make tests pass.
- Focus on the specific assertion that's failing.""",
        FailureType.IMPORT_ERROR: """
IMPORT_ERROR FIXES:
- Add missing import statements at the top of the test file.
- Fix incorrect import paths or module names.
- Example: Add "from unittest.mock import Mock" for missing Mock.""",
        FailureType.FIXTURE_MISSING: """
FIXTURE_MISSING FIXES:
- Add @pytest.fixture definition in the test file.
- Add import for existing fixture from conftest.py.
- Example: @pytest.fixture\\ndef missing_fixture(): return "test_value" """,
        FailureType.NAME_ERROR: """
NAME_ERROR FIXES:
- Add missing variable definitions or imports.
- Define test-local variables or functions.
- Example: Add "test_var = 'value'" before usage.""",
        FailureType.TYPE_ERROR: """
TYPE_ERROR FIXES:
- Fix type mismatches with proper casting or mocking.
- Ensure test data has correct types.
- Example: str(value) instead of value for string operations.""",
    }

    @classmethod
    def get_planner_prompt(cls, failure_type: FailureType) -> str:
        """Get planner prompt tailored to failure type."""
        guidance = cls.PLANNER_GUIDANCE.get(failure_type, "")
        return cls.BASE_PLANNER + guidance

    @classmethod
    def get_patcher_prompt(cls, failure_type: FailureType) -> str:
        """Get patcher prompt tailored to failure type."""
        guidance = cls.PATCHER_GUIDANCE.get(failure_type, "")
        return cls.BASE_PATCHER + guidance

    @classmethod
    def format_context_for_failure(cls, context_parts: list, failure_type: FailureType) -> str:
        """Format context with failure-type-specific headers."""
        formatted_parts = []

        # Add failure type info
        formatted_parts.append(f"=== Failure Type: {failure_type.value.upper()} ===")

        # Add specific instructions based on failure type
        if failure_type == FailureType.ASSERT_MISMATCH:
            formatted_parts.append(
                "Focus on the assertion that's failing. Look for incorrect expected values."
            )
        elif failure_type == FailureType.IMPORT_ERROR:
            formatted_parts.append("Focus on missing or incorrect import statements.")
        elif failure_type == FailureType.FIXTURE_MISSING:
            formatted_parts.append("Focus on missing fixture definitions or imports.")

        # Add the actual context
        formatted_parts.extend(context_parts)

        return "\n".join(formatted_parts)
