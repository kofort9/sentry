"""Type definitions for observability metrics."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal


@dataclass
class Event:
    """A single event captured during TestSentry execution."""

    message: str
    service: str = "testsentry"
    release: str = "dev"
    ts: datetime = None
    event_type: str = "llm_interaction"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.ts is None:
            self.ts = datetime.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TokenizationResult:
    """Result of tokenizing text with a specific algorithm."""

    text: str
    token_ids: List[int]
    tokens: List[str]
    algorithm: Literal["bpe", "sp"]
    vocab_size: int
    char_to_token_map: Dict[int, int]  # char position -> token index
    token_to_char_map: Dict[int, tuple]  # token index -> (start_char, end_char)


@dataclass
class Snapshot:
    """A snapshot of metrics at a point in time."""

    timestamp: datetime
    service: str
    release: str
    token_counts: Dict[int, int]  # token_id -> count
    total_tokens: int
    unique_tokens: int
    algorithm: Literal["bpe", "sp"]


@dataclass
class DriftMetrics:
    """Drift detection metrics between two snapshots."""

    psi: float
    js_divergence: float
    baseline_snapshot: Snapshot
    current_snapshot: Snapshot
    significant_drift: bool = False
    psi_threshold: float = 0.2


@dataclass
class PIIDetectionResult:
    """Result of PII detection on text."""

    text: str
    detected_spans: List[tuple]  # (start_char, end_char, pii_type)
    pii_types: List[str]
    total_pii_chars: int
    total_chars: int
    pii_density: float


@dataclass
class ScrubberMetrics:
    """Metrics for PII scrubbing performance."""

    algorithm: Literal["bpe", "sp"]
    precision: float
    recall: float
    leakage_rate: float
    over_redaction_rate: float
    total_pii_chars: int
    detected_pii_chars: int
    masked_pii_chars: int
    false_positive_chars: int
