#!/usr/bin/env python3
"""Generate deterministic PNG reports from observability metrics."""

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from packages.metrics_core.io import DuckDBManager

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def setup_matplotlib():
    """Configure matplotlib for deterministic output."""
    plt.rcParams["figure.figsize"] = (8, 5)  # 800x500 pixels at 100 DPI
    plt.rcParams["figure.dpi"] = 120
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["font.size"] = 10
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["grid.alpha"] = 0.3

    # Set random seed for reproducible plots
    np.random.seed(42)


def generate_drift_psi_js_chart(db_manager: DuckDBManager, output_path: str):
    """Generate PSI and JS divergence chart over time."""
    try:
        # Get drift metrics from database
        drift_df = db_manager.get_drift_metrics("testsentry", "bpe", days_back=30)

        if drift_df.empty:
            # Create empty chart if no data
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.text(
                0.5,
                0.5,
                "No drift data available",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("PSI and JS Divergence Over Time")
            ax.set_xlabel("Date")
            ax.set_ylabel("Divergence Value")
            plt.tight_layout()
            plt.savefig(output_path, dpi=120, bbox_inches="tight")
            plt.close()
            return

        # Convert timestamps
        drift_df["baseline_ts"] = pd.to_datetime(drift_df["baseline_ts"])
        drift_df["current_ts"] = pd.to_datetime(drift_df["current_ts"])

        # Create the plot
        fig, ax = plt.subplots(figsize=(8, 5))

        # Plot PSI
        ax.plot(
            drift_df["current_ts"],
            drift_df["psi"],
            marker="o",
            linewidth=2,
            label="PSI",
            color="#1f77b4",
        )

        # Plot JS divergence
        ax.plot(
            drift_df["current_ts"],
            drift_df["js_divergence"],
            marker="s",
            linewidth=2,
            label="JS Divergence",
            color="#ff7f0e",
        )

        # Add threshold line for PSI
        ax.axhline(y=0.2, color="red", linestyle="--", alpha=0.7, label="PSI Threshold (0.2)")

        # Formatting
        ax.set_title("PSI and JS Divergence Over Time", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Divergence Value", fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close()

        print(f"✅ Generated drift chart: {output_path}")

    except Exception as e:
        print(f"❌ Error generating drift chart: {e}")
        # Create error chart
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(
            0.5,
            0.5,
            f"Error generating chart: {str(e)}",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="red",
        )
        ax.set_title("PSI and JS Divergence Over Time")
        plt.tight_layout()
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close()


def generate_scrubber_leakage_chart(db_manager: DuckDBManager, output_path: str):
    """Generate PII scrubbing performance chart."""
    try:
        # Get scrubber metrics from database
        scrubber_df = db_manager.get_scrubber_metrics()

        if scrubber_df.empty:
            # Create empty chart if no data
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.text(
                0.5,
                0.5,
                "No scrubber data available",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("PII Scrubbing Performance")
            ax.set_xlabel("Algorithm")
            ax.set_ylabel("Performance Metric")
            plt.tight_layout()
            plt.savefig(output_path, dpi=120, bbox_inches="tight")
            plt.close()
            return

        # Group by algorithm
        algorithms = scrubber_df["algorithm"].unique()

        # Prepare data for grouped bar chart
        metrics = ["precision", "recall", "leakage_rate"]
        x = np.arange(len(algorithms))
        width = 0.25

        fig, ax = plt.subplots(figsize=(8, 5))

        for i, metric in enumerate(metrics):
            values = [
                (
                    scrubber_df[scrubber_df["algorithm"] == alg][metric].iloc[0]
                    if not scrubber_df[scrubber_df["algorithm"] == alg].empty
                    else 0
                )
                for alg in algorithms
            ]

            ax.bar(x + i * width, values, width, label=metric.replace("_", " ").title(), alpha=0.8)

        # Formatting
        ax.set_title("PII Scrubbing Performance by Algorithm", fontsize=14, fontweight="bold")
        ax.set_xlabel("Algorithm", fontsize=12)
        ax.set_ylabel("Performance Value", fontsize=12)
        ax.set_xticks(x + width)
        ax.set_xticklabels(algorithms)
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # Set y-axis limits
        ax.set_ylim(0, 1)

        plt.tight_layout()
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close()

        print(f"✅ Generated scrubber chart: {output_path}")

    except Exception as e:
        print(f"❌ Error generating scrubber chart: {e}")
        # Create error chart
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(
            0.5,
            0.5,
            f"Error generating chart: {str(e)}",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="red",
        )
        ax.set_title("PII Scrubbing Performance")
        plt.tight_layout()
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close()


def generate_top_tokens_csv(db_manager: DuckDBManager, output_path: str):
    """Generate CSV of top tokens for drift analysis."""
    try:
        # Get latest snapshots
        bpe_snapshots = db_manager.get_latest_snapshots("testsentry", "bpe")
        sp_snapshots = db_manager.get_latest_snapshots("testsentry", "sp")

        if bpe_snapshots.empty and sp_snapshots.empty:
            # Create empty CSV
            empty_df = pd.DataFrame(columns=["algorithm", "token_id", "count", "frequency"])
            empty_df.to_csv(output_path, index=False)
            print(f"✅ Generated empty top tokens CSV: {output_path}")
            return

        # Process snapshots
        all_tokens = []

        for _, snapshot in bpe_snapshots.iterrows():
            if snapshot["token_counts"]:
                # Parse token_counts JSON
                import json

                token_counts = json.loads(snapshot["token_counts"])
                for token_id, count in token_counts.items():
                    all_tokens.append(
                        {
                            "algorithm": "bpe",
                            "token_id": int(token_id),
                            "count": count,
                            "frequency": count / snapshot["total_tokens"],
                        }
                    )

        for _, snapshot in sp_snapshots.iterrows():
            if snapshot["token_counts"]:
                # Parse token_counts JSON
                import json

                token_counts = json.loads(snapshot["token_counts"])
                for token_id, count in token_counts.items():
                    all_tokens.append(
                        {
                            "algorithm": "sp",
                            "token_id": int(token_id),
                            "count": count,
                            "frequency": count / snapshot["total_tokens"],
                        }
                    )

        if not all_tokens:
            # Create empty CSV
            empty_df = pd.DataFrame(columns=["algorithm", "token_id", "count", "frequency"])
            empty_df.to_csv(output_path, index=False)
            print(f"✅ Generated empty top tokens CSV: {output_path}")
            return

        # Create DataFrame and sort by frequency
        tokens_df = pd.DataFrame(all_tokens)
        tokens_df = tokens_df.sort_values(["algorithm", "frequency"], ascending=[True, False])

        # Save to CSV
        tokens_df.to_csv(output_path, index=False)
        print(f"✅ Generated top tokens CSV: {output_path}")

    except Exception as e:
        print(f"❌ Error generating top tokens CSV: {e}")
        # Create empty CSV
        empty_df = pd.DataFrame(columns=["algorithm", "token_id", "count", "frequency"])
        empty_df.to_csv(output_path, index=False)


def main():
    """Generate all observability reports."""
    print("📊 Generating observability reports...")

    # Setup matplotlib
    setup_matplotlib()

    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Initialize database manager
    db_manager = DuckDBManager("warehouse/metrics.duckdb")

    try:
        # Generate charts
        generate_drift_psi_js_chart(db_manager, "reports/drift_psi_js.png")
        generate_scrubber_leakage_chart(db_manager, "reports/scrubber_leakage.png")
        generate_top_tokens_csv(db_manager, "reports/drift_top_tokens.csv")

        print("✅ All reports generated successfully!")

    except Exception as e:
        print(f"❌ Error generating reports: {e}")
        sys.exit(1)

    finally:
        db_manager.disconnect()


if __name__ == "__main__":
    main()
