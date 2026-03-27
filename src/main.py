"""
Main pipeline and CLI for The Compliance Clerk.

Orchestrates:
- PDF ingestion
- Page classification
- Deterministic extraction
- Optional LLM fallback (token-optimized)
- Validation
- Audit logging
- Excel export
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from src.logger import get_logger
from src.schemas import DocumentType
from src.ingest import ingest_pdf
from src.classify import DocumentClassifier
from src.extract_echallan import extract_echallan
from src.extract_na import extract_na_permission
from src.validate import Validator
from src.audit import AuditLogger
from src.export import ExcelExporter

logger = get_logger(__name__)


def _to_doc_type(classification: Dict[str, Any]) -> DocumentType:
    value = classification.get("document_type", DocumentType.UNKNOWN)
    if isinstance(value, DocumentType):
        return value
    if isinstance(value, str):
        value_lower = value.lower()
        if "challan" in value_lower:
            return DocumentType.ECHALLAN
        if "na" in value_lower or "lease" in value_lower:
            return DocumentType.NA_PERMISSION
    return DocumentType.UNKNOWN


def _status_from_confidence(confidence: float, issues: List[str]) -> str:
    if confidence >= 0.75 and not issues:
        return "success"
    if confidence > 0:
        return "partial"
    return "failed"


def _list_pdf_files(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.pdf"))
    return []


def process_batch(
    input_path: str,
    output_excel: Optional[str] = None,
    use_llm: bool = False,
    enable_audit: bool = True,
) -> Dict[str, Any]:
    """
    Process one PDF or a directory of PDFs.

    Args:
        input_path: PDF path or directory path
        output_excel: Excel output path (optional)
        use_llm: Enable LLM fallback for low-confidence pages
        enable_audit: Enable SQLite audit logging

    Returns:
        Dictionary containing `results`, `summary`, and `output_excel`
    """
    started = time.time()
    input_obj = Path(input_path)
    pdf_files = _list_pdf_files(input_obj)

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found at: {input_path}")

    classifier = DocumentClassifier()
    validator = Validator()
    audit = AuditLogger() if enable_audit else None
    exporter = ExcelExporter()

    llm_client = None
    if use_llm:
        from src.llm_client import LLMClient

        llm_client = LLMClient()

    all_results: List[Dict[str, Any]] = []

    for pdf_file in pdf_files:
        logger.info(f"Processing file: {pdf_file.name}")
        ingested = ingest_pdf(str(pdf_file))

        for page in ingested.get("pages", []):
            page_num = page.get("page_num", 0)
            text = page.get("text", "")

            classification = classifier.classify_with_structure(text, page_num)
            doc_type = _to_doc_type(classification)

            tokens_used = 0
            extraction_method = "deterministic"
            deterministic_conf = classification.get("confidence", 0.0)

            if doc_type == DocumentType.ECHALLAN:
                det = extract_echallan(text)
                extracted_data = det["data"].model_dump(exclude_none=True)
                confidence = float(det.get("overall_confidence", deterministic_conf))
                fields_extracted = int(det.get("extracted_fields", 0))
                bucket_key = "echallan_data"
            elif doc_type == DocumentType.NA_PERMISSION:
                det = extract_na_permission(text)
                extracted_data = det["data"].model_dump(exclude_none=True)
                confidence = float(det.get("overall_confidence", deterministic_conf))
                fields_extracted = int(det.get("extracted_fields", 0))
                bucket_key = "na_data"
            else:
                extracted_data = {}
                confidence = float(deterministic_conf)
                fields_extracted = 0
                bucket_key = "unknown_data"
                extraction_method = "fallback_ocr"

            if use_llm and llm_client and doc_type != DocumentType.UNKNOWN and llm_client.should_use_llm(confidence):
                extraction_method = "llm"
                llm_data, llm_confidence, tokens_used = llm_client.extract_with_fallback(
                    text=text,
                    doc_type=doc_type,
                    deterministic_result=extracted_data,
                    deterministic_confidence=confidence,
                )
                extracted_data = llm_data
                confidence = llm_confidence

            if doc_type == DocumentType.ECHALLAN:
                validated, confidence_adj, issues = validator.validate_echallan(dict(extracted_data))
                validated_data = validated.model_dump(exclude_none=True)
            elif doc_type == DocumentType.NA_PERMISSION:
                validated, confidence_adj, issues = validator.validate_na_permission(dict(extracted_data))
                validated_data = validated.model_dump(exclude_none=True)
            else:
                validated_data = extracted_data
                confidence_adj = 0.0
                issues = ["Document type unknown"] if not text.strip() else []

            final_confidence = max(0.0, min(1.0, confidence + confidence_adj))
            status = _status_from_confidence(final_confidence, issues)

            result_row = {
                "file_name": pdf_file.name,
                "page_number": page_num,
                "document_type": doc_type.name,
                "extraction_method": extraction_method,
                "confidence": round(final_confidence, 3),
                "status": status,
                "tokens_used": int(tokens_used),
                "validation_issues": issues,
                "validated_data": validated_data,
                "echallan_data": validated_data if doc_type == DocumentType.ECHALLAN else {},
                "na_data": validated_data if doc_type == DocumentType.NA_PERMISSION else {},
            }
            all_results.append(result_row)

            if audit:
                extraction_id = audit.log_extraction(
                    file_name=pdf_file.name,
                    page_number=page_num,
                    document_type=doc_type.name,
                    extraction_method=extraction_method,
                    confidence=final_confidence,
                    fields_extracted=fields_extracted,
                    validation_issues=len(issues),
                    status=status,
                    raw_extraction=json.dumps(extracted_data),
                    validated_extraction=json.dumps(validated_data),
                )

                if extraction_method == "llm":
                    audit.log_decision(
                        extraction_id=extraction_id,
                        decision_type="fallback_to_llm",
                        reason="Low deterministic confidence",
                        action_taken="Applied LLM extraction",
                        confidence_before=confidence,
                        confidence_after=final_confidence,
                    )

                if tokens_used > 0:
                    model_name = llm_client.model if llm_client else "unknown"
                    audit.log_token_usage(
                        extraction_id=extraction_id,
                        tier="tier_4",
                        tokens_used=int(tokens_used),
                        model_name=model_name,
                    )

    if output_excel:
        out_path = Path(output_excel)
    else:
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"compliance_results_{timestamp}.xlsx"

    exporter.export_batch_results(all_results, out_path)

    total = len(all_results)
    success = len([row for row in all_results if row["status"] == "success"])
    partial = len([row for row in all_results if row["status"] == "partial"])
    failed = len([row for row in all_results if row["status"] == "failed"])
    total_tokens = sum(row.get("tokens_used", 0) for row in all_results)

    summary = {
        "total_pages": total,
        "success": success,
        "partial": partial,
        "failed": failed,
        "success_rate": round((success / total) * 100, 2) if total else 0.0,
        "total_tokens": total_tokens,
        "elapsed_seconds": round(time.time() - started, 2),
    }

    logger.info(
        f"Batch complete: pages={summary['total_pages']}, "
        f"success_rate={summary['success_rate']}%, tokens={summary['total_tokens']}"
    )

    return {
        "results": all_results,
        "summary": summary,
        "output_excel": str(out_path),
    }


@click.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "output_excel", type=click.Path(path_type=Path), default=None, help="Excel output path")
@click.option("--use-llm", is_flag=True, default=False, help="Enable LLM fallback for low-confidence extraction")
@click.option("--disable-audit", is_flag=True, default=False, help="Disable SQLite audit logging")
def main(input_path: Path, output_excel: Optional[Path], use_llm: bool, disable_audit: bool):
    """Run Compliance Clerk pipeline on a PDF file or directory of PDFs."""
    result = process_batch(
        input_path=str(input_path),
        output_excel=str(output_excel) if output_excel else None,
        use_llm=use_llm,
        enable_audit=not disable_audit,
    )

    click.echo("\n=== Compliance Clerk Run Summary ===")
    click.echo(f"Pages Processed : {result['summary']['total_pages']}")
    click.echo(f"Success         : {result['summary']['success']}")
    click.echo(f"Partial         : {result['summary']['partial']}")
    click.echo(f"Failed          : {result['summary']['failed']}")
    click.echo(f"Success Rate    : {result['summary']['success_rate']}%")
    click.echo(f"Tokens Used     : {result['summary']['total_tokens']}")
    click.echo(f"Excel Output    : {result['output_excel']}")


if __name__ == "__main__":
    main()
