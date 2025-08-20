#!/usr/bin/env python3
"""
End-to-End Testing Script for Sentries

This script creates a comprehensive test environment to verify that
all Sentries components work together correctly.
"""
import re

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Try to import sentries, add parent directory to path if needed
try:
    from sentries.banner import show_sentry_banner
    from sentries.runner_common import TESTS_ALLOWLIST, DOCS_ALLOWLIST
except ImportError:
    # Add the parent directory to the path so we can import sentries
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from sentries.banner import show_sentry_banner
    from sentries.runner_common import TESTS_ALLOWLIST, DOCS_ALLOWLIST


class E2ETestRunner:
    """Comprehensive end-to-end testing for sentries"""

    def __init__(self):
        """Initialize the E2E test runner."""
        self.test_dir = None
        self.test_repo = None
        self.results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "total_tests": 0,
            "details": []
        }

    def setup_test_environment(self):
        """Create a temporary test repository with various scenarios"""
        print("🔧 Setting up test environment...")

        # Create temporary directory
        self.test_dir = tempfile.mkdtemp(prefix="sentries-e2e-")
        self.test_repo = Path(self.test_dir) / "test-repo"
        self.test_repo.mkdir()

        # Create repository structure
        self._create_repository_structure()
        self._initialize_git_repository()

        print(f"✅ Test environment created at: {self.test_dir}")

    def _create_repository_structure(self):
        """Create a realistic repository structure for testing"""
        # Create directories
        (self.test_repo / "tests").mkdir()
        (self.test_repo / "docs").mkdir()
        (self.test_repo / "src").mkdir()

        # Create a failing test
        test_content = '''import pytest

def test_failing_function():
    """This test will fail and should be fixed by TestSentry"""
    assert 1 == 2, "This assertion will fail"

def test_passing_function():
    """This test should pass"""
    assert 1 == 1, "This assertion should pass"

def test_another_failing_test():
    """Another failing test for variety"""
    result = 2 + 2
    assert result == 5, f"Expected 5, got {result}"
'''
        (self.test_repo / "tests" / "test_example.py").write_text(test_content)

        # Create source code
        src_content = '''def example_function():
    """Example function that should work correctly"""
    return "Hello, World!"

def another_function():
    """Another function for testing"""
    return 42
'''
        (self.test_repo / "src" / "example.py").write_text(src_content)

        # Create documentation
        docs_content = '''# Test Documentation

This is test documentation that should be updated by DocSentry.

## Features

- Feature 1
- Feature 2
- Feature 3

## Usage

```python
from src.example import example_function
result = example_function()
```
'''
        (self.test_repo / "docs" / "README.md").write_text(docs_content)

        # Create main README
        main_readme = '''# Test Repository

This is a test repository for testing Sentries functionality.

## Installation

```bash
pip install -e .
```

## Testing

```bash
pytest tests/
```

## Documentation

See the `docs/` directory for detailed documentation.
'''
        (self.test_repo / "README.md").write_text(main_readme)

        # Create pyproject.toml
        pyproject_content = '''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-repo"
version = "0.1.0"
description = "Test repository for Sentries"
requires-python = ">=3.8"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
'''
        (self.test_repo / "pyproject.toml").write_text(pyproject_content)

    def _initialize_git_repository(self):
        """Initialize git repository and create initial commit"""
        os.chdir(self.test_repo)

        # Initialize git
        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True, capture_output=True)

        # Add all files
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], check=True, capture_output=True)

        # Create a feature branch
        subprocess.run(["git", "checkout", "-b", "feature/test-sentries"], check=True, capture_output=True)

        # Make some changes to trigger doc updates
        readme_content = '''# Test Repository

This is a test repository for testing Sentries functionality.

## Installation

```bash
pip install -e .
```

## Testing

```bash
pytest tests/
```

## Documentation

See the `docs/` directory for detailed documentation.

## New Feature

This is a new feature that was added recently.
'''
        (self.test_repo / "README.md").write_text(readme_content)

        subprocess.run(["git", "add", "README.md"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add new feature"], check=True, capture_output=True)

        print("✅ Git repository initialized with test data")

    def test_import_functionality(self):
        """Test that all sentries modules can be imported"""
        print("🧪 Testing import functionality...")

        try:
            # Test core imports
            from sentries import banner, chat, prompts
            print("✅ All core modules imported successfully")

            # Test specific functionality
            assert hasattr(banner, 'show_sentry_banner'), "banner module missing show_sentry_banner"
            assert hasattr(chat, 'chat'), "chat module missing chat function"
            assert hasattr(prompts, 'PLANNER_TESTS'), "prompts module missing PLANNER_TESTS"
            assert hasattr(prompts, 'PATCHER_TESTS'), "prompts module missing PATCHER_TESTS"

            self._record_test_result("Import functionality", True, "All modules imported successfully")

        except ImportError as e:
            self._record_test_result("Import functionality", False, f"Import failed: {e}")
            raise

    def test_allowlist_validation(self):
        """Test that allowlists are properly configured"""
        print("🧪 Testing allowlist validation...")

        try:
            # Test test allowlist
            assert "tests/" in TESTS_ALLOWLIST, "tests/ not in TESTS_ALLOWLIST"
            assert "tests/" in [str(p) for p in TESTS_ALLOWLIST], "tests/ path not properly configured"

            # Test docs allowlist
            assert "README.md" in [str(p) for p in DOCS_ALLOWLIST], "README.md not in DOCS_ALLOWLIST"
            assert "docs/" in [str(p) for p in DOCS_ALLOWLIST], "docs/ not in DOCS_ALLOWLIST"

            print("✅ Allowlists properly configured")
            self._record_test_result("Allowlist validation", True, "All allowlists properly configured")

        except AssertionError as e:
            self._record_test_result("Allowlist validation", False, f"Allowlist validation failed: {e}")
            raise

    def test_cli_commands(self):
        """Test that all CLI commands are available"""
        print("🧪 Testing CLI command availability...")

        try:
            # Test CLI commands
            cli_commands = [
                "testsentry", "docsentry", "sentries-cleanup",
                "sentries-status", "sentries-setup", "sentries-update-models"
            ]

            # Set required environment variables for testing
            test_env = os.environ.copy()
            test_env.update({
                'GITHUB_TOKEN': 'test-token',
                'GITHUB_REPOSITORY': 'test-org/test-repo',
                'LLM_BASE': 'http://127.0.0.1:11434',
                'MODEL_PLAN': 'llama3.1:8b-instruct-q4_K_M',
                'MODEL_PATCH': 'deepseek-coder:6.7b-instruct-q5_K_M'
            })

            for cmd in cli_commands:
                # Run from the test repository directory
                os.chdir(self.test_repo)
                result = subprocess.run([cmd, "--help"], capture_output=True, text=True, env=test_env)
                if result.returncode == 0:
                    print(f"✅ {cmd} command available")
                else:
                    # Some commands might fail due to missing environment, but we can still verify they exist
                    if "GITHUB_TOKEN environment variable is required" in result.stderr:
                        print(f"✅ {cmd} command available (requires proper environment)")
                    else:
                        raise RuntimeError(f"{cmd} command failed: {result.stderr}")

            print("✅ All CLI commands available")
            self._record_test_result("CLI commands", True, "All CLI commands available")

        except Exception as e:
            self._record_test_result("CLI commands", False, f"CLI command test failed: {e}")
            raise

    def test_repository_structure(self):
        """Test that the test repository structure is correct"""
        print("🧪 Testing repository structure...")

        try:
            # Check that all expected files exist
            expected_files = [
                "tests/test_example.py",
                "src/example.py",
                "docs/README.md",
                "README.md",
                "pyproject.toml"
            ]

            for file_path in expected_files:
                full_path = self.test_repo / file_path
                assert full_path.exists(), f"Expected file {file_path} not found"
                assert full_path.stat().st_size > 0, f"File {file_path} is empty"

            # Check git status
            os.chdir(self.test_repo)
            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
            assert result.returncode == 0, "Git status command failed"

            print("✅ Repository structure is correct")
            self._record_test_result("Repository structure", True, "Repository structure is correct")

        except Exception as e:
            self._record_test_result("Repository structure", False, f"Repository structure test failed: {e}")
            raise

    def test_failing_tests(self):
        """Test that the failing tests actually fail"""
        print("🧪 Testing that tests actually fail...")

        try:
            os.chdir(self.test_repo)

            # Run pytest and expect it to fail
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-v"],
                capture_output=True,
                text=True
            )

            # pytest should fail with failing tests
            assert result.returncode != 0, "Expected pytest to fail with failing tests"

            # Check that we have the expected failing tests
            output = result.stdout + result.stderr
            assert "test_failing_function" in output, "test_failing_function not found in output"
            assert "test_another_failing_test" in output, "test_another_failing_test not found in output"

            print("✅ Failing tests are properly configured")
            self._record_test_result("Failing tests", True, "Failing tests are properly configured")

        except Exception as e:
            self._record_test_result("Failing tests", False, f"Failing tests test failed: {e}")
            raise

    def _record_test_result(self, test_name: str, passed: bool, details: str):
        """Record the result of a test"""
        self.results["total_tests"] += 1
        if passed:
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1

        self.results["details"].append({
            "test": test_name,
            "passed": passed,
            "details": details
        })

    def run_all_tests(self):
        """Run all end-to-end tests"""
        show_sentry_banner()
        print("🚀 Starting End-to-End Testing for Sentries")
        print("=" * 60)

        try:
            # Setup
            self.setup_test_environment()

            # Run tests
            self.test_import_functionality()
            self.test_allowlist_validation()
            self.test_cli_commands()
            self.test_repository_structure()
            self.test_failing_tests()

            # Summary
            self._print_summary()

        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            self._print_summary()
            raise

        finally:
            self.cleanup()

    def _print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)

        print(f"Total Tests: {self.results['total_tests']}")
        print(f"Passed: {self.results['tests_passed']} ✅")
        print(f"Failed: {self.results['tests_failed']} ❌")

        if self.results['tests_failed'] > 0:
            print("\nFailed Tests:")
            for test in self.results['details']:
                if not test['passed']:
                    print(f"  ❌ {test['test']}: {test['details']}")

        if self.results['total_tests'] > 0:
            print(f"\nSuccess Rate: {(self.results['tests_passed'] / self.results['total_tests'] * 100):.1f}%")
        else:
            print("\nSuccess Rate: N/A (no tests run)")

        if self.results['tests_failed'] == 0:
            print("\n🎉 All tests passed! Sentries are ready for deployment.")
        else:
            print(f"\n⚠️  {self.results['tests_failed']} test(s) failed. Please fix before deployment.")

    def cleanup(self):
        """Clean up test environment"""
        if self.test_dir and os.path.exists(self.test_dir):
            print(f"🧹 Cleaning up test environment: {self.test_dir}")
            shutil.rmtree(self.test_dir)
            print("✅ Test environment cleaned up")


def main():
    """Main entry point"""
    runner = E2ETestRunner()
    runner.run_all_tests()


if __name__ == "__main__":
    main()
