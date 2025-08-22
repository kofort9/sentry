#!/usr/bin/env python3
"""
Unit tests for the patch engine module.
"""

import json
import tempfile
import unittest
from pathlib import Path

from .patch_engine import (
    NoEffectiveChangeError,
    PatchEngine,
    PatchOperation,
    ValidationError,
)


class TestPatchOperation(unittest.TestCase):
    """Test the PatchOperation dataclass."""

    def test_valid_operation(self) -> None:
        """Test creating a valid operation."""
        op = PatchOperation(file="test_file.py", find="old text", replace="new text")
        self.assertEqual(op.file, "test_file.py")
        self.assertEqual(op.find, "old text")
        self.assertEqual(op.replace, "new text")

    def test_invalid_file(self) -> None:
        """Test that empty file raises error."""
        with self.assertRaises(ValueError):
            PatchOperation(file="", find="old", replace="new")

    def test_invalid_find(self) -> None:
        """Test that empty find raises error."""
        with self.assertRaises(ValueError):
            PatchOperation(file="test.py", find="", replace="new")

    def test_invalid_replace_type(self) -> None:
        """Test that non-string replace raises error."""
        with self.assertRaises(ValueError):
            PatchOperation(file="test.py", find="old", replace=123)  # type: ignore[arg-type]


class TestPatchEngine(unittest.TestCase):
    """Test the PatchEngine class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a test-specific patch engine that allows temporary files
        self.engine = PatchEngine(
            allowed_paths={
                "tests/",
                "docs/",
                "README.md",
                "sentries/test_",
                "sentries/docsentry.py",
                "/tmp/",  # Allow temporary files for testing
                "/var/folders/",  # Allow macOS temp directories
            }
        )

        # Create temporary test directory
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_basic.py"

        # Create test file with failing assertion
        with open(self.test_file, "w") as f:
            f.write(
                """def test_intentional_failure():
    assert 1 == 2

def test_another_intentional_failure():
    assert False
"""
            )

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_is_path_allowed(self) -> None:
        """Test path allowlist checking."""
        # Allowed paths
        self.assertTrue(self.engine._is_path_allowed("tests/test_file.py"))
        self.assertTrue(self.engine._is_path_allowed("sentries/test_basic.py"))
        self.assertTrue(self.engine._is_path_allowed("README.md"))

        # Disallowed paths
        self.assertFalse(self.engine._is_path_allowed("src/main.py"))
        self.assertFalse(self.engine._is_path_allowed("config.py"))

    def test_validate_operations_success(self) -> None:
        """Test successful operation validation."""
        operations = [
            PatchOperation(file="tests/test_file.py", find="assert 1 == 2", replace="assert 1 == 1")
        ]

        # Should not raise
        self.engine.validate_operations(operations)

    def test_validate_operations_too_many(self) -> None:
        """Test validation fails with too many operations."""
        operations = [
            PatchOperation(file=f"tests/file{i}.py", find="old", replace="new")
            for i in range(6)  # More than MAX_FILES_CHANGED (5)
        ]

        with self.assertRaises(ValidationError) as cm:
            self.engine.validate_operations(operations)
        self.assertIn("Too many operations", str(cm.exception))

    def test_validate_operations_disallowed_path(self) -> None:
        """Test validation fails with disallowed path."""
        operations = [
            PatchOperation(file="src/main.py", find="old", replace="new")  # Not in allowlist
        ]

        with self.assertRaises(ValidationError) as cm:
            self.engine.validate_operations(operations)
        self.assertIn("not in allowlist", str(cm.exception))

    def test_apply_operations_to_file_success(self) -> None:
        """Test successful operation application to file."""
        operations = [
            PatchOperation(file=str(self.test_file), find="assert 1 == 2", replace="assert 1 == 1")
        ]

        original, modified = self.engine.apply_operations_to_file(str(self.test_file), operations)

        self.assertIn("assert 1 == 2", original)
        self.assertIn("assert 1 == 1", modified)
        self.assertNotIn("assert 1 == 2", modified)

    def test_apply_operations_to_file_find_not_found(self) -> None:
        """Test operation fails when find text not found."""
        operations = [
            PatchOperation(
                file=str(self.test_file),
                find="assert 1 == 999",  # Not in file
                replace="assert 1 == 1",
            )
        ]

        with self.assertRaises(ValidationError) as cm:
            self.engine.apply_operations_to_file(str(self.test_file), operations)
        self.assertIn("Find text not found", str(cm.exception))

    def test_build_unified_diff(self) -> None:
        """Test unified diff generation."""
        original = "line1\nline2\nline3\n"
        modified = "line1\nline2_modified\nline3\n"

        diff = self.engine.build_unified_diff("test.py", original, modified)

        # Should contain diff headers
        self.assertIn("--- a/test.py", diff)
        self.assertIn("+++ b/test.py", diff)
        # Should contain the change
        self.assertIn("-line2", diff)
        self.assertIn("+line2_modified", diff)

    def test_process_operations_success(self) -> None:
        """Test successful JSON processing."""
        # Create a test file in the temp directory
        test_file_path = Path(self.temp_dir) / "test_basic.py"
        with open(test_file_path, "w") as f:
            f.write(
                """def test_intentional_failure():
    assert 1 == 2

def test_another_intentional_failure():
    assert False
"""
            )

        operations_json = json.dumps(
            {
                "ops": [
                    {
                        "file": str(test_file_path),
                        "find": "assert 1 == 2",
                        "replace": "assert 1 == 1",
                    }
                ]
            }
        )

        diff = self.engine.process_operations(operations_json)

        # Should generate valid diff
        self.assertIn("--- a/", diff)
        self.assertIn("+++ b/", diff)
        # Check for the actual diff content (the format may vary)
        self.assertIn("assert 1 == 2", diff)
        self.assertIn("assert 1 == 1", diff)

    def test_process_operations_invalid_json(self) -> None:
        """Test processing fails with invalid JSON."""
        with self.assertRaises(ValidationError) as cm:
            self.engine.process_operations("invalid json")
        self.assertIn("Invalid JSON", str(cm.exception))

    def test_process_operations_missing_ops_key(self) -> None:
        """Test processing fails without ops key."""
        operations_json = json.dumps({"other": "data"})

        with self.assertRaises(ValidationError) as cm:
            self.engine.process_operations(operations_json)
        self.assertIn("must contain 'ops' key", str(cm.exception))

    def test_process_operations_empty_ops_list(self) -> None:
        """Test processing fails with empty ops list."""
        operations_json = json.dumps({"ops": []})

        with self.assertRaises(ValidationError) as cm:
            self.engine.process_operations(operations_json)
        self.assertIn("must be a non-empty list", str(cm.exception))

    def test_process_operations_missing_required_keys(self) -> None:
        """Test processing fails with missing operation keys."""
        operations_json = json.dumps(
            {
                "ops": [
                    {
                        "file": "test.py",
                        "find": "old",
                        # Missing "replace" key
                    }
                ]
            }
        )

        with self.assertRaises(ValidationError) as cm:
            self.engine.process_operations(operations_json)
        self.assertIn("Missing required keys", str(cm.exception))

    def test_process_operations_no_effective_change(self) -> None:
        """Test processing fails when no effective change would be made."""
        # Create a test file in the temp directory
        test_file_path = Path(self.temp_dir) / "test_basic.py"
        with open(test_file_path, "w") as f:
            f.write(
                """def test_intentional_failure():
    assert 1 == 2

def test_another_intentional_failure():
    assert False
"""
            )

        operations_json = json.dumps(
            {
                "ops": [
                    {
                        "file": str(test_file_path),
                        "find": "assert 1 == 2",
                        "replace": "assert 1 == 2",  # Same text
                    }
                ]
            }
        )

        with self.assertRaises(NoEffectiveChangeError) as cm:
            self.engine.process_operations(operations_json)
        self.assertIn("No effective changes would be made", str(cm.exception))

    def test_process_operations_multiple_files(self) -> None:
        """Test processing operations across multiple files."""
        # Create test files in the temp directory
        test_file1 = Path(self.temp_dir) / "test_basic.py"
        test_file2 = Path(self.temp_dir) / "test_another.py"

        with open(test_file1, "w") as f:
            f.write(
                """def test_intentional_failure():
    assert 1 == 2

def test_another_intentional_failure():
    assert False
"""
            )

        with open(test_file2, "w") as f:
            f.write("def test_something():\n    assert False\n")

        operations_json = json.dumps(
            {
                "ops": [
                    {"file": str(test_file1), "find": "assert 1 == 2", "replace": "assert 1 == 1"},
                    {"file": str(test_file2), "find": "assert False", "replace": "assert True"},
                ]
            }
        )

        diff = self.engine.process_operations(operations_json)

        # Should contain diffs for both files
        self.assertIn(str(test_file1), diff)
        self.assertIn(str(test_file2), diff)
        # Check for the actual diff content
        self.assertIn("assert 1 == 2", diff)
        self.assertIn("assert 1 == 1", diff)
        self.assertIn("assert False", diff)
        self.assertIn("assert True", diff)


class TestPatchEngineIntegration(unittest.TestCase):
    """Integration tests for the patch engine."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a test-specific patch engine that allows temporary files
        self.engine = PatchEngine(
            allowed_paths={
                "tests/",
                "docs/",
                "README.md",
                "sentries/test_",
                "sentries/docsentry.py",
                "/tmp/",  # Allow temporary files for testing
                "/var/folders/",  # Allow macOS temp directories
            }
        )

        # Create temporary test directory
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_basic.py"

        with open(self.test_file, "w") as f:
            f.write(
                """def test_intentional_failure():
    assert 1 == 2

def test_another_intentional_failure():
    assert False
"""
            )

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_end_to_end_fix_assertion(self) -> None:
        """Test end-to-end fixing of a failing assertion."""
        # This test simulates the exact scenario that was failing before
        operations_json = json.dumps(
            {
                "ops": [
                    {
                        "file": str(self.test_file),
                        "find": "assert 1 == 2",
                        "replace": "assert 1 == 1",
                    }
                ]
            }
        )

        # Process operations
        diff = self.engine.process_operations(operations_json)

        # Verify diff format
        self.assertIn("--- a/", diff)
        self.assertIn("+++ b/", diff)
        # Check for the actual diff content
        self.assertIn("assert 1 == 2", diff)
        self.assertIn("assert 1 == 1", diff)

        # Verify the change would actually work
        with open(self.test_file, "r") as f:
            current_content = f.read()

        # Apply the change manually to verify
        modified_content = current_content.replace("assert 1 == 2", "assert 1 == 1")

        # Should be different
        self.assertNotEqual(current_content, modified_content)
        # Should contain the fix
        self.assertIn("assert 1 == 1", modified_content)
        # Should not contain the old assertion
        self.assertNotIn("assert 1 == 2", modified_content)


if __name__ == "__main__":
    unittest.main()
