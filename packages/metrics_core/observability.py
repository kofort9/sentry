"""Observability hooks for TestSentry LLM operations."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd

from ..scrubber.detectors import detect_all_pii, get_pii_statistics
from .io import DuckDBManager
from .psi_js import jensen_shannon, population_stability_index
from .tokenize import build_bpe_tokenizer, build_sentencepiece_unigram, tokenize_text
from .types import DriftMetrics, Event, Snapshot, TokenizationResult


class TestSentryObservability:
    """Observability manager for TestSentry operations."""

    def __init__(self, db_path: str = "warehouse/metrics.duckdb"):
        """Initialize observability manager."""
        self.db_manager = DuckDBManager(db_path)
        self.logger = logging.getLogger("testsentry.observability")

        # Initialize tokenizers
        self.bpe_tokenizer = None
        self.sp_tokenizer = None

        # Metrics storage
        self.current_events: List[Event] = []
        self.baseline_snapshots: Dict[str, Snapshot] = {}

    def initialize_tokenizers(self):
        """Initialize BPE and SentencePiece tokenizers."""
        try:
            self.bpe_tokenizer = build_bpe_tokenizer()
            self.sp_tokenizer = build_sentencepiece_unigram()
            self.logger.info("Tokenizers initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize tokenizers: {e}")

    def log_llm_interaction(
        self,
        prompt: str,
        response: str,
        service: str = "testsentry",
        release: str = "dev",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log an LLM interaction for observability."""
        if metadata is None:
            metadata = {}

        # Create event with enhanced metadata for three-mode system
        event = Event(
            message=f"PROMPT: {prompt}\nRESPONSE: {response}",
            service=service,
            release=release,
            event_type="llm_interaction",
            metadata={
                "prompt_length": len(prompt),
                "response_length": len(response),
                "total_length": len(prompt) + len(response),
                "mode": metadata.get("mode", "unknown"),  # Track LLM mode
                "is_simulation": metadata.get("mode") == "simulation",
                "is_api": metadata.get("mode") == "api",
                "is_local": metadata.get("mode") == "local",
                **metadata,
            },
        )

        self.current_events.append(event)

        # Log to console
        self.logger.info(f"LLM interaction logged: {service}/{release}")
        self.logger.debug(f"Prompt length: {len(prompt)}, Response length: {len(response)}")

    def analyze_pii_in_text(self, text: str) -> Dict[str, Any]:
        """Analyze PII in text and return metrics."""
        # Detect PII
        pii_result = detect_all_pii(text)
        pii_spans = pii_result.pii_spans
        pii_stats = get_pii_statistics(pii_spans, text)

        # Log PII detection
        if pii_spans:
            self.logger.warning(
                f"PII detected: {len(pii_spans)} spans, {pii_stats['pii_density']:.2%} density"
            )
            for span in pii_spans:
                self.logger.debug(f"PII span: {span.pii_type} at {span.start}-{span.end}")
        else:
            self.logger.info("No PII detected in text")

        return {
            "pii_spans": [(s.start, s.end, s.pii_type) for s in pii_spans],
            "pii_stats": pii_stats,
        }

    def tokenize_and_analyze(self, text: str) -> Dict[str, TokenizationResult]:
        """Tokenize text with both BPE and SentencePiece and analyze."""
        if not self.bpe_tokenizer or not self.sp_tokenizer:
            self.initialize_tokenizers()

        results: Dict[str, TokenizationResult] = {}

        # BPE tokenization
        try:
            if self.bpe_tokenizer is not None:
                bpe_ids = tokenize_text(text, self.bpe_tokenizer, "bpe")
                bpe_tokens = self.bpe_tokenizer.decode(bpe_ids)

                results["bpe"] = TokenizationResult(
                    text=text,
                    token_ids=bpe_ids,
                    tokens=bpe_tokens.split(),
                    algorithm="bpe",
                    vocab_size=32000,
                    char_to_token_map={},  # Simplified for now
                    token_to_char_map={},
                )

                self.logger.info(f"BPE tokenization: {len(bpe_ids)} tokens")

        except Exception as e:
            self.logger.error(f"BPE tokenization failed: {e}")

        # SentencePiece tokenization
        try:
            if self.sp_tokenizer is not None:
                sp_ids = tokenize_text(text, self.sp_tokenizer, "sp")
                sp_tokens = self.sp_tokenizer.decode(sp_ids)

                results["sp"] = TokenizationResult(
                    text=text,
                    token_ids=sp_ids,
                    tokens=sp_tokens.split(),
                    algorithm="sp",
                    vocab_size=32000,
                    char_to_token_map={},  # Simplified for now
                    token_to_char_map={},
                )

                self.logger.info(f"SP tokenization: {len(sp_ids)} tokens")

        except Exception as e:
            self.logger.error(f"SP tokenization failed: {e}")

        return results

    def create_snapshot(
        self, service: str, release: str, algorithm: Literal["bpe", "sp"]
    ) -> Optional[Snapshot]:
        """Create a snapshot of current tokenization metrics."""
        if not self.current_events:
            return None

        # Collect all text from events
        all_text = " ".join(event.message for event in self.current_events)

        # Tokenize
        tokenization_results = self.tokenize_and_analyze(all_text)

        if algorithm not in tokenization_results:
            self.logger.error(f"No tokenization results for algorithm: {algorithm}")
            return None

        result = tokenization_results[algorithm]

        # Count token frequencies
        token_counts: Dict[int, int] = {}
        for token_id in result.token_ids:
            token_counts[token_id] = token_counts.get(token_id, 0) + 1

        snapshot = Snapshot(
            timestamp=datetime.now(),
            service=service,
            release=release,
            token_counts=token_counts,
            total_tokens=len(result.token_ids),
            unique_tokens=len(set(result.token_ids)),
            algorithm=algorithm,
        )

        self.logger.info(f"Snapshot created: {service}/{release} - {algorithm}")
        self.logger.info(f"Total tokens: {snapshot.total_tokens}, Unique: {snapshot.unique_tokens}")

        return snapshot

    def calculate_drift(
        self, baseline_snapshot: Snapshot, current_snapshot: Snapshot
    ) -> DriftMetrics:
        """Calculate drift metrics between two snapshots."""
        # Convert token counts to arrays for PSI/JS calculation
        all_token_ids = set(baseline_snapshot.token_counts.keys()) | set(
            current_snapshot.token_counts.keys()
        )

        baseline_counts = []
        current_counts = []

        for token_id in sorted(all_token_ids):
            baseline_counts.append(baseline_snapshot.token_counts.get(token_id, 0))
            current_counts.append(current_snapshot.token_counts.get(token_id, 0))

        baseline_counts = np.array(baseline_counts)
        current_counts = np.array(current_counts)

        # Calculate PSI and JS divergence
        psi = population_stability_index(baseline_counts, current_counts)
        js_divergence = jensen_shannon(baseline_counts, current_counts)

        # Determine if drift is significant
        psi_threshold = 0.2
        significant_drift = psi > psi_threshold

        drift_metrics = DriftMetrics(
            psi=psi,
            js_divergence=js_divergence,
            baseline_snapshot=baseline_snapshot,
            current_snapshot=current_snapshot,
            significant_drift=significant_drift,
            psi_threshold=psi_threshold,
        )

        self.logger.info(
            f"Drift calculated: PSI={psi:.4f}, JS={js_divergence:.4f}, "
            f"Significant={significant_drift}"
        )

        return drift_metrics

    def save_metrics_to_db(self):
        """Save current metrics to database."""
        try:
            with self.db_manager:
                # Save events
                if self.current_events:
                    events_df = pd.DataFrame(
                        [
                            {
                                "message": event.message,
                                "service": event.service,
                                "release": event.release,
                                "ts": event.ts,
                                "event_type": event.event_type,
                                "metadata": json.dumps(event.metadata),
                            }
                            for event in self.current_events
                        ]
                    )
                    self.db_manager.insert_events(events_df)

                # Save snapshots
                for service in ["testsentry"]:
                    for algorithm in ["bpe", "sp"]:
                        snapshot = self.create_snapshot(service, "dev", algorithm)
                        if snapshot:
                            snapshot_dict = {
                                "timestamp": snapshot.timestamp,
                                "service": snapshot.service,
                                "release": snapshot.release,
                                "algorithm": snapshot.algorithm,
                                "total_tokens": snapshot.total_tokens,
                                "unique_tokens": snapshot.unique_tokens,
                                "token_counts": snapshot.token_counts,
                            }
                            self.db_manager.insert_snapshot(snapshot_dict)

                self.logger.info("Metrics saved to database")

        except Exception as e:
            self.logger.error(f"Failed to save metrics to database: {e}")

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Get summary metrics for logging."""
        if not self.current_events:
            return {"message": "No events recorded"}

        # Basic stats
        total_events = len(self.current_events)
        total_chars = sum(len(event.message) for event in self.current_events)

        # PII analysis
        all_text = " ".join(event.message for event in self.current_events)
        pii_analysis = self.analyze_pii_in_text(all_text)

        # Tokenization analysis
        tokenization_results = self.tokenize_and_analyze(all_text)

        summary = {
            "total_events": total_events,
            "total_chars": total_chars,
            "pii_detected": len(pii_analysis["pii_spans"]) > 0,
            "pii_density": pii_analysis["pii_stats"]["pii_density"],
            "tokenization": {
                algorithm: {
                    "token_count": len(result.token_ids),
                    "unique_tokens": len(set(result.token_ids)),
                }
                for algorithm, result in tokenization_results.items()
            },
        }

        return summary


# Global observability instance
_observability = None


def get_observability() -> TestSentryObservability:
    """Get the global observability instance."""
    global _observability
    if _observability is None:
        _observability = TestSentryObservability()
    return _observability


def log_llm_interaction(prompt: str, response: str, **kwargs):
    """Convenience function to log LLM interactions."""
    obs = get_observability()
    obs.log_llm_interaction(prompt, response, **kwargs)


def analyze_text_for_pii(text: str) -> Dict[str, Any]:
    """Convenience function to analyze text for PII."""
    obs = get_observability()
    return obs.analyze_pii_in_text(text)


def save_observability_metrics():
    """Convenience function to save metrics."""
    obs = get_observability()
    obs.save_metrics_to_db()
