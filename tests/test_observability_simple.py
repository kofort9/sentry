"""
Simple test for observability integration with the three-mode LLM system.
Tests the integration without requiring complex observability dependencies.
"""

import os
from unittest.mock import MagicMock, patch

# import pytest  # Not used in current tests

from sentries.chat import chat


class TestObservabilitySimple:
    """Test basic observability integration."""

    def test_observability_import_handling(self) -> None:
        """Test that chat works with and without observability imports."""

        # Test 1: With observability available (mocked)
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    messages = [{"role": "user", "content": "Hello"}]
                    chat("test-model", messages)

                    assert isinstance(response, str)
                    assert len(response) > 0
                    mock_log.assert_called_once()
                    mock_analyze.assert_called_once()

                    # Check that mode metadata was passed
                    call_kwargs = mock_log.call_args[1]
                    metadata = call_kwargs["metadata"]
                    assert metadata["mode"] == "simulation"

                    print("✅ Observability integration working with mocked imports")

        # Test 2: Without observability (import error)
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Mock the import to fail
            original_import = __builtins__["__import__"]

            def mock_import(name, *args, **kwargs):
                if name.startswith("packages.metrics_core.observability"):
                    raise ImportError("No observability module")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                messages = [{"role": "user", "content": "Hello"}]
                chat("test-model", messages)

                assert isinstance(response, str)
                assert len(response) > 0
                print("✅ Chat works without observability imports")

    def test_mode_metadata_integration(self) -> None:
        """Test that mode information is correctly passed to observability."""

        test_cases = [
            ("simulation", {"SENTRIES_SIMULATION_MODE": "true"}),
            ("api", {"GROQ_API_KEY": "test-key"}),
            ("local", {}),
        ]

        for expected_mode, env_vars in test_cases:
            with patch.dict(os.environ, env_vars, clear=True):
                mock_log = MagicMock()
                mock_analyze = MagicMock(return_value={"pii_spans": []})

                # Mock the appropriate chat function
                if expected_mode == "api":
                    mock_target = "sentries.chat.chat_with_groq"
                elif expected_mode == "local":
                    mock_target = "sentries.chat.chat_with_ollama"
                else:
                    mock_target = None

                mock_context = (
                    patch(mock_target, return_value="Test response") if mock_target else MagicMock()
                )

                with mock_context:
                    with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                        with patch(
                            "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                        ):
                            messages = [{"role": "user", "content": "Hello"}]
                            chat("test-model", messages)

                            # Verify observability was called with correct mode
                            mock_log.assert_called_once()
                            call_kwargs = mock_log.call_args[1]
                            metadata = call_kwargs["metadata"]

                            assert metadata["mode"] == expected_mode
                            assert metadata[f"is_{expected_mode}"] is True

                            # Verify other modes are False
                            other_modes = [
                                m for m in ["simulation", "api", "local"] if m != expected_mode
                            ]
                            for other_mode in other_modes:
                                assert metadata[f"is_{other_mode}"] is False

                            print(f"✅ Mode metadata correct for {expected_mode} mode")

    def test_observability_metadata_completeness(self) -> None:
        """Test that all expected metadata is captured."""

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    messages = [
                        {"role": "system", "content": "You are helpful"},
                        {"role": "user", "content": "Hello"},
                        {"role": "user", "content": "World"},
                    ]

                    chat("test-model", messages, temperature=0.7, max_tokens=200)

                    # Verify metadata completeness
                    call_kwargs = mock_log.call_args[1]
                    metadata = call_kwargs["metadata"]

                    expected_keys = [
                        "mode",
                        "is_simulation",
                        "is_api",
                        "is_local",
                        "model",
                        "system_messages",
                        "user_messages",
                        "total_messages",
                        "temperature",
                        "max_tokens",
                    ]

                    for key in expected_keys:
                        assert key in metadata, f"Missing metadata key: {key}"

                    # Verify values
                    assert metadata["model"] == "test-model"
                    assert metadata["mode"] == "simulation"
                    assert metadata["system_messages"] == 1
                    assert metadata["user_messages"] == 2
                    assert metadata["total_messages"] == 3
                    assert metadata["temperature"] == 0.7
                    assert metadata["max_tokens"] == 200

                    print("✅ Metadata completeness verified")

    def test_pii_analysis_integration(self) -> None:
        """Test that PII analysis is called for all modes."""

        test_cases = [
            ("simulation", {"SENTRIES_SIMULATION_MODE": "true"}),
            ("api", {"GROQ_API_KEY": "test-key"}),
            ("local", {}),
        ]

        for mode_name, env_vars in test_cases:
            with patch.dict(os.environ, env_vars, clear=True):
                mock_log = MagicMock()
                mock_analyze = MagicMock(
                    return_value={"pii_spans": [{"type": "email", "start": 0, "end": 10}]}
                )

                # Mock the appropriate chat function
                if mode_name == "api":
                    mock_target = "sentries.chat.chat_with_groq"
                elif mode_name == "local":
                    mock_target = "sentries.chat.chat_with_ollama"
                else:
                    mock_target = None

                mock_context = (
                    patch(mock_target, return_value="Response with test@example.com")
                    if mock_target
                    else MagicMock()
                )

                with mock_context:
                    with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                        with patch(
                            "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                        ):
                            messages = [{"role": "user", "content": "Hello"}]
                            chat("test-model", messages)

                            # Verify PII analysis was called
                            mock_analyze.assert_called_once()
                            analyzed_text = mock_analyze.call_args[0][0]

                            # Should analyze the response text
                            assert isinstance(analyzed_text, str)

                            print(f"✅ PII analysis working for {mode_name} mode")

    def test_logging_integration(self) -> None:
        """Test that logging works correctly with observability."""

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    with patch("sentries.chat.logger") as mock_logger:
                        messages = [{"role": "user", "content": "Hello"}]
                        chat("test-model", messages)

                        # Verify logging calls
                        mock_logger.info.assert_any_call(
                            "🤖 Using simulation mode with model: test-model"
                        )
                        mock_logger.info.assert_any_call(
                            "📊 Observability enabled - logging LLM interaction"
                        )
                        mock_logger.info.assert_any_call("✅ No PII detected in LLM response")

                        print("✅ Logging integration working")

    def test_error_handling_in_observability(self) -> None:
        """Test that errors in observability don't break chat functionality."""

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Mock observability to raise an exception
            mock_log = MagicMock(side_effect=Exception("Observability error"))
            mock_analyze = MagicMock(side_effect=Exception("PII analysis error"))

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    messages = [{"role": "user", "content": "Hello"}]

                    # Should still work despite observability errors
                    chat("test-model", messages)

                    assert isinstance(response, str)
                    assert len(response) > 0

                    print("✅ Error handling in observability working")

    def test_backward_compatibility(self) -> None:
        """Test that the old chat_with_observability function still works."""

        from sentries.testsentry import chat_with_observability

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    messages = [{"role": "user", "content": "Hello"}]
                    response = chat_with_observability("test-model", messages)

                    assert isinstance(response, str)
                    assert len(response) > 0

                    # Should still call observability
                    mock_log.assert_called_once()

                    print("✅ Backward compatibility maintained")
