"""
Tests for Audit Logging module with SQLite operations.
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audit import AuditLogger
from src.schemas import DocumentType


def test_audit_logger_init():
    """Test AuditLogger initialization and schema creation."""
    print("Running Audit Logging tests...\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        assert db_path.exists()
        print("[PASS] AuditLogger initialized and database created")


def test_log_extraction():
    """Test logging extraction events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        extraction_id = logger.log_extraction(
            file_name="test.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.86,
            fields_extracted=9,
            validation_issues=0,
            status="success",
        )

        assert extraction_id == 1
        print(f"[PASS] Logged extraction with ID: {extraction_id}")


def test_log_decision():
    """Test logging routing decisions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        extraction_id = logger.log_extraction(
            file_name="test.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.50,
            fields_extracted=5,
            validation_issues=1,
            status="partial",
        )

        logger.log_decision(
            extraction_id=extraction_id,
            decision_type="tier_routing",
            reason="Low confidence (0.50 < 0.75)",
            action_taken="Route to LLM",
            confidence_before=0.50,
            confidence_after=0.68,
        )

        decisions = logger.query_decisions()
        assert len(decisions) == 1
        assert decisions[0]["decision_type"] == "tier_routing"
        print("[PASS] Logged and queried decision successfully")


def test_log_token_usage():
    """Test logging token usage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        extraction_id = logger.log_extraction(
            file_name="test.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="llm",
            confidence=0.75,
            fields_extracted=9,
        )

        logger.log_token_usage(
            extraction_id=extraction_id,
            tier="tier_4",
            tokens_used=125,
            model_name="mixtral-8x7b-32768",
            cost_estimate=0.001,
        )

        conn_test = __import__("sqlite3").connect(db_path)
        cursor = conn_test.cursor()
        cursor.execute("SELECT tokens_used FROM token_logs WHERE extraction_id = ?", (extraction_id,))
        result = cursor.fetchone()
        conn_test.close()

        assert result[0] == 125
        print("[PASS] Logged token usage: 125 tokens for tier_4")


def test_query_extractions_basic():
    """Test querying extraction logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        # Log 3 extractions
        for i in range(3):
            logger.log_extraction(
                file_name=f"test_{i}.pdf",
                page_number=1,
                document_type="ECHALLAN",
                extraction_method="deterministic",
                confidence=0.85,
                fields_extracted=9,
            )

        extractions = logger.query_extractions()
        assert len(extractions) == 3
        print(f"[PASS] Queried {len(extractions)} extractions")


def test_query_extractions_with_filters():
    """Test querying extractions with filters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        # Log mixed extractions
        logger.log_extraction(
            file_name="echallan_1.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.86,
            fields_extracted=9,
            status="success",
        )

        logger.log_extraction(
            file_name="na_perm_1.pdf",
            page_number=1,
            document_type="NA_PERMISSION",
            extraction_method="deterministic",
            confidence=0.87,
            fields_extracted=14,
            status="success",
        )

        logger.log_extraction(
            file_name="echallan_2.pdf",
            page_number=2,
            document_type="ECHALLAN",
            extraction_method="llm",
            confidence=0.50,
            fields_extracted=7,
            status="partial",
        )

        # Filter by document type
        echallan_only = logger.query_extractions(document_type="ECHALLAN")
        assert len(echallan_only) == 2
        print(f"[PASS] Filtered to {len(echallan_only)} ECHALLAN extractions")

        # Filter by status
        success_only = logger.query_extractions(status="success")
        assert len(success_only) == 2
        print(f"[PASS] Filtered to {len(success_only)} successful extractions")


def test_get_summary_stats():
    """Test summary statistics generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        # Log diverse extractions
        logger.log_extraction(
            file_name="test1.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.86,
            fields_extracted=9,
            status="success",
        )

        logger.log_extraction(
            file_name="test2.pdf",
            page_number=1,
            document_type="NA_PERMISSION",
            extraction_method="llm",
            confidence=0.75,
            fields_extracted=12,
            status="success",
        )

        logger.log_extraction(
            file_name="test3.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.50,
            fields_extracted=5,
            status="partial",
        )

        # Log tokens for one extraction
        logger.log_token_usage(
            extraction_id=2,
            tier="tier_4",
            tokens_used=150,
            model_name="mixtral-8x7b-32768",
        )

        stats = logger.get_summary_stats()

        assert stats["total_extractions"] == 3
        assert stats["total_tokens_used"] == 150
        assert stats["total_decisions"] == 0
        assert "by_status" in stats
        assert "by_document_type" in stats
        assert stats["average_confidence"] > 0.6
        print(f"[PASS] Summary stats: {stats['total_extractions']} extractions, "
              f"avg confidence: {stats['average_confidence']:.3f}, "
              f"tokens used: {stats['total_tokens_used']}")


def test_export_summary():
    """Test exporting audit summary to JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        export_file = Path(tmpdir) / "audit_summary.json"

        logger = AuditLogger(db_path)

        # Log a few extractions
        for i in range(2):
            logger.log_extraction(
                file_name=f"test_{i}.pdf",
                page_number=1,
                document_type="ECHALLAN",
                extraction_method="deterministic",
                confidence=0.85,
                fields_extracted=9,
            )

        exported = logger.export_summary(export_file)

        assert export_file.exists()
        assert "export_timestamp" in exported
        assert "total_extractions" in exported

        # Verify JSON is readable
        with open(export_file) as f:
            loaded = json.load(f)
            assert loaded["total_extractions"] == 2

        print(f"[PASS] Exported audit summary to {export_file.name}")


def test_query_decisions():
    """Test querying decision logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        extraction_id = logger.log_extraction(
            file_name="test.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.50,
            fields_extracted=5,
            status="partial",
        )

        # Log multiple decisions
        logger.log_decision(
            extraction_id=extraction_id,
            decision_type="tier_routing",
            reason="Low confidence",
            action_taken="Route to LLM",
            confidence_before=0.50,
            confidence_after=0.68,
        )

        logger.log_decision(
            extraction_id=extraction_id,
            decision_type="validation_alert",
            reason="Invalid vehicle format",
            action_taken="Flag for review",
            confidence_before=0.68,
            confidence_after=0.60,
        )

        # Query all decisions
        all_decisions = logger.query_decisions()
        assert len(all_decisions) == 2

        # Query specific decision type
        tier_decisions = logger.query_decisions(decision_type="tier_routing")
        assert len(tier_decisions) == 1
        assert tier_decisions[0]["decision_type"] == "tier_routing"

        print(f"[PASS] Queried decisions: {len(all_decisions)} total, "
              f"{len(tier_decisions)} tier_routing")


def test_multiple_pages_same_file():
    """Test tracking multiple pages from same file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        # Log 2 pages from same file
        file_name = "multi_page.pdf"
        for page in range(1, 3):
            logger.log_extraction(
                file_name=file_name,
                page_number=page,
                document_type="ECHALLAN" if page == 1 else "NA_PERMISSION",
                extraction_method="deterministic",
                confidence=0.85,
                fields_extracted=9 if page == 1 else 14,
            )

        extractions = logger.query_extractions(file_name=file_name)
        assert len(extractions) == 2
        assert extractions[0]["page_number"] + extractions[1]["page_number"] == 3
        print(f"[PASS] Tracked {len(extractions)} pages from same file")


def test_cleanup_old_logs():
    """Test cleanup of old audit logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        # Log extraction
        logger.log_extraction(
            file_name="test.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.85,
            fields_extracted=9,
        )

        # Get count before cleanup
        before = logger.query_extractions(hours_back=24 * 365)  # Full year
        initial_count = len(before)

        # Cleanup old logs (older than 0 days = delete all)
        logger.cleanup_old_logs(days_old=0)

        # Get count after cleanup
        after = logger.query_extractions(hours_back=24 * 365)
        final_count = len(after)

        assert final_count < initial_count
        print(f"[PASS] Cleanup removed old logs: {initial_count} → {final_count}")


def test_extraction_with_json_data():
    """Test logging extraction with JSON data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        logger = AuditLogger(db_path)

        raw_json = json.dumps({"challan_number": "CH001", "amount_due": 2000})
        validated_json = json.dumps(
            {"challan_number": "CH001", "amount_due": 2000.0, "currency": "INR"}
        )

        extraction_id = logger.log_extraction(
            file_name="test.pdf",
            page_number=1,
            document_type="ECHALLAN",
            extraction_method="deterministic",
            confidence=0.86,
            fields_extracted=9,
            raw_extraction=raw_json,
            validated_extraction=validated_json,
        )

        extractions = logger.query_extractions()
        assert len(extractions) == 1
        assert json.loads(extractions[0]["raw_extraction"])["challan_number"] == "CH001"
        print("[PASS] Logged extraction with JSON data preserved")


if __name__ == "__main__":
    test_audit_logger_init()
    test_log_extraction()
    test_log_decision()
    test_log_token_usage()
    test_query_extractions_basic()
    test_query_extractions_with_filters()
    test_get_summary_stats()
    test_export_summary()
    test_query_decisions()
    test_multiple_pages_same_file()
    test_cleanup_old_logs()
    test_extraction_with_json_data()

    print("\n[SUCCESS] All audit logging tests passed!")
