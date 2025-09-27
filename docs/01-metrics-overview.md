# TestSentry Observability Metrics

This document provides an overview of the observability metrics collected during TestSentry LLM operations.

## Key Metrics

### Population Stability Index (PSI)
- **Definition**: Measures the stability of token distributions over time
- **Formula**: `PSI = Σ((new% - baseline%) * ln(new% / baseline%))`
- **Alert Threshold**: 0.2 (configurable)
- **Interpretation**: Higher values indicate more drift in tokenization patterns

### Jensen-Shannon Divergence
- **Definition**: Symmetric measure of difference between two probability distributions
- **Range**: 0 to 1 (0 = identical, 1 = completely different)
- **Formula**: `JS = 0.5 * KL(p||m) + 0.5 * KL(q||m)` where `m = 0.5 * (p + q)`
- **Use Case**: Comparing tokenization patterns between different time periods

### PII Leakage Rate
- **Definition**: Percentage of PII characters that remain visible after masking
- **Formula**: `(unmasked_pii_chars / total_pii_chars) * 100`
- **Target**: < 5% for production use
- **Why Important**: Ensures sensitive data is properly scrubbed from logs

## Tokenization Algorithms

### BPE (Byte-Pair Encoding)
- **Library**: HuggingFace tokenizers
- **Strengths**: Good for code, handles subwords well
- **Use Case**: General text processing

### SentencePiece Unigram
- **Library**: Google SentencePiece
- **Strengths**: Language-agnostic, preserves domain-specific terms
- **Use Case**: Cross-language and specialized domain processing

## Determinism Policy

All generated reports must be **deterministic** to ensure:
- Consistent CI/CD behavior
- Reproducible results across environments
- Reliable drift detection

### Enforcement
- CI fails if regenerated assets differ from committed versions
- Fixed random seeds for all operations
- Consistent matplotlib styling and DPI settings

## Report Files

### `reports/drift_psi_js.png`
- Line chart showing PSI and JS divergence over time
- Red dashed line indicates PSI threshold (0.2)
- Helps identify when tokenization patterns change significantly

### `reports/scrubber_leakage.png`
- Bar chart comparing PII scrubbing performance by algorithm
- Shows precision, recall, and leakage rates
- Helps choose optimal scrubbing strategy

### `reports/drift_top_tokens.csv`
- Tabular data of most frequent tokens by algorithm
- Includes token ID, count, and frequency
- Useful for detailed drift analysis

## Usage

### Local Development
```bash
# Setup observability
make setup

# Generate sample data and run benchmarks
make sample-data
make benchmarks

# Generate reports
make reports

# Check determinism
make check-determinism

# Run interactive dashboard
make streamlit
```

### CI Integration
Observability metrics are automatically collected when:
- PR has `test-llm` label
- PR title contains `[test-llm]`
- PR body contains `[test-llm]`
- Manual workflow dispatch with `run_llm_tests=true`

## Data Storage

- **Database**: DuckDB (`warehouse/metrics.duckdb`)
- **Format**: Parquet files for efficient storage
- **Retention**: Configurable (default: 30 days for drift analysis)

## Privacy and Security

- **No Secrets**: Only synthetic or sanitized data in repository
- **PII Detection**: Automatic detection and masking of sensitive information
- **Deterministic Masking**: HMAC-based masking preserves class labels
- **Local Processing**: All analysis happens locally, no external data transmission
