# Makefile for Sentries observability metrics

.PHONY: setup sample-data benchmarks reports streamlit check-determinism clean lint test incident help

# Default target
all: setup sample-data benchmarks reports

# Development targets
setup:
	@echo "🔧 Setting up development environment..."
	python -m pip install --upgrade pip
	pip install -e .
	pip install -e .[viz]
	pre-commit install
	@echo "✅ Setup complete"

lint:
	@echo "🧹 Running code quality checks..."
	pre-commit run --all-files
	@echo "✅ Linting complete"

test:
	@echo "🧪 Running test suite..."
	python -m pytest tests/ -v --cov=sentries --cov-report=html --cov-report=term
	@echo "✅ Tests complete"

incident:
	@echo "🚨 Running incident response diagnostics..."
	@echo "System Status:"
	@python -c "import sys; print(f'Python: {sys.version}')"
	@echo "Repository Status:"
	@git status --porcelain || echo "Not a git repository"
	@echo "Package Status:"
	@pip show sentries || echo "Package not installed"
	@echo "Environment:"
	@echo "  SENTRIES_FORCE_LOCAL: $${SENTRIES_FORCE_LOCAL:-not set}"
	@echo "  SENTRIES_SIMULATION_MODE: $${SENTRIES_SIMULATION_MODE:-not set}"
	@echo "✅ Diagnostics complete"

# Observability targets (preserved)
sample-data:
	@echo "📊 Generating synthetic sample data..."
	python -c "
from packages.metrics_core.synthetic import generate_synthetic_events
from packages.metrics_core.io import DuckDBManager
import pandas as pd

# Generate synthetic events
events = generate_synthetic_events(num_events=1000, pii_density=0.15)
print(f'Generated {len(events)} synthetic events')

# Save to database
with DuckDBManager('warehouse/metrics.duckdb') as db:
    db.insert_events(events)
    print('Events saved to database')
"
	@echo "✅ Sample data generated"

# Run benchmarks and calculate metrics
benchmarks:
	@echo "🏃 Running observability benchmarks..."
	python -c "
from packages.metrics_core.io import DuckDBManager
from packages.metrics_core.tokenize import build_bpe_tokenizer, build_sentencepiece_unigram
from packages.metrics_core.psi_js import population_stability_index, jensen_shannon
from packages.scrubber.detectors import detect_all_pii, get_pii_statistics
from packages.scrubber.masking import mask_text_with_spans
import json

# Initialize database
with DuckDBManager('warehouse/metrics.duckdb') as db:
    # Get events
    events_df = db.get_events()
    print(f'Processing {len(events_df)} events')

    # Initialize tokenizers
    bpe_tokenizer = build_bpe_tokenizer()
    sp_tokenizer = build_sentencepiece_unigram()

    # Process events for tokenization analysis
    all_text = ' '.join(events_df['message'].tolist())

    # BPE analysis
    bpe_tokens = bpe_tokenizer.encode(all_text)
    bpe_counts = {}
    for token_id in bpe_tokens.ids:
        bpe_counts[token_id] = bpe_counts.get(token_id, 0) + 1

    # SP analysis
    sp_tokens = sp_tokenizer.encode(all_text)
    sp_counts = {}
    for token_id in sp_tokens:
        sp_counts[token_id] = sp_counts.get(token_id, 0) + 1

    # Create snapshots
    from datetime import datetime
    bpe_snapshot = {
        'timestamp': datetime.now(),
        'service': 'testsentry',
        'release': 'dev',
        'algorithm': 'bpe',
        'total_tokens': len(bpe_tokens.ids),
        'unique_tokens': len(set(bpe_tokens.ids)),
        'token_counts': bpe_counts
    }

    sp_snapshot = {
        'timestamp': datetime.now(),
        'service': 'testsentry',
        'release': 'dev',
        'algorithm': 'sp',
        'total_tokens': len(sp_tokens),
        'unique_tokens': len(set(sp_tokens)),
        'token_counts': sp_counts
    }

    db.insert_snapshot(bpe_snapshot)
    db.insert_snapshot(sp_snapshot)

    # PII analysis
    pii_spans = detect_all_pii(all_text)
    pii_stats = get_pii_statistics(pii_spans, all_text)

    # Calculate scrubber metrics (simplified)
    total_chars = len(all_text)
    pii_chars = sum(end - start for start, end, _ in pii_spans)

    # BPE scrubbing simulation
    bpe_scrubber_metrics = {
        'algorithm': 'bpe',
        'precision': 0.85,  # Simulated
        'recall': 0.90,     # Simulated
        'leakage_rate': 0.05,  # Simulated
        'over_redaction_rate': 0.02,  # Simulated
        'total_pii_chars': pii_chars,
        'detected_pii_chars': int(pii_chars * 0.90),
        'masked_pii_chars': int(pii_chars * 0.90 * 0.95),
        'false_positive_chars': int(pii_chars * 0.02)
    }

    # SP scrubbing simulation
    sp_scrubber_metrics = {
        'algorithm': 'sp',
        'precision': 0.88,  # Simulated
        'recall': 0.87,     # Simulated
        'leakage_rate': 0.03,  # Simulated
        'over_redaction_rate': 0.01,  # Simulated
        'total_pii_chars': pii_chars,
        'detected_pii_chars': int(pii_chars * 0.87),
        'masked_pii_chars': int(pii_chars * 0.87 * 0.97),
        'false_positive_chars': int(pii_chars * 0.01)
    }

    db.insert_scrubber_metrics(bpe_scrubber_metrics)
    db.insert_scrubber_metrics(sp_scrubber_metrics)

    print('✅ Benchmarks completed')
"
	@echo "✅ Benchmarks completed"

# Generate deterministic PNG reports
reports:
	@echo "📈 Generating observability reports..."
	python scripts/generate_reports.py
	@echo "✅ Reports generated"

# Run Streamlit app (optional)
streamlit:
	@echo "🌐 Starting Streamlit app..."
	streamlit run apps/metrics_viz/app_streamlit.py --server.port 8501

# Check that report generation is deterministic
check-determinism:
	@echo "🔍 Checking report determinism..."
	@# Generate reports
	$(MAKE) reports
	@# Check git status
	@if git status --porcelain | grep -q "reports/"; then \
		echo "❌ Reports are not deterministic - files changed after generation"; \
		git status --porcelain; \
		exit 1; \
	else \
		echo "✅ Reports are deterministic"; \
	fi

# Clean generated files
clean:
	@echo "🧹 Cleaning generated files..."
	rm -rf warehouse/
	rm -rf reports/*.png
	rm -rf reports/*.csv
	@echo "✅ Clean complete"

# Help
help:
	@echo "Available targets:"
	@echo ""
	@echo "Development workflow:"
	@echo "  setup          - Install dependencies and setup environment"
	@echo "  lint           - Run code quality checks (black, isort, flake8, mypy)"
	@echo "  test           - Run test suite with coverage reporting"
	@echo "  incident       - Run diagnostic checks for troubleshooting"
	@echo ""
	@echo "Observability workflow:"
	@echo "  sample-data    - Generate synthetic sample data"
	@echo "  benchmarks     - Run observability benchmarks"
	@echo "  reports        - Generate deterministic PNG reports"
	@echo "  streamlit      - Run interactive Streamlit app"
	@echo "  check-determinism - Verify reports are deterministic"
	@echo "  clean          - Remove generated files"
	@echo ""
	@echo "  help           - Show this help message"
