"""
Pipeline integration tests for all three LLM modes.
Tests the complete TestSentry workflow end-to-end.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sentries.chat import chat, has_api_key, is_simulation_mode

# from sentries.testsentry import main as testsentry_main  # Not used in current tests


class TestSimulationPipeline:
    """Test complete TestSentry pipeline in simulation mode."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def create_failing_test(self) -> None:
        """Create a failing test file."""
        test_content = '''
def test_failing_assertion():
    """This test will fail."""
    assert 1 == 2  # This will fail

def test_passing_assertion():
    """This test will pass."""
    assert 1 == 1  # This will pass
'''
        Path("test_example.py").write_text(test_content)

    def test_simulation_mode_pipeline(self) -> None:
        """Test complete pipeline in simulation mode."""
        # Set up simulation mode
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Verify simulation mode is active
            assert is_simulation_mode() is True

            # Create failing test
            self.create_failing_test()

            # Test chat functionality
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            response = chat("test-model", messages)

            # Verify simulation response
            assert "assert 1 == 1" in response
            assert "Fixed" in response
            print(f"✅ Simulation response: {response[:100]}...")

    def test_simulation_determinism_pipeline(self) -> None:
        """Test that simulation mode produces deterministic results."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

            # Run multiple times
            responses = []
            for i in range(3):
                response = chat("test-model", messages)
                responses.append(response)

            # All responses should be identical
            assert all(r == responses[0] for r in responses)
            print("✅ Simulation mode is deterministic across multiple runs")

    def test_simulation_different_prompts(self) -> None:
        """Test simulation mode with different prompt types."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Test planning prompt
            plan_messages = [{"role": "user", "content": "Create a plan for fixing this issue"}]
            plan_response = chat("test-model", plan_messages)
            assert "Plan" in plan_response

            # Test JSON prompt
            json_messages = [{"role": "user", "content": "Return JSON operations for fixing this"}]
            json_response = chat("test-model", json_messages)
            assert "operations" in json_response

            # Test general prompt
            general_messages = [{"role": "user", "content": "Help me with this problem"}]
            general_response = chat("test-model", general_messages)
            assert "I understand" in general_response

            print("✅ Simulation mode handles different prompt types correctly")


class TestAPIPipeline:
    """Test complete TestSentry pipeline in API mode."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_api_mode_detection(self) -> None:
        """Test API mode detection and priority."""
        # Test Groq API detection
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
            assert has_api_key() is True
            assert not is_simulation_mode()

        # Test OpenAI API detection
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            assert has_api_key() is True

        # Test Anthropic API detection
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            assert has_api_key() is True

        print("✅ API mode detection working for all providers")

    @patch("sentries.chat.chat_with_groq")
    def test_groq_pipeline(self, mock_groq: Any) -> None:
        """Test complete pipeline with Groq API."""
        mock_groq.return_value = "Fixed test: assert 1 == 1  # Changed from assert 1 == 2"

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            response = chat("llama3-8b-8192", messages)

            mock_groq.assert_called_once()
            assert "assert 1 == 1" in response
            print("✅ Groq API pipeline working correctly")

    @patch("sentries.chat.chat_with_openai")
    def test_openai_pipeline(self, mock_openai: Any) -> None:
        """Test complete pipeline with OpenAI API."""
        mock_openai.return_value = "Here's the fix: assert 1 == 1  # Fixed assertion"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            response = chat("gpt-4", messages)

            mock_openai.assert_called_once()
            assert "assert 1 == 1" in response
            print("✅ OpenAI API pipeline working correctly")

    @patch("sentries.chat.chat_with_anthropic")
    def test_anthropic_pipeline(self, mock_anthropic: Any) -> None:
        """Test complete pipeline with Anthropic API."""
        mock_anthropic.return_value = "The fix is: assert 1 == 1  # Corrected assertion"

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            response = chat("claude-3-sonnet", messages)

            mock_anthropic.assert_called_once()
            assert "assert 1 == 1" in response
            print("✅ Anthropic API pipeline working correctly")

    def test_api_fallback_chain(self) -> None:
        """Test API fallback chain works correctly."""
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "test-key",
                "OPENAI_API_KEY": "test-key",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=True,
        ):
            # Mock Groq to fail, should fallback to OpenAI
            with (
                patch("sentries.chat.chat_with_groq") as mock_groq,
                patch("sentries.chat.chat_with_openai") as mock_openai,
            ):

                mock_groq.side_effect = Exception("Groq failed")
                mock_openai.return_value = "OpenAI fallback response"

                messages = [{"role": "user", "content": "Hello"}]
                response = chat("llama3-8b-8192", messages)

                mock_groq.assert_called_once()
                mock_openai.assert_called_once()
                assert response == "OpenAI fallback response"
                print("✅ API fallback chain working correctly")


class TestLocalLLMPipeline:
    """Test complete TestSentry pipeline in local LLM mode."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    @patch("sentries.chat.chat_with_ollama")
    def test_local_llm_pipeline(self, mock_ollama: Any) -> None:
        """Test complete pipeline with local LLM."""
        mock_ollama.return_value = "Local LLM fix: assert 1 == 1  # Fixed locally"

        # Clear all environment variables to force local LLM mode
        with patch.dict(os.environ, {}, clear=True):
            assert not has_api_key()
            assert not is_simulation_mode()

            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            response = chat("llama3.1", messages)

            mock_ollama.assert_called_once()
            assert "assert 1 == 1" in response
            print("✅ Local LLM pipeline working correctly")

    @patch("sentries.chat.requests.post")
    def test_ollama_request_format(self, mock_post: Any) -> None:
        """Test that Ollama requests are formatted correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test response"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {}, clear=True):
            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Fix this test"},
            ]
            chat("llama3.1", messages)

            # Verify request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check URL
            assert "api/generate" in call_args[0][0]

            # Check payload structure
            payload = call_args[1]["json"]
            assert "model" in payload
            assert "prompt" in payload
            assert "options" in payload
            assert payload["stream"] is False

            print("✅ Ollama request format is correct")


class TestModePriority:
    """Test mode priority and switching."""

    def test_mode_priority_simulation_first(self) -> None:
        """Test that simulation mode has highest priority."""
        with patch.dict(
            os.environ,
            {
                "SENTRIES_SIMULATION_MODE": "true",
                "OPENAI_API_KEY": "test-key",
                "GROQ_API_KEY": "test-key",
            },
        ):
            # Should use simulation mode despite API keys being available
            assert is_simulation_mode() is True
            assert has_api_key() is True  # API keys are available but not used

            messages = [{"role": "user", "content": "Hello"}]
            response = chat("gpt-4", messages)

            # Should get simulation response
            assert "I understand" in response
            print("✅ Simulation mode has highest priority")

    def test_mode_priority_api_second(self) -> None:
        """Test that API mode has second priority."""
        with patch("sentries.chat.chat_with_openai") as mock_openai:
            mock_openai.return_value = "API response"

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
                assert not is_simulation_mode()
                assert has_api_key() is True

                messages = [{"role": "user", "content": "Hello"}]
                response = chat("gpt-4", messages)

                mock_openai.assert_called_once()
                assert response == "API response"
                print("✅ API mode has second priority")

    @patch("sentries.chat.chat_with_ollama")
    def test_mode_priority_local_last(self, mock_ollama: Any) -> None:
        """Test that local LLM mode has lowest priority."""
        mock_ollama.return_value = "Local response"

        with patch.dict(os.environ, {}, clear=True):
            assert not is_simulation_mode()
            assert not has_api_key()

            messages = [{"role": "user", "content": "Hello"}]
            response = chat("llama3.1", messages)

            mock_ollama.assert_called_once()
            assert response == "Local response"
            print("✅ Local LLM mode has lowest priority")


class TestErrorHandling:
    """Test error handling across all modes."""

    def test_simulation_error_recovery(self) -> None:
        """Test that simulation mode handles errors gracefully."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Test with empty messages
            response = chat("test-model", [])
            assert isinstance(response, str)
            assert len(response) > 0

            # Test with malformed messages
            response = chat("test-model", [{"invalid": "message"}])
            assert isinstance(response, str)
            assert len(response) > 0

            print("✅ Simulation mode error recovery working")

    def test_api_error_handling(self) -> None:
        """Test API error handling and fallback."""
        with patch("sentries.chat.chat_with_openai") as mock_openai:
            mock_openai.side_effect = Exception("API Error")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            with patch("sentries.chat.chat_with_openai") as mock_api:
                mock_api.side_effect = Exception("API Error")

                messages = [{"role": "user", "content": "Hello"}]

                with pytest.raises(ValueError, match="No valid API key found"):
                    chat("gpt-4", messages)

                print("✅ API error handling working correctly")

    @patch("sentries.chat.chat_with_ollama")
    def test_local_llm_error_handling(self, mock_ollama: Any) -> None:
        """Test local LLM error handling."""
        mock_ollama.side_effect = Exception("Ollama connection failed")

        with patch.dict(os.environ, {}, clear=True):
            messages = [{"role": "user", "content": "Hello"}]

            with pytest.raises(Exception, match="Ollama connection failed"):
                chat("llama3.1", messages)

            print("✅ Local LLM error handling working correctly")


class TestEnvironmentDetection:
    """Test environment detection and configuration."""

    def test_ci_environment_detection(self) -> None:
        """Test that CI environment automatically enables simulation mode."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert is_simulation_mode() is True
            print("✅ CI environment detection working")

    def test_github_actions_detection(self) -> None:
        """Test GitHub Actions environment detection."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            # Should not automatically enable simulation mode
            assert not is_simulation_mode()

            # But CI=true should
            with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true"}):
                assert is_simulation_mode() is True

            print("✅ GitHub Actions environment detection working")

    def test_environment_variable_precedence(self) -> None:
        """Test environment variable precedence."""
        # Explicit simulation mode should override CI
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "false", "CI": "true"}):
            # CI=true should still enable simulation mode
            assert is_simulation_mode() is True

        # Explicit true should work
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            assert is_simulation_mode() is True

        print("✅ Environment variable precedence working correctly")


class TestPerformance:
    """Test performance characteristics of different modes."""

    def test_simulation_mode_performance(self) -> None:
        """Test that simulation mode is fast."""
        import time

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

            start_time = time.time()
            for _ in range(10):
                chat("test-model", messages)
            end_time = time.time()

            avg_time = (end_time - start_time) / 10
            assert avg_time < 0.1  # Should be very fast
            print(f"✅ Simulation mode average response time: {avg_time:.4f}s")

    def test_mode_switching_performance(self) -> None:
        """Test that mode switching doesn't cause performance issues."""
        import time

        messages = [{"role": "user", "content": "Hello"}]

        # Test switching between modes
        start_time = time.time()

        # Simulation mode
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            chat("test-model", messages)

        # API mode (mocked)
        with patch("sentries.chat.chat_with_openai") as mock_openai:
            mock_openai.return_value = "API response"
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
                chat("gpt-4", messages)

        # Local LLM mode (mocked)
        with patch("sentries.chat.chat_with_ollama") as mock_ollama:
            mock_ollama.return_value = "Local response"
            with patch.dict(os.environ, {}, clear=True):
                chat("llama3.1", messages)

        end_time = time.time()
        total_time = end_time - start_time

        assert total_time < 1.0  # Should be fast
        print(f"✅ Mode switching total time: {total_time:.4f}s")
