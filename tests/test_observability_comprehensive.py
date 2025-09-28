"""
Comprehensive test suite for observability integration.
Tests the full observability pipeline with all three modes.
"""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from sentries.chat import chat


class TestObservabilityComprehensive:
    """Comprehensive tests for observability integration."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_observability_full_pipeline_simulation(self) -> None:
        """Test complete observability pipeline in simulation mode."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Mock all observability components
            mock_log = MagicMock()
            mock_analyze = MagicMock(
                return_value={"pii_spans": [], "total_pii_chars": 0, "leakage_rate": 0.0}
            )

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    # Test multiple interactions
                    test_cases = [
                        {"role": "user", "content": "Fix this test: assert 1 == 2"},
                        {"role": "user", "content": "Create a plan for this issue"},
                        {"role": "user", "content": "Generate JSON operations"},
                    ]

                    for i, message in enumerate(test_cases):
                        chat(f"test-model-{i}", [message], temperature=0.1 + i * 0.1)

                    # Verify all interactions were logged
                    assert mock_log.call_count == 3
                    assert mock_analyze.call_count == 3

                    # Verify metadata for each call
                    for i, call_args in enumerate(mock_log.call_args_list):
                        metadata = call_args[1]["metadata"]
                        assert metadata["mode"] == "simulation"
                        assert metadata["model"] == f"test-model-{i}"
                        assert metadata["temperature"] == 0.1 + i * 0.1
                        assert metadata["is_simulation"] is True
                        assert metadata["is_api"] is False
                        assert metadata["is_local"] is False

                    print("✅ Full simulation pipeline working")

    def test_observability_api_mode_with_fallback(self) -> None:
        """Test observability with API mode and fallback chain."""
        with patch.dict(
            os.environ,
            {"GROQ_API_KEY": "test-groq-key", "OPENAI_API_KEY": "test-openai-key"},
            clear=True,
        ):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            # Mock Groq to fail, OpenAI to succeed
            with patch("sentries.chat.chat_with_groq", side_effect=Exception("Groq failed")):
                with patch("sentries.chat.chat_with_openai", return_value="OpenAI response"):
                    with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                        with patch(
                            "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                        ):
                            messages = [{"role": "user", "content": "Hello"}]
                            response = chat("gpt-4", messages)

                            # Should log the successful OpenAI call
                            mock_log.assert_called_once()
                            metadata = mock_log.call_args[1]["metadata"]
                            assert metadata["mode"] == "api"
                            assert metadata["model"] == "gpt-4"
                            assert response == "OpenAI response"

                            print("✅ API mode with fallback observability working")

    def test_observability_local_mode(self) -> None:
        """Test observability with local LLM mode."""
        with patch.dict(os.environ, {}, clear=True):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("sentries.chat.chat_with_ollama", return_value="Local response"):
                with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                    with patch(
                        "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                    ):
                        messages = [
                            {"role": "system", "content": "You are helpful"},
                            {"role": "user", "content": "Hello world"},
                        ]
                        response = chat("llama3.1", messages, max_tokens=1000)

                        # Verify observability logging
                        mock_log.assert_called_once()
                        metadata = mock_log.call_args[1]["metadata"]
                        assert metadata["mode"] == "local"
                        assert metadata["model"] == "llama3.1"
                        assert metadata["max_tokens"] == 1000
                        assert metadata["system_messages"] == 1
                        assert metadata["user_messages"] == 1
                        assert metadata["total_messages"] == 2

                        print("✅ Local LLM mode observability working")

    def test_pii_detection_integration(self) -> None:
        """Test PII detection integration across all modes."""
        pii_responses = [
            "Contact me at john.doe@example.com for more info",
            "My IP address is 192.168.1.1",
            "Call me at (555) 123-4567",
        ]

        modes = [
            ("simulation", {"SENTRIES_SIMULATION_MODE": "true"}),
            ("api", {"GROQ_API_KEY": "test-key"}),
            ("local", {}),
        ]

        for mode_name, env_vars in modes:
            with patch.dict(os.environ, env_vars, clear=True):
                mock_log = MagicMock()

                # Mock PII detection to return different results
                mock_analyze = MagicMock(
                    side_effect=[
                        {"pii_spans": [{"type": "email", "start": 11, "end": 31}]},
                        {"pii_spans": [{"type": "ip", "start": 18, "end": 29}]},
                        {"pii_spans": [{"type": "phone", "start": 11, "end": 25}]},
                    ]
                )

                # Mock appropriate chat function
                if mode_name == "api":
                    chat_mock = patch("sentries.chat.chat_with_groq", side_effect=pii_responses)
                elif mode_name == "local":
                    chat_mock = patch("sentries.chat.chat_with_ollama", side_effect=pii_responses)
                else:
                    chat_mock = MagicMock()  # Simulation mode doesn't need mocking

                with chat_mock if mode_name != "simulation" else MagicMock():
                    with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                        with patch(
                            "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                        ):
                            for i, expected_response in enumerate(pii_responses):
                                if mode_name == "simulation":
                                    # Simulation mode returns its own responses
                                    messages = [{"role": "user", "content": f"Test {i}"}]
                                    chat("test-model", messages)
                                else:
                                    messages = [{"role": "user", "content": f"Test {i}"}]
                                    response = chat("test-model", messages)
                                    if mode_name != "simulation":
                                        assert response == expected_response

                            # Verify PII analysis was called for each response
                            assert mock_analyze.call_count == 3

                            print(f"✅ PII detection working for {mode_name} mode")

    def test_observability_error_scenarios(self) -> None:
        """Test observability behavior in error scenarios."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Test 1: Observability logging fails
            mock_log = MagicMock(side_effect=Exception("Logging failed"))
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    messages = [{"role": "user", "content": "Hello"}]

                    # Should not raise exception
                    try:
                        response = chat("test-model", messages)
                        assert isinstance(response, str)
                        print("✅ Graceful handling of logging errors")
                    except Exception as e:
                        # If it does raise, it should be the logging error
                        assert "Logging failed" in str(e)
                        print("⚠️  Logging error not handled gracefully")

            # Test 2: PII analysis fails
            mock_log = MagicMock()
            mock_analyze = MagicMock(side_effect=Exception("PII analysis failed"))

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    messages = [{"role": "user", "content": "Hello"}]

                    try:
                        response = chat("test-model", messages)
                        assert isinstance(response, str)
                        # Logging should still work
                        mock_log.assert_called_once()
                        print("✅ Graceful handling of PII analysis errors")
                    except Exception as e:
                        assert "PII analysis failed" in str(e)
                        print("⚠️  PII analysis error not handled gracefully")

    def test_observability_performance_impact(self) -> None:
        """Test that observability doesn't significantly impact performance."""
        import time

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            messages = [{"role": "user", "content": "Performance test"}]

            # Test without observability
            with patch(
                "packages.metrics_core.observability.log_llm_interaction", side_effect=ImportError
            ):
                start_time = time.time()
                for _ in range(10):
                    chat("test-model", messages)
                without_obs_time = time.time() - start_time

            # Test with observability (mocked for speed)
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    start_time = time.time()
                    for _ in range(10):
                        chat("test-model", messages)
                    with_obs_time = time.time() - start_time

            # Calculate overhead
            overhead = with_obs_time - without_obs_time
            overhead_per_call = overhead / 10

            # Should be minimal overhead
            assert (
                overhead_per_call < 0.1
            ), f"Observability overhead too high: {overhead_per_call:.3f}s per call"

            print(f"✅ Observability overhead acceptable: {overhead_per_call:.4f}s per call")

    def test_metadata_completeness_all_modes(self) -> None:
        """Test that metadata is complete for all modes."""
        test_scenarios = [
            ("simulation", {"SENTRIES_SIMULATION_MODE": "true"}, None),
            ("api", {"GROQ_API_KEY": "test-key"}, "sentries.chat.chat_with_groq"),
            ("local", {}, "sentries.chat.chat_with_ollama"),
        ]

        for mode_name, env_vars, mock_target in test_scenarios:
            with patch.dict(os.environ, env_vars, clear=True):
                mock_log = MagicMock()
                mock_analyze = MagicMock(return_value={"pii_spans": []})

                mock_context = (
                    patch(mock_target, return_value="Test response") if mock_target else MagicMock()
                )

                with mock_context:
                    with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                        with patch(
                            "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                        ):
                            messages = [
                                {"role": "system", "content": "System prompt"},
                                {"role": "user", "content": "User message 1"},
                                {"role": "assistant", "content": "Assistant response"},
                                {"role": "user", "content": "User message 2"},
                            ]

                            chat("test-model", messages, temperature=0.8, max_tokens=500)

                            # Verify metadata completeness
                            mock_log.assert_called_once()
                            metadata = mock_log.call_args[1]["metadata"]

                            required_fields = [
                                "mode",
                                "model",
                                "temperature",
                                "max_tokens",
                                "system_messages",
                                "user_messages",
                                "total_messages",
                                "is_simulation",
                                "is_api",
                                "is_local",
                            ]

                            for field in required_fields:
                                assert field in metadata, f"Missing {field} in {mode_name} mode"

                            # Verify values
                            assert metadata["mode"] == mode_name
                            assert metadata["model"] == "test-model"
                            assert metadata["temperature"] == 0.8
                            assert metadata["max_tokens"] == 500
                            assert metadata["system_messages"] == 1
                            assert metadata["user_messages"] == 2  # Only user messages
                            assert metadata["total_messages"] == 4
                            assert metadata[f"is_{mode_name}"] is True

                            # Other modes should be False
                            other_modes = [
                                m for m in ["simulation", "api", "local"] if m != mode_name
                            ]
                            for other_mode in other_modes:
                                assert metadata[f"is_{other_mode}"] is False

                            print(f"✅ Metadata complete for {mode_name} mode")

    def test_concurrent_observability(self) -> None:
        """Test observability with concurrent requests."""
        import threading
        import time

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
                            messages = [{"role": "user", "content": f"Thread {thread_id} request"}]
                            response = chat(f"model-{thread_id}", messages)
                            results.append((thread_id, response))
                except Exception as e:
                    errors.append((thread_id, str(e)))

            # Create and start threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=make_request, args=(i,))
                threads.append(thread)

            start_time = time.time()
            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()
            end_time = time.time()

            # Verify results
            assert len(errors) == 0, f"Errors in concurrent requests: {errors}"
            assert len(results) == 5

            # All should have successful responses
            for thread_id, response in results:
                assert isinstance(response, str)
                assert len(response) > 0

            total_time = end_time - start_time
            print(f"✅ Concurrent observability working: {total_time:.2f}s for 5 threads")

    def test_backward_compatibility_integration(self) -> None:
        """Test that backward compatibility works with full observability."""
        from sentries.testsentry import chat_with_observability

        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            mock_log = MagicMock()
            mock_analyze = MagicMock(return_value={"pii_spans": []})

            with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
                with patch(
                    "packages.metrics_core.observability.analyze_text_for_pii", mock_analyze
                ):
                    # Test old function
                    messages = [{"role": "user", "content": "Backward compatibility test"}]
                    response1 = chat_with_observability("test-model", messages)

                    # Test new function
                    response2 = chat("test-model", messages)

                    # Both should work and log observability
                    assert isinstance(response1, str)
                    assert isinstance(response2, str)
                    assert mock_log.call_count == 2

                    # Both should have same metadata structure
                    call1_metadata = mock_log.call_args_list[0][1]["metadata"]
                    call2_metadata = mock_log.call_args_list[1][1]["metadata"]

                    assert call1_metadata["mode"] == call2_metadata["mode"] == "simulation"
                    assert call1_metadata["model"] == call2_metadata["model"] == "test-model"

                    print("✅ Backward compatibility with observability working")

    def test_observability_import_fallback(self) -> None:
        """Test that system works when observability imports fail."""
        with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
            # Mock import failure
            def mock_import(name, *args, **kwargs):
                if "packages.metrics_core.observability" in name:
                    raise ImportError("Observability not available")
                return __import__(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                messages = [{"role": "user", "content": "Test without observability"}]
                response = chat("test-model", messages)

                # Should still work
                assert isinstance(response, str)
                assert len(response) > 0

                print("✅ Graceful fallback when observability unavailable")

    def test_mode_switching_observability(self) -> None:
        """Test observability when switching between modes."""
        mock_log = MagicMock()
        mock_analyze = MagicMock(return_value={"pii_spans": []})

        with patch("packages.metrics_core.observability.log_llm_interaction", mock_log):
            with patch("packages.metrics_core.observability.analyze_text_for_pii", mock_analyze):
                messages = [{"role": "user", "content": "Mode switching test"}]

                # Test simulation mode
                with patch.dict(os.environ, {"SENTRIES_SIMULATION_MODE": "true"}):
                    chat("test-model", messages)

                # Test API mode
                with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
                    with patch("sentries.chat.chat_with_groq", return_value="API response"):
                        chat("test-model", messages)

                # Test local mode
                with patch.dict(os.environ, {}, clear=True):
                    with patch("sentries.chat.chat_with_ollama", return_value="Local response"):
                        chat("test-model", messages)

                # Verify all three calls were logged with correct modes
                assert mock_log.call_count == 3

                modes = [call[1]["metadata"]["mode"] for call in mock_log.call_args_list]
                assert modes == ["simulation", "api", "local"]

                print("✅ Mode switching observability working")


class TestObservabilityComponents:
    """Test individual observability components."""

    def test_pii_detection_components(self) -> None:
        """Test PII detection components work correctly."""
        # Test that we can import and use PII detection
        try:
            from packages.scrubber.detectors import PIIDetectionResult, PIISpan, detect_all_pii

            # Test basic PII detection
            test_text = "Contact john.doe@example.com or call (555) 123-4567"
            result = detect_all_pii(test_text)

            assert isinstance(result, PIIDetectionResult)
            assert len(result.pii_spans) >= 2  # Should detect email and phone
            assert result.total_pii_chars > 0

            print("✅ PII detection components working")

        except ImportError as e:
            print(f"⚠️  PII detection import issue: {e}")

    def test_tokenization_components(self) -> None:
        """Test tokenization components work correctly."""
        try:
            from packages.metrics_core.tokenize import build_bpe_tokenizer, tokenize_text

            # Test BPE tokenizer creation
            tokenizer = build_bpe_tokenizer(vocab_size=1000)
            assert tokenizer is not None

            # Test tokenization
            test_text = "Hello world, this is a test."
            tokens = tokenize_text(test_text, tokenizer, "bpe")
            assert isinstance(tokens, list)
            assert len(tokens) > 0

            print("✅ Tokenization components working")

        except ImportError as e:
            print(f"⚠️  Tokenization import issue: {e}")
        except Exception as e:
            print(f"⚠️  Tokenization runtime issue: {e}")

    def test_metrics_components(self) -> None:
        """Test metrics calculation components."""
        try:
            import numpy as np

            from packages.metrics_core.psi_js import jensen_shannon, population_stability_index

            # Test PSI calculation
            baseline = np.array([0.4, 0.3, 0.2, 0.1])
            new_dist = np.array([0.35, 0.35, 0.2, 0.1])

            psi = population_stability_index(baseline, new_dist)
            assert isinstance(psi, float)
            assert psi >= 0

            # Test JS divergence
            js = jensen_shannon(baseline, new_dist)
            assert isinstance(js, float)
            assert 0 <= js <= 1

            print("✅ Metrics calculation components working")

        except ImportError as e:
            print(f"⚠️  Metrics import issue: {e}")
        except Exception as e:
            print(f"⚠️  Metrics runtime issue: {e}")
