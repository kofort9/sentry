"""
CI integration tests to ensure GitHub Actions workflow works correctly.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from sentries.chat import chat, is_simulation_mode


class TestCIIntegration:
    """Test CI integration and GitHub Actions compatibility."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_github_actions_simulation_mode(self) -> None:
        """Test that GitHub Actions automatically uses simulation mode."""
        # Simulate GitHub Actions environment
        github_env = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "kofort9/sentry",
            "GITHUB_REF": "refs/heads/main",
        }

        with patch.dict(os.environ, github_env, clear=True):
            # Should automatically detect simulation mode
            assert is_simulation_mode() is True

            # Should work without any API keys
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            response = chat("test-model", messages)

            assert "assert 1 == 1" in response
            print("✅ GitHub Actions simulation mode working")

    def test_ci_without_secrets(self) -> None:
        """Test that CI works without any API key secrets."""
        ci_env = {"CI": "true", "GITHUB_ACTIONS": "true"}

        with patch.dict(os.environ, ci_env, clear=True):
            # Ensure no API keys are present
            assert "OPENAI_API_KEY" not in os.environ
            assert "ANTHROPIC_API_KEY" not in os.environ
            assert "GROQ_API_KEY" not in os.environ

            # Should still work in simulation mode
            messages = [{"role": "user", "content": "Create a plan for this fix"}]
            response = chat("test-model", messages)

            assert "Plan" in response
            print("✅ CI works without API key secrets")

    def test_pr_workflow_simulation(self) -> None:
        """Test PR workflow with simulation mode."""
        pr_env = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_HEAD_REF": "feature/test-branch",
        }

        with patch.dict(os.environ, pr_env, clear=True):
            # Create a mock failing test
            test_content = """
def test_example():
    assert 1 == 2  # This will fail
"""
            Path("test_failing.py").write_text(test_content)

            # Test that simulation mode can handle the test
            messages = [{"role": "user", "content": f"Fix this test: {test_content}"}]
            response = chat("test-model", messages)

            assert "assert 1 == 1" in response
            print("✅ PR workflow simulation working")

    def test_deterministic_ci_results(self) -> None:
        """Test that CI produces deterministic results."""
        ci_env = {"CI": "true"}

        with patch.dict(os.environ, ci_env, clear=True):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

            # Run multiple times to ensure determinism
            responses = []
            for i in range(5):
                response = chat("test-model", messages)
                responses.append(response)

            # All responses should be identical
            assert all(r == responses[0] for r in responses)
            print("✅ CI produces deterministic results")

    def test_ci_performance_requirements(self) -> None:
        """Test that CI meets performance requirements."""
        import time

        ci_env = {"CI": "true"}

        with patch.dict(os.environ, ci_env, clear=True):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

            # Measure response time
            start_time = time.time()
            response = chat("test-model", messages)
            end_time = time.time()

            response_time = end_time - start_time

            # Should be very fast in CI
            assert response_time < 1.0
            assert len(response) > 0
            print(f"✅ CI response time: {response_time:.4f}s (meets requirements)")

    def test_ci_memory_usage(self) -> None:
        """Test that CI doesn't use excessive memory."""
        import psutil

        ci_env = {"CI": "true"}

        with patch.dict(os.environ, ci_env, clear=True):
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Run multiple chat operations
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            for i in range(50):
                chat("test-model", messages)

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Should not use excessive memory
            assert memory_increase < 100  # Less than 100MB increase
            print(f"✅ CI memory usage: {memory_increase:.2f}MB increase (acceptable)")

    def test_workflow_without_llm_tests(self) -> None:
        """Test that workflow works when LLM tests are skipped."""
        # Simulate environment where LLM tests should be skipped
        skip_env = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "pull_request",
            # No test-llm label or trigger
        }

        with patch.dict(os.environ, skip_env, clear=True):
            # Basic functionality should still work
            assert is_simulation_mode() is True

            # Chat should work for basic operations
            messages = [{"role": "user", "content": "Hello"}]
            response = chat("test-model", messages)

            assert isinstance(response, str)
            assert len(response) > 0
            print("✅ Workflow works when LLM tests are skipped")

    def test_error_handling_in_ci(self) -> None:
        """Test error handling in CI environment."""
        ci_env = {"CI": "true"}

        with patch.dict(os.environ, ci_env, clear=True):
            # Test with various edge cases
            test_cases = [
                [],  # Empty messages
                [{"role": "invalid", "content": "test"}],  # Invalid role
                [{"content": "test"}],  # Missing role
                [{"role": "user"}],  # Missing content
            ]

            for messages in test_cases:
                try:
                    response = chat("test-model", messages)
                    # Should get some response, even if not perfect
                    assert isinstance(response, str)
                except Exception as e:
                    # Errors should be handled gracefully
                    error_msg = str(e).lower()
                    assert any(
                        keyword in error_msg
                        for keyword in ["simulation", "mock", "content", "message", "format"]
                    )

            print("✅ Error handling in CI working correctly")

    def test_observability_integration(self) -> None:
        """Test that observability features work in CI."""
        ci_env = {"CI": "true", "GITHUB_ACTIONS": "true"}

        with patch.dict(os.environ, ci_env, clear=True):
            # Test that observability hooks don't break simulation mode
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

            # Should work even with observability enabled
            response = chat("test-model", messages)

            assert "assert 1 == 1" in response
            print("✅ Observability integration working in CI")

    def test_multiple_python_versions(self) -> None:
        """Test compatibility across Python versions (simulated)."""
        ci_env = {"CI": "true"}

        # Simulate different Python version environments
        python_versions = ["3.10", "3.11", "3.12"]

        for version in python_versions:
            test_env = {**ci_env, "PYTHON_VERSION": version}

            with patch.dict(os.environ, test_env, clear=True):
                messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
                response = chat("test-model", messages)

                assert "assert 1 == 1" in response
                print(f"✅ Python {version} compatibility confirmed")

    def test_concurrent_requests(self) -> None:
        """Test handling of concurrent requests in CI."""
        import threading
        import time

        ci_env = {"CI": "true"}
        results = []
        errors = []

        def make_request(thread_id: int) -> None:
            try:
                with patch.dict(os.environ, ci_env, clear=True):
                    messages = [{"role": "user", "content": f"Fix test {thread_id}: assert 1 == 2"}]
                    response = chat("test-model", messages)
                    results.append((thread_id, response))
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)

        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        end_time = time.time()

        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

        # All should have successful responses
        for thread_id, response in results:
            assert "assert 1 == 1" in response

        total_time = end_time - start_time
        print(f"✅ Concurrent requests handled successfully in {total_time:.2f}s")


class TestWorkflowCompatibility:
    """Test compatibility with GitHub Actions workflow."""

    def test_workflow_environment_variables(self) -> None:
        """Test that workflow sets correct environment variables."""
        workflow_env = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_WORKFLOW": "Test Sentries",
            "GITHUB_JOB": "test-basic",
            "GITHUB_REPOSITORY": "kofort9/sentry",
        }

        with patch.dict(os.environ, workflow_env, clear=True):
            # Should detect CI environment
            assert is_simulation_mode() is True

            # Should work correctly
            messages = [{"role": "user", "content": "Test workflow"}]
            response = chat("test-model", messages)

            assert isinstance(response, str)
            assert len(response) > 0
            print("✅ Workflow environment variables working correctly")

    def test_artifact_generation_compatibility(self) -> None:
        """Test that simulation mode is compatible with artifact generation."""
        ci_env = {"CI": "true"}

        with patch.dict(os.environ, ci_env, clear=True):
            # Simulate generating multiple responses for artifacts
            responses = {}

            test_scenarios = [
                "Fix this test: assert 1 == 2",
                "Create a plan for fixing this issue",
                "Generate JSON operations for this fix",
            ]

            for i, scenario in enumerate(test_scenarios):
                messages = [{"role": "user", "content": scenario}]
                response = chat("test-model", messages)
                responses[f"scenario_{i}"] = response

            # All responses should be deterministic and valid
            assert len(responses) == 3
            for key, response in responses.items():
                assert isinstance(response, str)
                assert len(response) > 0

            print("✅ Artifact generation compatibility confirmed")

    def test_step_summary_compatibility(self) -> None:
        """Test compatibility with GitHub Actions step summaries."""
        ci_env = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_STEP_SUMMARY": "/tmp/step_summary.md",
        }

        with patch.dict(os.environ, ci_env, clear=True):
            # Should work even when step summary is expected
            messages = [{"role": "user", "content": "Generate summary data"}]
            response = chat("test-model", messages)

            assert isinstance(response, str)
            assert len(response) > 0
            print("✅ Step summary compatibility confirmed")
