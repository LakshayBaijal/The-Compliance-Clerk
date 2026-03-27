"""Tests for main pipeline and CLI orchestration."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from click.testing import CliRunner

from src.main import process_batch, main
from src.schemas import DocumentType


class _DummyModel:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self, exclude_none=True):
        return self.payload


def _fake_ingest_response(file_name: str):
    return {
        "file_name": file_name,
        "file_path": file_name,
        "metadata": {"page_count": 2},
        "pages": [
            {"page_num": 0, "text": "challan number CH001 amount due 2000", "has_text": True},
            {"page_num": 1, "text": "property id P001 permission date 01/01/2024", "has_text": True},
        ],
    }


def test_process_batch_file_happy_path():
    print("Running main pipeline tests...\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        output_path = Path(tmpdir) / "result.xlsx"

        with patch("src.main.ingest_pdf") as mock_ingest, \
            patch("src.main.DocumentClassifier") as mock_classifier_cls, \
            patch("src.main.extract_echallan") as mock_extract_echallan, \
            patch("src.main.extract_na_permission") as mock_extract_na, \
            patch("src.main.Validator") as mock_validator_cls, \
            patch("src.main.AuditLogger") as mock_audit_cls, \
            patch("src.main.ExcelExporter") as mock_exporter_cls:

            mock_ingest.return_value = _fake_ingest_response("sample.pdf")

            classifier = MagicMock()
            classifier.classify_with_structure.side_effect = [
                {"document_type": DocumentType.ECHALLAN, "confidence": 0.9},
                {"document_type": DocumentType.NA_PERMISSION, "confidence": 0.85},
            ]
            mock_classifier_cls.return_value = classifier

            mock_extract_echallan.return_value = {
                "data": _DummyModel({"challan_number": "CH001", "amount_due": 2000.0}),
                "overall_confidence": 0.86,
                "extracted_fields": 2,
            }
            mock_extract_na.return_value = {
                "data": _DummyModel({"property_id": "P001", "property_area": 1200.0}),
                "overall_confidence": 0.87,
                "extracted_fields": 2,
            }

            validator = MagicMock()
            validator.validate_echallan.return_value = (
                _DummyModel({"challan_number": "CH001", "amount_due": 2000.0}),
                0.0,
                [],
            )
            validator.validate_na_permission.return_value = (
                _DummyModel({"property_id": "P001", "property_area": 1200.0}),
                0.0,
                [],
            )
            mock_validator_cls.return_value = validator

            audit = MagicMock()
            audit.log_extraction.return_value = 1
            mock_audit_cls.return_value = audit

            exporter = MagicMock()
            exporter.export_batch_results.return_value = output_path
            mock_exporter_cls.return_value = exporter

            result = process_batch(
                input_path=str(pdf_path),
                output_excel=str(output_path),
                use_llm=False,
                enable_audit=True,
            )

            assert result["summary"]["total_pages"] == 2
            assert result["summary"]["success"] == 2
            assert result["summary"]["total_tokens"] == 0
            assert len(result["results"]) == 2
            # Note: ExcelExporter is no longer used (CSV-only output)
            # exporter.export_batch_results.assert_called_once()
            assert audit.log_extraction.call_count == 2

            print("[PASS] `process_batch` handles single PDF end-to-end")


def test_process_batch_directory_happy_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        (folder / "a.pdf").write_bytes(b"%PDF-1.4 a")
        (folder / "b.pdf").write_bytes(b"%PDF-1.4 b")

        with patch("src.main.ingest_pdf") as mock_ingest, \
            patch("src.main.DocumentClassifier") as mock_classifier_cls, \
            patch("src.main.extract_echallan") as mock_extract_echallan, \
            patch("src.main.Validator") as mock_validator_cls, \
            patch("src.main.ExcelExporter") as mock_exporter_cls:

            mock_ingest.side_effect = [
                {"pages": [{"page_num": 0, "text": "challan text"}]},
                {"pages": [{"page_num": 0, "text": "challan text again"}]},
            ]

            classifier = MagicMock()
            classifier.classify_with_structure.return_value = {
                "document_type": DocumentType.ECHALLAN,
                "confidence": 0.9,
            }
            mock_classifier_cls.return_value = classifier

            mock_extract_echallan.return_value = {
                "data": _DummyModel({"challan_number": "CHX"}),
                "overall_confidence": 0.9,
                "extracted_fields": 1,
            }

            validator = MagicMock()
            validator.validate_echallan.return_value = (_DummyModel({"challan_number": "CHX"}), 0.0, [])
            mock_validator_cls.return_value = validator

            exporter = MagicMock()
            mock_exporter_cls.return_value = exporter

            result = process_batch(str(folder), use_llm=False, enable_audit=False)

            assert result["summary"]["total_pages"] == 2
            assert mock_ingest.call_count == 2
            print("[PASS] `process_batch` handles directory input")


def test_process_batch_missing_input_raises():
    try:
        process_batch("non_existent_path_abcxyz", use_llm=False, enable_audit=False)
    except FileNotFoundError:
        print("[PASS] Missing input path raises FileNotFoundError")
        return
    assert False, "Expected FileNotFoundError"


def test_process_batch_llm_path_logs_tokens():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        with patch("src.main.ingest_pdf") as mock_ingest, \
            patch("src.main.DocumentClassifier") as mock_classifier_cls, \
            patch("src.main.extract_echallan") as mock_extract_echallan, \
            patch("src.main.Validator") as mock_validator_cls, \
            patch("src.main.AuditLogger") as mock_audit_cls, \
            patch("src.main.ExcelExporter") as mock_exporter_cls, \
            patch("src.llm_client.LLMClient") as mock_llm_cls:

            mock_ingest.return_value = {"pages": [{"page_num": 0, "text": "challan text low conf"}]}

            classifier = MagicMock()
            classifier.classify_with_structure.return_value = {
                "document_type": DocumentType.ECHALLAN,
                "confidence": 0.3,
            }
            mock_classifier_cls.return_value = classifier

            mock_extract_echallan.return_value = {
                "data": _DummyModel({"challan_number": "CHL"}),
                "overall_confidence": 0.2,
                "extracted_fields": 1,
            }

            llm = MagicMock()
            llm.should_use_llm.return_value = True
            llm.extract_with_fallback.return_value = ({"challan_number": "CHL"}, 0.7, 120)
            llm.model = "mixtral-8x7b-32768"
            llm.confidence_threshold = 0.75  # Add confidence_threshold as a float, not MagicMock
            mock_llm_cls.return_value = llm

            validator = MagicMock()
            validator.validate_echallan.return_value = (_DummyModel({"challan_number": "CHL"}), 0.0, [])
            mock_validator_cls.return_value = validator

            audit = MagicMock()
            audit.log_extraction.return_value = 99
            mock_audit_cls.return_value = audit

            exporter = MagicMock()
            mock_exporter_cls.return_value = exporter

            result = process_batch(str(pdf_path), use_llm=True, enable_audit=True)

            assert result["summary"]["total_tokens"] == 120
            audit.log_token_usage.assert_called_once()
            audit.log_decision.assert_called_once()
            print("[PASS] LLM fallback path logs token usage and decisions")


def test_cli_invocation_works():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        out_path = Path(tmpdir) / "out.xlsx"

        runner = CliRunner()

        with patch("src.main.process_batch") as mock_process:
            mock_process.return_value = {
                "summary": {
                    "total_pages": 1,
                    "success": 1,
                    "partial": 0,
                    "failed": 0,
                    "success_rate": 100.0,
                    "total_tokens": 0,
                },
                "output_excel": str(out_path),
                "results": [],
            }

            result = runner.invoke(main, [str(pdf_path), "--output", str(out_path)])

            assert result.exit_code == 0
            assert "Compliance Clerk Run Summary" in result.output
            print("[PASS] CLI command executes and prints summary")


if __name__ == "__main__":
    test_process_batch_file_happy_path()
    test_process_batch_directory_happy_path()
    test_process_batch_missing_input_raises()
    test_process_batch_llm_path_logs_tokens()
    test_cli_invocation_works()
    print("\n[SUCCESS] All main pipeline tests passed!")
