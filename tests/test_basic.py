#!/usr/bin/env python3
"""
Basic tests for the sentries package.
"""

from pathlib import Path


def test_banner_import() -> None:
    """Test that the banner module can be imported."""
    import sentries.banner

    assert sentries.banner is not None


def test_runner_common_import() -> None:
    """Test that the runner_common module can be imported."""
    import sentries.runner_common

    assert sentries.runner_common is not None


def test_allowlists_are_lists() -> None:
    """Test that allowlists are properly defined as lists."""
    import sentries.runner_common as rc

    # Check that allowlists exist and are lists
    assert hasattr(rc, "TESTS_ALLOWLIST")
    assert isinstance(rc.TESTS_ALLOWLIST, list)

    # Check that allowlists contain expected patterns
    assert "tests/" in rc.TESTS_ALLOWLIST
    # Only tests/ directory is allowed
    assert len(rc.TESTS_ALLOWLIST) == 1


def test_cli_scripts_exist() -> None:
    """Test that CLI scripts exist and are executable."""
    # Check for the main CLI scripts
    scripts = ["testsentry.py", "docsentry.py"]

    for script in scripts:
        script_path = Path("sentries") / script
        assert script_path.exists(), f"Script {script} not found"
        assert script_path.is_file(), f"Script {script} is not a file"


def test_version_consistency() -> None:
    """Test that version information is consistent across the package."""
    import sentries

    # Check that __version__ exists
    assert hasattr(sentries, "__version__")
    assert isinstance(sentries.__version__, str)
    assert len(sentries.__version__) > 0


def test_intentional_failure() -> None:
    """This test intentionally fails to trigger TestSentry."""
    # This should trigger TestSentry to fix it
    assert 1 == 2, "This assertion should fail to trigger TestSentry"


def test_another_intentional_failure() -> None:
    """Another intentionally failing test to trigger TestSentry."""
    # This should also trigger TestSentry
    assert False, "This should always fail to trigger TestSentry"


def test_patch_engine_import() -> None:
    """Test that the new patch engine can be imported."""
    import sentries.patch_engine

    assert sentries.patch_engine is not None

    # Test that key classes exist
    from sentries.patch_engine import PatchEngine, PatchOperation

    assert PatchEngine is not None
    assert PatchOperation is not None


def test_patch_engine_creation() -> None:
    """Test that patch engine can be created."""
    from sentries.patch_engine import create_patch_engine

    engine = create_patch_engine()
    assert engine is not None
    assert hasattr(engine, "process_operations")
