"""
Test all three chat modes: simulation, API, and local LLM.
"""

import os
from typing import Any
from unittest.mock import patch

import pytest

from sentries.chat import chat, has_api_key, is_simulation_mode


class TestSimulationMode:
    """Test simulation mode functionality."""

    def test_simulation_mode_detection(self) -> None:
        """Test that simulation mode is detected correctly."""
        # Test environment variable
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            assert is_simulation_mode() is True

        # Test CI environment
        with patch.dict(os.environ, {"CI": "true"}):
            assert is_simulation_mode() is True

        # Test default
        with patch.dict(os.environ, {}, clear=True):
            assert is_simulation_mode() is False

    def test_simulation_chat(self) -> None:
        """Test that simulation mode returns deterministic responses."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
            response = chat("test-model", messages)

            assert "assert 1 == 1" in response
            assert "Fixed" in response
            assert "test" in response.lower()

    def test_simulation_deterministic(self) -> None:
        """Test that simulation mode is deterministic."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

            response1 = chat("test-model", messages)
            response2 = chat("test-model", messages)

            assert response1 == response2  # Should be identical


class TestAPIMode:
    """Test API mode functionality."""

    def test_api_key_detection(self) -> None:
        """Test that API keys are detected correctly."""
        # Test OpenAI key
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            assert has_api_key() is True

        # Test Anthropic key
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            assert has_api_key() is True

        # Test Groq key
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            assert has_api_key() is True

        # Test no keys
        with patch.dict(os.environ, {}, clear=True):
            assert has_api_key() is False

    @patch("sentries.chat.chat_with_groq")
    def test_groq_api_call(self, mock_groq: Any) -> None:
        """Test Groq API integration."""
        mock_groq.return_value = "Mock Groq response"

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            messages = [{"role": "user", "content": "Hello"}]
            response = chat("llama3-8b-8192", messages)

            mock_groq.assert_called_once()
            assert response == "Mock Groq response"

    @patch("sentries.chat.chat_with_openai")
    def test_openai_api_call(self, mock_openai: Any) -> None:
        """Test OpenAI API integration."""
        mock_openai.return_value = "Mock OpenAI response"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            messages = [{"role": "user", "content": "Hello"}]
            response = chat("gpt-4", messages)

            mock_openai.assert_called_once()
            assert response == "Mock OpenAI response"

    @patch("sentries.chat.chat_with_anthropic")
    def test_anthropic_api_call(self, mock_anthropic: Any) -> None:
        """Test Anthropic API integration."""
        mock_anthropic.return_value = "Mock Anthropic response"

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            messages = [{"role": "user", "content": "Hello"}]
            response = chat("claude-3-sonnet", messages)

            mock_anthropic.assert_called_once()
            assert response == "Mock Anthropic response"


class TestLocalLLMMode:
    """Test local LLM mode functionality."""

    @patch("sentries.chat.chat_with_ollama")
    def test_local_llm_fallback(self, mock_ollama: Any) -> None:
        """Test that local LLM is used when no API keys are available."""
        mock_ollama.return_value = "Mock Ollama response"

        with patch.dict(os.environ, {}, clear=True):
            messages = [{"role": "user", "content": "Hello"}]
            response = chat("llama3.1", messages)

            mock_ollama.assert_called_once()
            assert response == "Mock Ollama response"


class TestModePriority:
    """Test that modes are selected in the correct priority order."""

    def test_simulation_overrides_api(self) -> None:
        """Test that simulation mode overrides API mode."""
        with patch.dict(
            os.environ, {"SENTRIES_SIMULATION_MODE": "true", "OPENAI_API_KEY": "test-key"}
        ):
            messages = [{"role": "user", "content": "Hello"}]
            response = chat("gpt-4", messages)

            # Should get simulation response, not API response
            assert "I understand" in response
            assert isinstance(response, str)
            assert len(response) > 0

    def test_api_overrides_local(self) -> None:
        """Test that API mode overrides local LLM mode."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("sentries.chat.chat_with_openai") as mock_api:
                mock_api.return_value = "API response"

                messages = [{"role": "user", "content": "Hello"}]
                response = chat("gpt-4", messages)

                mock_api.assert_called_once()
                assert response == "API response"


class TestErrorHandling:
    """Test error handling in different modes."""

    def test_simulation_mode_error_handling(self) -> None:
        """Test that simulation mode handles errors gracefully."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Test with empty messages
            response = chat("test-model", [])
            assert isinstance(response, str)
            assert len(response) > 0

    def test_api_mode_error_handling(self) -> None:
        """Test that API mode handles errors gracefully."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            with patch("sentries.chat.chat_with_openai") as mock_api:
                mock_api.side_effect = Exception("API Error")

                # Should exhaust all fallbacks and raise "No valid API key found"
                with pytest.raises(ValueError, match="No valid API key found"):
                    chat("gpt-4", [{"role": "user", "content": "Hello"}])

    def test_local_llm_mode_error_handling(self) -> None:
        """Test that local LLM mode handles errors gracefully."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sentries.chat.chat_with_ollama") as mock_ollama:
                mock_ollama.side_effect = Exception("Ollama Error")

                with pytest.raises(Exception, match="Ollama Error"):
                    chat("llama3.1", [{"role": "user", "content": "Hello"}])


class TestIntegration:
    """Test integration between different modes."""

    def test_mode_switching(self) -> None:
        """Test that modes can be switched dynamically."""
        # Start with simulation
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Hello"}]
            response1 = chat("test-model", messages)
            assert "I understand" in response1

        # Switch to API mode
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("sentries.chat.chat_with_openai") as mock_api:
                mock_api.return_value = "API response"
                response2 = chat("gpt-4", messages)
                assert response2 == "API response"

        # Switch to local LLM mode
        with patch.dict(os.environ, {}, clear=True):
            with patch("sentries.chat.chat_with_ollama") as mock_ollama:
                mock_ollama.return_value = "Ollama response"
                response3 = chat("llama3.1", messages)
                assert response3 == "Ollama response"
