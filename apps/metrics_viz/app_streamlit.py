#!/usr/bin/env python3
"""Streamlit app for interactive observability metrics visualization."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from packages.metrics_core.io import DuckDBManager

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    """Main Streamlit app."""
    st.set_page_config(page_title="TestSentry Observability", page_icon="📊", layout="wide")

    st.title("📊 TestSentry Observability Dashboard")
    st.markdown("Interactive metrics visualization for TestSentry LLM operations")

    # Initialize database
    try:
        db_manager = DuckDBManager("warehouse/metrics.duckdb")
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        st.info("Run `make sample-data` and `make benchmarks` first")
        return

    # Sidebar filters
    st.sidebar.header("Filters")

    # Service filter
    services = ["testsentry", "docsentry", "patch-engine", "git-utils"]
    selected_service = st.sidebar.selectbox("Service", services, index=0)

    # Algorithm filter
    algorithms = ["bpe", "sp"]
    selected_algorithm = st.sidebar.selectbox("Algorithm", algorithms, index=0)

    # Date range filter
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.date_input("Start Date", value=datetime.now() - timedelta(days=7))
    with col2:
        st.date_input("End Date", value=datetime.now())

    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Drift Analysis", "🔒 PII Detection", "🧹 Scrubbing Performance", "📋 Raw Data"]
    )

    with tab1:
        st.header("Tokenization Drift Analysis")

        try:
            # Get drift metrics
            drift_df = db_manager.get_drift_metrics(
                selected_service, selected_algorithm, days_back=30
            )

            if drift_df.empty:
                st.warning("No drift data available. Run benchmarks first.")
            else:
                # PSI and JS divergence over time
                fig = go.Figure()

                fig.add_trace(
                    go.Scatter(
                        x=drift_df["current_ts"],
                        y=drift_df["psi"],
                        mode="lines+markers",
                        name="PSI",
                        line=dict(color="#1f77b4", width=3),
                    )
                )

                fig.add_trace(
                    go.Scatter(
                        x=drift_df["current_ts"],
                        y=drift_df["js_divergence"],
                        mode="lines+markers",
                        name="JS Divergence",
                        line=dict(color="#ff7f0e", width=3),
                    )
                )

                # Add PSI threshold line
                fig.add_hline(
                    y=0.2, line_dash="dash", line_color="red", annotation_text="PSI Threshold (0.2)"
                )

                fig.update_layout(
                    title=f"Drift Metrics for {selected_service} ({selected_algorithm})",
                    xaxis_title="Date",
                    yaxis_title="Divergence Value",
                    hovermode="x unified",
                )

                st.plotly_chart(fig, use_container_width=True)

                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Latest PSI", f"{drift_df['psi'].iloc[-1]:.4f}")
                with col2:
                    st.metric("Latest JS Divergence", f"{drift_df['js_divergence'].iloc[-1]:.4f}")
                with col3:
                    significant_drift = drift_df["significant_drift"].iloc[-1]
                    st.metric("Significant Drift", "Yes" if significant_drift else "No")

        except Exception as e:
            st.error(f"Error loading drift data: {e}")

    with tab2:
        st.header("PII Detection Analysis")

        try:
            # Get events with PII analysis
            events_df = db_manager.get_events(service=selected_service)

            if events_df.empty:
                st.warning("No event data available.")
            else:
                # Analyze PII in events
                from packages.scrubber.detectors import detect_all_pii, get_pii_statistics

                all_text = " ".join(events_df["message"].tolist())
                pii_spans = detect_all_pii(all_text)
                pii_stats = get_pii_statistics(pii_spans, all_text)

                # PII statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total PII Spans", pii_stats["total_spans"])
                with col2:
                    st.metric("PII Density", f"{pii_stats['pii_density']:.2%}")
                with col3:
                    st.metric("PII Types", len(pii_stats["pii_types"]))
                with col4:
                    st.metric("Char Coverage", f"{pii_stats['char_coverage']:.2%}")

                # PII types breakdown
                if pii_stats["pii_types"]:
                    pii_types_df = pd.DataFrame(
                        [
                            {"Type": pii_type, "Count": count}
                            for pii_type, count in pii_stats["pii_types"].items()
                        ]
                    )

                    fig = px.bar(pii_types_df, x="Type", y="Count", title="PII Types Detected")
                    st.plotly_chart(fig, use_container_width=True)

                # Sample PII detections
                if pii_spans:
                    st.subheader("Sample PII Detections")
                    sample_spans = pii_spans[:10]  # Show first 10

                    for i, span in enumerate(sample_spans):
                        with st.expander(f"PII Detection {i+1}: {span.pii_type}"):
                            st.code(f"Position: {span.start}-{span.end}")
                            st.code(f"Text: {all_text[span.start:span.end]}")

        except Exception as e:
            st.error(f"Error loading PII data: {e}")

    with tab3:
        st.header("PII Scrubbing Performance")

        try:
            # Get scrubber metrics
            scrubber_df = db_manager.get_scrubber_metrics()

            if scrubber_df.empty:
                st.warning("No scrubber data available. Run benchmarks first.")
            else:
                # Performance comparison
                fig = go.Figure()

                algorithms = scrubber_df["algorithm"].unique()
                metrics = ["precision", "recall", "leakage_rate"]

                for metric in metrics:
                    values = []
                    for alg in algorithms:
                        alg_data = scrubber_df[scrubber_df["algorithm"] == alg]
                        if not alg_data.empty:
                            values.append(alg_data[metric].iloc[0])
                        else:
                            values.append(0)

                    fig.add_trace(
                        go.Bar(name=metric.replace("_", " ").title(), x=algorithms, y=values)
                    )

                fig.update_layout(
                    title="Scrubbing Performance by Algorithm",
                    xaxis_title="Algorithm",
                    yaxis_title="Performance Value",
                    barmode="group",
                )

                st.plotly_chart(fig, use_container_width=True)

                # Detailed metrics table
                st.subheader("Detailed Metrics")
                st.dataframe(
                    scrubber_df[
                        [
                            "algorithm",
                            "precision",
                            "recall",
                            "leakage_rate",
                            "over_redaction_rate",
                            "created_at",
                        ]
                    ],
                    use_container_width=True,
                )

        except Exception as e:
            st.error(f"Error loading scrubber data: {e}")

    with tab4:
        st.header("Raw Data")

        try:
            # Events data
            st.subheader("Events")
            events_df = db_manager.get_events(service=selected_service)
            if not events_df.empty:
                st.dataframe(events_df, use_container_width=True)
            else:
                st.info("No events data available")

            # Snapshots data
            st.subheader("Snapshots")
            snapshots_df = db_manager.get_latest_snapshots(selected_service, selected_algorithm)
            if not snapshots_df.empty:
                st.dataframe(snapshots_df, use_container_width=True)
            else:
                st.info("No snapshots data available")

        except Exception as e:
            st.error(f"Error loading raw data: {e}")

    # Footer
    st.markdown("---")
    st.markdown("**TestSentry Observability Dashboard** - Real-time metrics for LLM operations")


if __name__ == "__main__":
    main()
