"""
Basic tests for sentries package to verify testing infrastructure
"""

import pytest
from pathlib import Path


def test_banner_import():
    """Test that banner module can be imported"""
    from sentries import banner
    assert hasattr(banner, 'show_sentry_banner')


def test_runner_common_import():
    """Test that runner_common module can be imported"""
    from sentries import runner_common
    assert hasattr(runner_common, 'TESTS_ALLOWLIST')
    assert hasattr(runner_common, 'DOCS_ALLOWLIST')


def test_allowlists_are_lists():
    """Test that allowlists are properly configured as lists"""
    from sentries.runner_common import TESTS_ALLOWLIST, DOCS_ALLOWLIST

    assert isinstance(TESTS_ALLOWLIST, list), "TESTS_ALLOWLIST should be a list"
    assert isinstance(DOCS_ALLOWLIST, list), "DOCS_ALLOWLIST should be a list"

    # Test that they contain expected paths
    assert any("tests" in str(path)
               for path in TESTS_ALLOWLIST), "TESTS_ALLOWLIST should contain tests path"
    assert any("README.md" in str(path)
               for path in DOCS_ALLOWLIST), "DOCS_ALLOWLIST should contain README.md"


def test_package_structure():
    """Test that all core modules exist"""
    core_modules = [
        'banner', 'chat', 'prompts', 'diff_utils', 'git_utils', 'runner_common',
        'testsentry', 'docsentry'
    ]

    for module_name in core_modules:
        try:
            __import__(f'sentries.{module_name}')
        except ImportError as e:
            pytest.fail(f"Failed to import sentries.{module_name}: {e}")


def test_cli_scripts_exist():
    """Test that core CLI script files exist"""
    script_dir = Path(__file__).parent

    core_scripts = [
        'testsentry.py', 'docsentry.py'
    ]

    for script in core_scripts:
        script_path = script_dir / script
        assert script_path.exists(), f"CLI script {script} not found"
        assert script_path.stat().st_size > 0, f"CLI script {script} is empty"


def test_version_consistency():
    """Test that version is consistent across package"""
    from sentries import __version__
    import toml

    # Read version from pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    pyproject_data = toml.load(pyproject_path)
    pyproject_version = pyproject_data['project']['version']

    assert __version__ == pyproject_version, (
        f"Version mismatch: {__version__} != {pyproject_version}"
    )


if __name__ == "__main__":
    pytest.main([__file__])
