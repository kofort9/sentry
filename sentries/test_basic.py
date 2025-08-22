"""
Basic tests for sentries package to verify testing infrastructure
"""

from pathlib import Path

import pytest


def test_banner_import() -> None:
    """Test that banner module can be imported"""
    from sentries import banner

    assert hasattr(banner, "show_sentry_banner")


def test_runner_common_import() -> None:
    """Test that runner_common module can be imported"""
    from sentries import runner_common

    assert hasattr(runner_common, "TESTS_ALLOWLIST")
    assert hasattr(runner_common, "DOCS_ALLOWLIST")


def test_allowlists_are_lists() -> None:
    """Test that allowlists are properly configured as lists"""
    from sentries.runner_common import DOCS_ALLOWLIST, TESTS_ALLOWLIST

    assert isinstance(TESTS_ALLOWLIST, list), "TESTS_ALLOWLIST should be a list"
    assert isinstance(DOCS_ALLOWLIST, list), "DOCS_ALLOWLIST should be a list"

    # Test that they contain expected paths
    assert any(
        "tests" in str(path) for path in TESTS_ALLOWLIST
    ), "TESTS_ALLOWLIST should contain tests path"
    assert any(
        "README.md" in str(path) for path in DOCS_ALLOWLIST
    ), "DOCS_ALLOWLIST should contain README.md"


def test_package_structure() -> None:
    """Test that all core modules exist"""
    core_modules = [
        "banner",
        "chat",
        "prompts",
        "diff_utils",
        "git_utils",
        "runner_common",
        "testsentry",
        "docsentry",
    ]

    for module_name in core_modules:
        try:
            __import__(f"sentries.{module_name}")
        except ImportError as e:
            pytest.fail(f"Failed to import sentries.{module_name}: {e}")


def test_cli_scripts_exist() -> None:
    """Test that core CLI script files exist"""
    script_dir = Path(__file__).parent

    core_scripts = ["testsentry.py", "docsentry.py"]

    for script in core_scripts:
        script_path = script_dir / script
        assert script_path.exists(), f"CLI script {script} not found"
        assert script_path.stat().st_size > 0, f"CLI script {script} is empty"


def test_version_consistency() -> None:
    """Test that version is consistent across package"""
    import toml

    from sentries import __version__

    # Read version from pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    pyproject_data = toml.load(pyproject_path)
    pyproject_version = pyproject_data["project"]["version"]

    assert (
        __version__ == pyproject_version
    ), f"Version mismatch: {__version__} != {pyproject_version}"


def test_intentional_failure() -> None:
    """Intentionally failing test to trigger TestSentry"""
    # This test should fail to trigger TestSentry in CI
    assert 1 == 2, "This test is intentionally failing to test TestSentry automation"


def test_another_intentional_failure() -> None:
    """Another intentionally failing test"""
    # Multiple failures to give TestSentry more context
    result = 5 + 5
    assert result == 11, f"Expected 11 but got {result} - this should trigger TestSentry"


if __name__ == "__main__":
    pytest.main([__file__])
