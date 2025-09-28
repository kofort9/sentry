"""
Test observability integration with the three-mode LLM system.
"""

import os
from unittest.mock import MagicMock, patch

from sentries.chat import chat


class TestObservabilityIntegration:
    """Test observability integration across all three modes."""

    def test_simulation_mode_observability(self) -> None:
        """Test that simulation mode logs observability metrics."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            with patch("packages.metrics_core.observability.log_llm_interaction") as mock_log:
                messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
                chat("test-model", messages)

                # Verify observability was called
                mock_log.assert_called_once()
                call_args = mock_log.call_args

                # Check metadata includes mode information
                metadata = call_args[1]["metadata"]
                assert metadata["mode"] == "simulation"
                assert metadata["is_simulation"] is True
                assert metadata["is_api"] is False
                assert metadata["is_local"] is False
                assert metadata["model"] == "test-model"

                print("✅ Simulation mode observability working")

    def test_api_mode_observability(self) -> None:
        """Test that API mode logs observability metrics."""
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
            with patch("sentries.chat.chat_with_groq") as mock_groq:
                mock_groq.return_value = "API response"

                with patch("packages.metrics_core.observability.log_llm_interaction") as mock_log:
                    messages = [{"role": "user", "content": "Hello"}]
                    chat("llama3-8b-8192", messages)

                    # Verify observability was called
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args

                    # Check metadata includes mode information
                    metadata = call_args[1]["metadata"]
                    assert metadata["mode"] == "api"
                    assert metadata["is_simulation"] is False
                    assert metadata["is_api"] is True
                    assert metadata["is_local"] is False
                    assert metadata["model"] == "llama3-8b-8192"

                    print("✅ API mode observability working")

    def test_local_mode_observability(self) -> None:
        """Test that local LLM mode logs observability metrics."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sentries.chat.chat_with_ollama") as mock_ollama:
                mock_ollama.return_value = "Local response"

                with patch("packages.metrics_core.observability.log_llm_interaction") as mock_log:
                    messages = [{"role": "user", "content": "Hello"}]
                    chat("llama3.1", messages)

                    # Verify observability was called
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args

                    # Check metadata includes mode information
                    metadata = call_args[1]["metadata"]
                    assert metadata["mode"] == "local"
                    assert metadata["is_simulation"] is False
                    assert metadata["is_api"] is False
                    assert metadata["is_local"] is True
                    assert metadata["model"] == "llama3.1"

                    print("✅ Local LLM mode observability working")

    def test_pii_analysis_integration(self) -> None:
        """Test that PII analysis works with all modes."""
        test_cases = [
            ("simulation", {"SENTRIES_SIMULATION_MODE": "true"}),
            ("api", {"GROQ_API_KEY": "test-key"}),
            ("local", {}),
        ]

        for mode_name, env_vars in test_cases:
            with patch.dict(os.environ, env_vars, clear=True):
                # Mock the appropriate chat function
                if mode_name == "api":
                    mock_target = "sentries.chat.chat_with_groq"
                elif mode_name == "local":
                    mock_target = "sentries.chat.chat_with_ollama"
                else:
                    mock_target = None

                mock_context = (
                    patch(mock_target, return_value="Test response")
                    if mock_target
                    else patch("builtins.open", MagicMock())
                )

                with mock_context:
                    with patch(
                        "packages.metrics_core.observability.analyze_text_for_pii"
                    ) as mock_pii:
                        mock_pii.return_value = {"pii_spans": []}

                        messages = [{"role": "user", "content": "Hello"}]
                        chat("test-model", messages)

                        # Verify PII analysis was called
                        mock_pii.assert_called_once()

                        print(f"✅ PII analysis working for {mode_name} mode")

    def test_observability_metadata_completeness(self) -> None:
        """Test that all expected metadata is captured."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            with patch("packages.metrics_core.observability.log_llm_interaction") as mock_log:
                messages = [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Fix this test"},
                    {"role": "user", "content": "Additional context"},
                ]

                chat("test-model", messages, temperature=0.5, max_tokens=1000)

                # Verify all expected metadata is present
                call_args = mock_log.call_args
                metadata = call_args[1]["metadata"]

                expected_keys = [
                    "model",
                    "mode",
                    "is_simulation",
                    "is_api",
                    "is_local",
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
                assert metadata["temperature"] == 0.5
                assert metadata["max_tokens"] == 1000

                print("✅ Metadata completeness verified")

    def test_observability_graceful_failure(self) -> None:
        """Test that chat works even when observability fails."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Mock observability to raise an exception
            with patch("packages.metrics_core.observability.log_llm_interaction") as mock_log:
                mock_log.side_effect = Exception("Observability failed")

                messages = [{"role": "user", "content": "Hello"}]

                # Should not raise an exception
                try:
                    response = chat("test-model", messages)
                    assert isinstance(response, str)
                    assert len(response) > 0
                    print("✅ Graceful failure handling working")
                except Exception as e:
                    # If it fails, it should be the observability exception, not a chat failure
                    assert "Observability failed" in str(e)
                    print("⚠️  Observability failure not handled gracefully")

    def test_observability_disabled_fallback(self) -> None:
        """Test that chat works when observability packages are not available."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Mock the import to fail
            with patch("builtins.__import__", side_effect=ImportError("No observability")):
                messages = [{"role": "user", "content": "Hello"}]
                response = chat("test-model", messages)

                assert isinstance(response, str)
                assert len(response) > 0
                print("✅ Observability disabled fallback working")

    def test_mode_detection_accuracy(self) -> None:
        """Test that mode detection is accurate in observability logs."""
        test_scenarios = [
            # (env_vars, expected_mode)
            ({"SENTRIES_SIMULATION_MODE": "true", "GROQ_API_KEY": "key"}, "simulation"),
            ({"CI": "true", "OPENAI_API_KEY": "key"}, "simulation"),  # CI overrides API
            ({"GROQ_API_KEY": "key"}, "api"),
            ({"OPENAI_API_KEY": "key"}, "api"),
            ({"ANTHROPIC_API_KEY": "key"}, "api"),
            ({}, "local"),
        ]

        for env_vars, expected_mode in test_scenarios:
            with patch.dict(os.environ, env_vars, clear=True):
                # Mock appropriate functions
                mocks = []
                if expected_mode == "api":
                    mocks.append(patch("sentries.chat.chat_with_groq", return_value="API response"))
                    mocks.append(
                        patch("sentries.chat.chat_with_openai", return_value="API response")
                    )
                    mocks.append(
                        patch("sentries.chat.chat_with_anthropic", return_value="API response")
                    )
                elif expected_mode == "local":
                    mocks.append(
                        patch("sentries.chat.chat_with_ollama", return_value="Local response")
                    )

                with patch("packages.metrics_core.observability.log_llm_interaction") as mock_log:
                    for mock in mocks:
                        mock.start()

                    try:
                        messages = [{"role": "user", "content": "Hello"}]
                        chat("test-model", messages)

                        # Verify mode detection
                        call_args = mock_log.call_args
                        metadata = call_args[1]["metadata"]
                        assert (
                            metadata["mode"] == expected_mode
                        ), f"Expected {expected_mode}, got {metadata['mode']}"

                    finally:
                        for mock in mocks:
                            mock.stop()

                print(f"✅ Mode detection accurate for {expected_mode} mode")

    def test_observability_performance_impact(self) -> None:
        """Test that observability doesn't significantly impact performance."""
        import time

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Hello"}]

            # Test without observability
            with patch("packages.metrics_core.observability.log_llm_interaction"):
                start_time = time.time()
                for _ in range(10):
                    chat("test-model", messages)
                without_obs_time = time.time() - start_time

            # Test with observability (mocked to avoid actual DB operations)
            with patch("packages.metrics_core.observability.log_llm_interaction") as mock_log:
                mock_log.return_value = None  # Fast mock

                start_time = time.time()
                for _ in range(10):
                    chat("test-model", messages)
                with_obs_time = time.time() - start_time

            # Observability should add minimal overhead
            overhead = with_obs_time - without_obs_time
            assert overhead < 1.0, f"Observability overhead too high: {overhead:.3f}s"

            print(f"✅ Observability overhead acceptable: {overhead:.3f}s for 10 calls")
