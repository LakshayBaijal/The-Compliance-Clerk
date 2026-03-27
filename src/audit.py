"""
Audit logging module for tracking document extractions, decisions, and token usage.

Logs all extraction events to SQLite database for compliance and analysis.
"""

import sqlite3
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from src import config

logger = logging.getLogger(__name__)


class AuditLogger:
    """SQLite-based audit logger for extraction pipeline."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize audit logger with SQLite database.

        Args:
            db_path: Path to SQLite database (default: config.SQLITE_DB)
        """
        self.db_path = db_path or config.SQLITE_DB
        self.db_path.parent.mkdir(exist_ok=True)
        
        logger.info(f"Initializing Audit Logger: {self.db_path}")
        self._init_schema()

    def _init_schema(self):
        """Create database schema if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Extraction logs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS extraction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_name TEXT NOT NULL,
                page_number INTEGER,
                document_type TEXT,
                extraction_method TEXT,
                confidence REAL,
                fields_extracted INTEGER,
                validation_issues INTEGER,
                status TEXT,
                raw_extraction TEXT,
                validated_extraction TEXT
            )
            """
        )

        # Decision logs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                extraction_id INTEGER,
                decision_type TEXT,
                reason TEXT,
                action_taken TEXT,
                confidence_before REAL,
                confidence_after REAL,
                FOREIGN KEY(extraction_id) REFERENCES extraction_logs(id)
            )
            """
        )

        # Token usage logs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS token_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                extraction_id INTEGER,
                tier TEXT,
                tokens_used INTEGER,
                model_name TEXT,
                cost_estimate REAL,
                FOREIGN KEY(extraction_id) REFERENCES extraction_logs(id)
            )
            """
        )

        conn.commit()
        conn.close()
        logger.info("Audit schema initialized")

    def log_extraction(
        self,
        file_name: str,
        page_number: int,
        document_type: str,
        extraction_method: str,
        confidence: float,
        fields_extracted: int,
        validation_issues: int = 0,
        status: str = "success",
        raw_extraction: Optional[str] = None,
        validated_extraction: Optional[str] = None,
    ) -> int:
        """
        Log an extraction event.

        Args:
            file_name: Source PDF file name
            page_number: Page number extracted
            document_type: Type (ECHALLAN, NA_PERMISSION, UNKNOWN)
            extraction_method: Method used (deterministic, llm, ocr)
            confidence: Confidence score (0.0-1.0)
            fields_extracted: Number of fields successfully extracted
            validation_issues: Number of validation issues found
            status: Status (success, partial, failed)
            raw_extraction: JSON string of raw extraction
            validated_extraction: JSON string of validated extraction

        Returns:
            Extraction log ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO extraction_logs
            (file_name, page_number, document_type, extraction_method, confidence,
             fields_extracted, validation_issues, status, raw_extraction, validated_extraction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_name,
                page_number,
                document_type,
                extraction_method,
                confidence,
                fields_extracted,
                validation_issues,
                status,
                raw_extraction,
                validated_extraction,
            ),
        )

        conn.commit()
        extraction_id = cursor.lastrowid
        conn.close()

        logger.debug(
            f"Logged extraction: {file_name}:page{page_number} "
            f"({document_type}, {extraction_method}, conf={confidence:.2f})"
        )

        return extraction_id

    def log_decision(
        self,
        extraction_id: int,
        decision_type: str,
        reason: str,
        action_taken: str,
        confidence_before: float,
        confidence_after: float,
    ):
        """
        Log a routing/fallback decision.

        Args:
            extraction_id: ID of extraction that triggered decision
            decision_type: Type (tier_routing, fallback_to_llm, validation_alert)
            reason: Reason for decision
            action_taken: Action taken
            confidence_before: Confidence before decision
            confidence_after: Confidence after decision
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO decision_logs
            (extraction_id, decision_type, reason, action_taken, confidence_before, confidence_after)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                extraction_id,
                decision_type,
                reason,
                action_taken,
                confidence_before,
                confidence_after,
            ),
        )

        conn.commit()
        conn.close()

        logger.debug(
            f"Logged decision: {decision_type} for extraction {extraction_id} "
            f"(reason: {reason})"
        )

    def log_token_usage(
        self,
        extraction_id: int,
        tier: str,
        tokens_used: int,
        model_name: str,
        cost_estimate: Optional[float] = None,
    ):
        """
        Log token usage for LLM calls.

        Args:
            extraction_id: ID of extraction using tokens
            tier: Tier used (tier_1, tier_3, tier_4, etc.)
            tokens_used: Number of tokens consumed
            model_name: Model name (e.g., mixtral-8x7b-32768)
            cost_estimate: Estimated cost (optional)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO token_logs
            (extraction_id, tier, tokens_used, model_name, cost_estimate)
            VALUES (?, ?, ?, ?, ?)
            """,
            (extraction_id, tier, tokens_used, model_name, cost_estimate),
        )

        conn.commit()
        conn.close()

        logger.debug(
            f"Logged token usage: {tokens_used} tokens ({tier}) for extraction {extraction_id}"
        )

    def query_extractions(
        self,
        file_name: Optional[str] = None,
        document_type: Optional[str] = None,
        status: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query extraction logs with filters.

        Args:
            file_name: Filter by file name (optional)
            document_type: Filter by document type (optional)
            status: Filter by status (optional)
            hours_back: Only return logs from last N hours
            limit: Max results to return

        Returns:
            List of extraction log dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM extraction_logs WHERE timestamp > datetime('now', ?)"
        params = [f"-{hours_back} hours"]

        if file_name:
            query += " AND file_name LIKE ?"
            params.append(f"%{file_name}%")

        if document_type:
            query += " AND document_type = ?"
            params.append(document_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def query_decisions(
        self,
        decision_type: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query decision logs.

        Args:
            decision_type: Filter by decision type (optional)
            hours_back: Only return logs from last N hours
            limit: Max results to return

        Returns:
            List of decision log dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM decision_logs WHERE timestamp > datetime('now', ?)"
        params = [f"-{hours_back} hours"]

        if decision_type:
            query += " AND decision_type = ?"
            params.append(decision_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_summary_stats(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get summary statistics for a time period.

        Args:
            hours_back: Time period in hours

        Returns:
            Dictionary with aggregate statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total extractions
        cursor.execute(
            "SELECT COUNT(*) FROM extraction_logs WHERE timestamp > datetime('now', ?)",
            [f"-{hours_back} hours"],
        )
        total_extractions = cursor.fetchone()[0]

        # By status
        cursor.execute(
            """
            SELECT status, COUNT(*) as count FROM extraction_logs
            WHERE timestamp > datetime('now', ?)
            GROUP BY status
            """,
            [f"-{hours_back} hours"],
        )
        by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # By document type
        cursor.execute(
            """
            SELECT document_type, COUNT(*) as count FROM extraction_logs
            WHERE timestamp > datetime('now', ?)
            GROUP BY document_type
            """,
            [f"-{hours_back} hours"],
        )
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # By extraction method
        cursor.execute(
            """
            SELECT extraction_method, COUNT(*) as count FROM extraction_logs
            WHERE timestamp > datetime('now', ?)
            GROUP BY extraction_method
            """,
            [f"-{hours_back} hours"],
        )
        by_method = {row[0]: row[1] for row in cursor.fetchall()}

        # Average confidence
        cursor.execute(
            """
            SELECT AVG(confidence) FROM extraction_logs
            WHERE timestamp > datetime('now', ?)
            """,
            [f"-{hours_back} hours"],
        )
        avg_confidence = cursor.fetchone()[0] or 0.0

        # Total tokens used
        cursor.execute(
            """
            SELECT SUM(tokens_used) FROM token_logs
            WHERE timestamp > datetime('now', ?)
            """,
            [f"-{hours_back} hours"],
        )
        total_tokens = cursor.fetchone()[0] or 0

        # Total decisions
        cursor.execute(
            "SELECT COUNT(*) FROM decision_logs WHERE timestamp > datetime('now', ?)",
            [f"-{hours_back} hours"],
        )
        total_decisions = cursor.fetchone()[0]

        conn.close()

        stats = {
            "time_period_hours": hours_back,
            "total_extractions": total_extractions,
            "by_status": by_status,
            "by_document_type": by_type,
            "by_extraction_method": by_method,
            "average_confidence": round(avg_confidence, 3),
            "total_tokens_used": total_tokens,
            "total_decisions": total_decisions,
        }

        logger.info(f"Summary stats: {total_extractions} extractions, {total_tokens} tokens")
        return stats

    def export_summary(
        self, file_path: Path, hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Export audit summary to JSON file.

        Args:
            file_path: Path to export JSON file
            hours_back: Time period in hours

        Returns:
            Exported summary data
        """
        import json

        summary = self.get_summary_stats(hours_back)
        summary["export_timestamp"] = datetime.now().isoformat()

        with open(file_path, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Exported audit summary to {file_path}")
        return summary

    def cleanup_old_logs(self, days_old: int = 30):
        """
        Delete audit logs older than specified days (for storage management).

        Args:
            days_old: Delete logs older than this many days
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

        cursor.execute(
            "DELETE FROM extraction_logs WHERE timestamp < ?", (cutoff_date,)
        )
        rows_deleted = cursor.rowcount

        cursor.execute(
            "DELETE FROM decision_logs WHERE timestamp < ?", (cutoff_date,)
        )

        cursor.execute("DELETE FROM token_logs WHERE timestamp < ?", (cutoff_date,))

        conn.commit()
        conn.close()

        logger.info(f"Cleaned up {rows_deleted} old audit log entries (older than {days_old} days)")
