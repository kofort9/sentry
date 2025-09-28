"""DuckDB and Parquet I/O utilities for metrics storage."""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import duckdb
import pandas as pd


class DuckDBManager:
    """Manager for DuckDB operations and metrics storage."""

    def __init__(self, db_path: str = "warehouse/metrics.duckdb"):
        """Initialize DuckDB manager."""
        self.db_path = db_path
        self.conn = None
        self._ensure_db_directory()

    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def connect(self):
        """Connect to DuckDB database."""
        if self.conn is None:
            self.conn = duckdb.connect(self.db_path)
            self._create_tables()

    def disconnect(self):
        """Disconnect from DuckDB database."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _create_tables(self):
        """Create necessary tables for metrics storage."""
        if not self.conn:
            return

        # Events table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                message TEXT,
                service TEXT,
                release TEXT,
                ts TIMESTAMP,
                event_type TEXT,
                metadata JSON
            )
        """
        )

        # Snapshots table for drift detection
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP,
                service TEXT,
                release TEXT,
                algorithm TEXT,
                total_tokens INTEGER,
                unique_tokens INTEGER,
                token_counts JSON
            )
        """
        )

        # Drift metrics table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS drift_metrics (
                id INTEGER PRIMARY KEY,
                baseline_snapshot_id INTEGER,
                current_snapshot_id INTEGER,
                psi REAL,
                js_divergence REAL,
                significant_drift BOOLEAN,
                psi_threshold REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # PII detection results
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pii_detections (
                id INTEGER PRIMARY KEY,
                event_id INTEGER,
                algorithm TEXT,
                pii_type TEXT,
                char_start INTEGER,
                char_end INTEGER,
                token_start INTEGER,
                token_end INTEGER,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Scrubber metrics
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scrubber_metrics (
                id INTEGER PRIMARY KEY,
                algorithm TEXT,
                precision REAL,
                recall REAL,
                leakage_rate REAL,
                over_redaction_rate REAL,
                total_pii_chars INTEGER,
                detected_pii_chars INTEGER,
                masked_pii_chars INTEGER,
                false_positive_chars INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

    def insert_events(self, events: pd.DataFrame):
        """Insert events into the database."""
        if not self.conn:
            self.connect()

        # Convert metadata to JSON strings
        events_copy = events.copy()
        if "metadata" in events_copy.columns:
            events_copy["metadata"] = events_copy["metadata"].apply(
                lambda x: x if isinstance(x, str) else str(x)
            )

        self.conn.execute(
            """
            INSERT INTO events (message, service, release, ts, event_type, metadata)
            SELECT * FROM events_copy
        """,
            {"events_copy": events_copy},
        )

    def insert_snapshot(self, snapshot: Dict[str, Any]):
        """Insert a snapshot into the database."""
        if not self.conn:
            self.connect()

        self.conn.execute(
            """
            INSERT INTO snapshots
            (timestamp, service, release, algorithm, total_tokens, unique_tokens, token_counts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            [
                snapshot["timestamp"],
                snapshot["service"],
                snapshot["release"],
                snapshot["algorithm"],
                snapshot["total_tokens"],
                snapshot["unique_tokens"],
                str(snapshot["token_counts"]),
            ],
        )

    def insert_drift_metrics(self, drift_metrics: Dict[str, Any]):
        """Insert drift metrics into the database."""
        if not self.conn:
            self.connect()

        self.conn.execute(
            """
            INSERT INTO drift_metrics
            (baseline_snapshot_id, current_snapshot_id, psi, js_divergence,
             significant_drift, psi_threshold)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            [
                drift_metrics["baseline_snapshot_id"],
                drift_metrics["current_snapshot_id"],
                drift_metrics["psi"],
                drift_metrics["js_divergence"],
                drift_metrics["significant_drift"],
                drift_metrics["psi_threshold"],
            ],
        )

    def insert_pii_detection(self, detection: Dict[str, Any]):
        """Insert PII detection result into the database."""
        if not self.conn:
            self.connect()

        self.conn.execute(
            """
            INSERT INTO pii_detections
            (event_id, algorithm, pii_type, char_start, char_end,
             token_start, token_end)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            [
                detection["event_id"],
                detection["algorithm"],
                detection["pii_type"],
                detection["char_start"],
                detection["char_end"],
                detection["token_start"],
                detection["token_end"],
            ],
        )

    def insert_scrubber_metrics(self, metrics: Dict[str, Any]):
        """Insert scrubber metrics into the database."""
        if not self.conn:
            self.connect()

        self.conn.execute(
            """
            INSERT INTO scrubber_metrics
            (algorithm, precision, recall, leakage_rate, over_redaction_rate,
             total_pii_chars, detected_pii_chars, masked_pii_chars, false_positive_chars)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                metrics["algorithm"],
                metrics["precision"],
                metrics["recall"],
                metrics["leakage_rate"],
                metrics["over_redaction_rate"],
                metrics["total_pii_chars"],
                metrics["detected_pii_chars"],
                metrics["masked_pii_chars"],
                metrics["false_positive_chars"],
            ],
        )

    def get_events(
        self,
        service: Optional[str] = None,
        release: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Query events from the database."""
        if not self.conn:
            self.connect()

        query = "SELECT * FROM events WHERE 1=1"
        params = []

        if service:
            query += " AND service = ?"
            params.append(service)

        if release:
            query += " AND release = ?"
            params.append(release)

        if start_date:
            query += " AND ts >= ?"
            params.append(start_date)

        if end_date:
            query += " AND ts <= ?"
            params.append(end_date)

        query += " ORDER BY ts"

        return self.conn.execute(query, params).df()

    def get_latest_snapshots(self, service: str, algorithm: str) -> pd.DataFrame:
        """Get the latest snapshots for a service and algorithm."""
        if not self.conn:
            self.connect()

        query = """
            SELECT * FROM snapshots
            WHERE service = ? AND algorithm = ?
            ORDER BY timestamp DESC
            LIMIT 10
        """

        return self.conn.execute(query, [service, algorithm]).df()

    def get_drift_metrics(self, service: str, algorithm: str, days_back: int = 7) -> pd.DataFrame:
        """Get drift metrics for a service and algorithm."""
        if not self.conn:
            self.connect()

        query = """
            SELECT dm.*, s1.timestamp as baseline_ts, s2.timestamp as current_ts
            FROM drift_metrics dm
            JOIN snapshots s1 ON dm.baseline_snapshot_id = s1.id
            JOIN snapshots s2 ON dm.current_snapshot_id = s2.id
            WHERE s1.service = ? AND s1.algorithm = ?
            AND dm.created_at >= datetime('now', '-{} days')
            ORDER BY dm.created_at DESC
        """.format(
            days_back
        )

        return self.conn.execute(query, [service, algorithm]).df()

    def get_scrubber_metrics(self, algorithm: Optional[str] = None) -> pd.DataFrame:
        """Get scrubber metrics."""
        if not self.conn:
            self.connect()

        if algorithm:
            query = "SELECT * FROM scrubber_metrics WHERE algorithm = ? ORDER BY created_at DESC"
            return self.conn.execute(query, [algorithm]).df()
        else:
            query = "SELECT * FROM scrubber_metrics ORDER BY created_at DESC"
            return self.conn.execute(query).df()

    def export_to_parquet(self, table_name: str, output_path: str):
        """Export a table to Parquet format."""
        if not self.conn:
            self.connect()

        query = f"SELECT * FROM {table_name}"
        df = self.conn.execute(query).df()
        df.to_parquet(output_path, index=False)

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
