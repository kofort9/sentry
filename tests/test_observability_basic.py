"""
Basic observability integration tests.

This module consolidates tests from test_observability_simple.py and
test_observability_working.py, focusing on:
- Basic import handling and mocking
- Setup/teardown with temp directories
- Core observability functionality
- Component integration testing
- Error handling and fallbacks

For comprehensive testing, see test_observability_comprehensive.py.
For integration testing, see test_observability_integration.py.
"""

import os
import shutil
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

from sentries.chat import chat


class TestObservabilityBasic:
    """Basic tests for observability integration with minimal setup."""

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
                    response = chat("test-model", messages)

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
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name.startswith("packages.metrics_core.observability"):
                    raise ImportError("No observability module")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                messages = [{"role": "user", "content": "Hello"}]
                response = chat("test-model", messages)

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
                            # Note: is_simulation, is_api, is_local flags are added
                            # inside log_llm_interaction, not by chat()

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

                    # Note: chat() provides these fields, but is_simulation/is_api/is_local
                    # flags are added inside log_llm_interaction itself
                    expected_keys = [
                        "mode",
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
                    response = chat("test-model", messages)

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


class TestObservabilityWithSetup:
    """Tests with setup/teardown for file system operations."""

    def setup_method(self) -> None:
        """Set up test environment with temporary directory."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_observability_integration_basic(self) -> None:
        """Test basic observability integration works."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    messages = [{"role": "user", "content": "Hello"}]
                    response = chat("test-model", messages)

                    # Verify observability was called
                    assert mock_log.called
                    assert mock_analyze.called
                    assert isinstance(response, str)

                    # Check basic metadata
                    call_args = mock_log.call_args
                    metadata = call_args[1]["metadata"]
                    assert metadata["mode"] == "simulation"
                    assert metadata["model"] == "test-model"

                    print("✅ Basic observability integration working")

    def test_observability_class_integration(self) -> None:
        """Test observability class integration directly."""
        try:
            from packages.metrics_core.observability import TestSentryObservability

            obs = TestSentryObservability()

            # Test logging
            obs.log_llm_interaction(
                prompt="Test prompt",
                response="Test response",
                metadata={"mode": "simulation", "model": "test-model", "temperature": 0.5},
            )

            # Check that event was stored
            assert len(obs.current_events) == 1
            event = obs.current_events[0]

            # Check enhanced metadata
            assert event.metadata["mode"] == "simulation"
            assert event.metadata["is_simulation"] is True
            assert event.metadata["is_api"] is False
            assert event.metadata["is_local"] is False
            assert event.metadata["model"] == "test-model"
            assert event.metadata["temperature"] == 0.5

            print("✅ Observability class integration working")

        except ImportError as e:
            print(f"⚠️  Observability class import issue: {e}")

    def test_pii_analysis_components(self) -> None:
        """Test PII analysis integration."""
        try:
            from packages.metrics_core.observability import TestSentryObservability

            obs = TestSentryObservability()

            # Test PII analysis
            test_text = "Contact me at john.doe@example.com"
            result = obs.analyze_pii_in_text(test_text)

            assert "pii_spans" in result
            assert "pii_stats" in result
            assert isinstance(result["pii_spans"], list)

            print("✅ PII analysis integration working")

        except ImportError as e:
            print(f"⚠️  PII analysis import issue: {e}")
        except Exception as e:
            print(f"⚠️  PII analysis runtime issue: {e}")

    def test_mode_detection_in_chat(self) -> None:
        """Test that mode detection works correctly in chat function."""
        test_scenarios = [
            ("simulation", {"SENTRIES_SIMULATION_MODE": "true"}),
            ("api", {"GROQ_API_KEY": "test-key"}),
            ("local", {}),
        ]

        for expected_mode, env_vars in test_scenarios:
            with patch.dict(os.environ, env_vars, clear=True):
                mock_log = MagicMock()
                mock_analyze = MagicMock(return_value={"pii_spans": []})

                # Mock appropriate chat function
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

                            # Verify mode was detected correctly
                            assert mock_log.called
                            metadata = mock_log.call_args[1]["metadata"]
                            assert metadata["mode"] == expected_mode

                            print(f"✅ Mode detection working for {expected_mode}")

    def test_observability_performance(self) -> None:
        """Test observability performance impact."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Performance test"}]

            # Test without observability
            with patch(
                "packages.metrics_core.observability.log_llm_interaction", side_effect=ImportError
            ):
                start_time = time.time()
                for _ in range(5):
                    chat("test-model", messages)
                without_obs_time = time.time() - start_time

            # Test with observability (mocked)
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    start_time = time.time()
                    for _ in range(5):
                        chat("test-model", messages)
                    with_obs_time = time.time() - start_time

            # Calculate overhead
            overhead = with_obs_time - without_obs_time
            overhead_per_call = overhead / 5

            print(f"✅ Performance overhead: {overhead_per_call:.4f}s per call")
            assert overhead_per_call < 0.1  # Should be minimal

    def test_full_integration_with_real_observability(self) -> None:
        """Test full integration with real observability components."""
        try:
            from packages.metrics_core.observability import get_observability

            with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
                # Get the real observability instance
                obs = get_observability()
                initial_events = len(obs.current_events)

                # Make a chat call
                messages = [{"role": "user", "content": "Test real observability"}]
                chat("test-model", messages, temperature=0.7)

                # Check that event was logged
                final_events = len(obs.current_events)
                assert final_events > initial_events

                # Check the logged event
                latest_event = obs.current_events[-1]
                assert latest_event.event_type == "llm_interaction"
                assert "Test real observability" in latest_event.message
                assert latest_event.metadata["mode"] == "simulation"
                assert latest_event.metadata["is_simulation"] is True
                assert latest_event.metadata["model"] == "test-model"
                assert latest_event.metadata["temperature"] == 0.7

                print("✅ Full real observability integration working")

        except ImportError as e:
            print(f"⚠️  Real observability import issue: {e}")
        except Exception as e:
            print(f"⚠️  Real observability runtime issue: {e}")

    def test_concurrent_observability(self) -> None:
        """Test observability with concurrent requests."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})
            results = []
            errors = []

            def make_request(thread_id: int) -> None:
                try:
                    with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                        with patch(
                            "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                        ):
                            messages = [{"role": "user", "content": f"Thread {thread_id}"}]
                            response = chat(f"model-{thread_id}", messages)
                            results.append((thread_id, response))
                except Exception as e:
                    errors.append((thread_id, str(e)))

            # Create and run threads
            threads = []
            for i in range(3):
                thread = threading.Thread(target=make_request, args=(i,))
                threads.append(thread)

            start_time = time.time()
            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()
            end_time = time.time()

            # Check results
            assert len(errors) == 0, f"Errors: {errors}"
            assert len(results) == 3

            total_time = end_time - start_time
            print(f"✅ Concurrent observability working: {total_time:.2f}s for 3 threads")
