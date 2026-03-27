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
from src.image_only_extractor import ImageOnlyExtractor
from src.validate import Validator
from src.audit import AuditLogger
from src.export import ExcelExporter
from src.batch_reporter import BatchReporter
from src.performance_profiler import get_global_profiler
from src.output_generator import OutputGenerator

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


def _list_pdf_files(input_path: Path, recursive: bool = False) -> List[Path]:
    """
    List all PDF files in a given path.
    
    Args:
        input_path: File or directory path
        recursive: If True, scan subdirectories recursively
    
    Returns:
        Sorted list of PDF file paths
    """
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return [input_path]
    if input_path.is_dir():
        pattern = "**/*.pdf" if recursive else "*.pdf"
        return sorted(input_path.glob(pattern))
    return []


def process_batch(
    input_path: str,
    output_excel: Optional[str] = None,
    use_llm: bool = False,
    enable_audit: bool = True,
    recursive: bool = False,
) -> Dict[str, Any]:
    """
    Process one PDF or a directory of PDFs.

    Args:
        input_path: PDF path or directory path
        output_excel: Excel output path (optional)
        use_llm: Enable LLM fallback for low-confidence pages
        enable_audit: Enable SQLite audit logging
        recursive: Recursively scan subdirectories

    Returns:
        Dictionary containing `results`, `summary`, and `output_excel`
    """
    started = time.time()
    input_obj = Path(input_path)
    pdf_files = _list_pdf_files(input_obj, recursive=recursive)

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found at: {input_path}")

    classifier = DocumentClassifier()
    validator = Validator()
    audit = AuditLogger() if enable_audit else None
    exporter = ExcelExporter()

    # Always initialize LLM client for image-heavy documents (scanned PDFs)
    # Even if use_llm=False, we need it for image-only pages
    llm_client = None
    try:
        from src.llm_client import LLMClient
        llm_client = LLMClient()
        logger.info("LLM Client initialized for fallback on image-only pages")
    except Exception as e:
        logger.warning(f"Failed to initialize LLM client: {e}")
        if use_llm:
            raise  # Re-raise if user specifically requested LLM

    all_results: List[Dict[str, Any]] = []

    for pdf_file in pdf_files:
        logger.info(f"Processing file: {pdf_file.name}")
        ingested = ingest_pdf(str(pdf_file))

        for page in ingested.get("pages", []):
            page_num = page.get("page_num", 0)
            text = page.get("text", "")
            has_images = page.get("has_images", False)
            ocr_used = page.get("ocr_used", False)
            
            # Determine if we should force LLM for image-only pages
            is_image_only = has_images and (not text or not text.strip())
            force_llm_for_images = is_image_only and llm_client is not None
            
            # Handle pages with no extractable text
            if (not text or not text.strip()):
                if has_images:
                    if not force_llm_for_images:
                        # Image-only page but no LLM available - fail gracefully
                        logger.warning(f"Page {page_num} is image-only but LLM not available")
                        result_row = {
                            "file_name": pdf_file.name,
                            "page_number": page_num,
                            "document_type": "UNKNOWN",
                            "extraction_method": "none",
                            "confidence": 0.0,
                            "status": "failed",
                            "tokens_used": 0,
                            "validation_issues": ["Image-only page - OCR/LLM extraction unavailable"],
                            "validated_data": {},
                            "echallan_data": {},
                            "na_data": {},
                        }
                        all_results.append(result_row)
                        if audit:
                            audit.log_extraction(
                                file_name=pdf_file.name,
                                page_number=page_num,
                                document_type="UNKNOWN",
                                extraction_method="none",
                                confidence=0.0,
                                fields_extracted=0,
                                validation_issues=1,
                                status="failed",
                                raw_extraction=json.dumps({}),
                                validated_extraction=json.dumps({}),
                            )
                        continue
                    # else: will process with LLM below
                    logger.info(f"Page {page_num} is image-only - using LLM for extraction")
                else:
                    # No text, no images - skip this page
                    logger.warning(f"Skipping page {page_num} - no readable text and no images")
                    result_row = {
                        "file_name": pdf_file.name,
                        "page_number": page_num,
                        "document_type": "UNKNOWN",
                        "extraction_method": "none",
                        "confidence": 0.0,
                        "status": "failed",
                        "tokens_used": 0,
                        "validation_issues": ["No readable text and no images on page"],
                        "validated_data": {},
                        "echallan_data": {},
                        "na_data": {},
                    }
                    all_results.append(result_row)
                    
                    if audit:
                        audit.log_extraction(
                            file_name=pdf_file.name,
                            page_number=page_num,
                            document_type="UNKNOWN",
                            extraction_method="none",
                            confidence=0.0,
                            fields_extracted=0,
                            validation_issues=1,
                            status="failed",
                            raw_extraction=json.dumps({}),
                            validated_extraction=json.dumps({}),
                        )
                    continue

            # Classify document type (uses filename as fallback for image-only pages)
            classification = classifier.classify_with_structure(text, page_num, pdf_file.name)
            doc_type = _to_doc_type(classification)

            tokens_used = 0
            extraction_method = "deterministic"
            deterministic_conf = classification.get("confidence", 0.0)

            # For image-only pages, boost classification confidence from filename hints
            if is_image_only and doc_type != DocumentType.UNKNOWN:
                logger.debug(f"Image-only page: Using filename-based classification: {doc_type.value}")
                deterministic_conf = 0.6  # Boost confidence for filename-based classification

            # Extract using deterministic method
            if doc_type == DocumentType.ECHALLAN:
                if is_image_only:
                    # Use image-only extraction for documents with no text
                    extracted_data, det_confidence = ImageOnlyExtractor.extract_echallan_from_image(
                        pdf_file.name, page_num
                    )
                    fields_extracted = sum(1 for v in extracted_data.values() if v is not None)
                    logger.info(f"Image-only eChallan: {fields_extracted} fields from filename")
                else:
                    det = extract_echallan(text)
                    extracted_data = det["data"].model_dump(exclude_none=True)
                    det_confidence = float(det.get("overall_confidence", 0.0))
                    fields_extracted = int(det.get("extracted_fields", 0))
                
                confidence = det_confidence if det_confidence > 0 else deterministic_conf
                bucket_key = "echallan_data"
                
            elif doc_type == DocumentType.NA_PERMISSION:
                if is_image_only:
                    # Use image-only extraction for documents with no text
                    extracted_data, det_confidence = ImageOnlyExtractor.extract_na_permission_from_image(
                        pdf_file.name, page_num
                    )
                    fields_extracted = sum(1 for v in extracted_data.values() if v is not None)
                    logger.info(f"Image-only NA_PERMISSION: {fields_extracted} fields from filename")
                else:
                    det = extract_na_permission(text)
                    extracted_data = det["data"].model_dump(exclude_none=True)
                    det_confidence = float(det.get("overall_confidence", 0.0))
                    fields_extracted = int(det.get("extracted_fields", 0))
                
                confidence = det_confidence if det_confidence > 0 else deterministic_conf
                bucket_key = "na_data"
            else:
                # Document type not recognized
                logger.warning(f"Unknown document type on page {page_num}")
                extracted_data = {}
                confidence = float(deterministic_conf)
                fields_extracted = 0
                bucket_key = "unknown_data"
                extraction_method = "none"

            # Use LLM if:
            # 1. User requested it AND confidence is low
            # 2. OR it's an image-only page (force LLM)
            should_use_llm_here = (use_llm or force_llm_for_images) and llm_client
            
            if should_use_llm_here and doc_type != DocumentType.UNKNOWN:
                # For image-only pages, lower threshold to trigger LLM
                threshold = 0.5 if is_image_only else llm_client.confidence_threshold
                
                if is_image_only or confidence < threshold:
                    extraction_method = "llm"
                    llm_data, llm_confidence, tokens_used = llm_client.extract_with_fallback(
                        text=text if text.strip() else f"[Image-only page - Document type: {doc_type.value}]",
                        doc_type=doc_type,
                        deterministic_result=extracted_data,
                        deterministic_confidence=confidence,
                    )
                    extracted_data = llm_data
                    confidence = llm_confidence
                    logger.info(f"LLM extraction on page {page_num}: confidence={confidence:.3f}, tokens={tokens_used}")

            # Validate extracted data
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
                        reason="Low deterministic confidence or image-only page",
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
@click.option("--recursive", "-r", is_flag=True, default=False, help="Recursively scan subdirectories for PDFs")
@click.option("--with-reports", is_flag=True, default=False, help="Generate batch report and performance report after processing")
def main(input_path: Path, output_excel: Optional[Path], use_llm: bool, disable_audit: bool, recursive: bool, with_reports: bool):
    """Run Compliance Clerk pipeline on a PDF file or directory of PDFs."""
    profiler = get_global_profiler()
    if with_reports:
        profiler.start()
    
    result = process_batch(
        input_path=str(input_path),
        output_excel=str(output_excel) if output_excel else None,
        use_llm=use_llm,
        enable_audit=not disable_audit,
        recursive=recursive,
    )

    click.echo("\n=== Compliance Clerk Run Summary ===")
    click.echo(f"Pages Processed : {result['summary']['total_pages']}")
    click.echo(f"Success         : {result['summary']['success']}")
    click.echo(f"Partial         : {result['summary']['partial']}")
    click.echo(f"Failed          : {result['summary']['failed']}")
    click.echo(f"Success Rate    : {result['summary']['success_rate']}%")
    click.echo(f"Tokens Used     : {result['summary']['total_tokens']}")
    click.echo(f"Excel Output    : {result['output_excel']}")
    
    # Generate output.xlsx (always)
    try:
        from pathlib import Path as PathlibPath
        output_dir = PathlibPath("output")
        output_dir.mkdir(exist_ok=True)
        output_xlsx_path = output_dir / "output.xlsx"
        
        generator = OutputGenerator()
        generated_path = generator.generate(result, str(output_xlsx_path))
        click.echo(f"[OK] Output File: {generated_path}")
    except Exception as e:
        click.echo(f"[ERROR] Failed to generate output.xlsx: {e}")
        logger.error(f"Output generation error: {e}")
    
    # Generate optional reports
    if with_reports:
        profiler.end()
        
        click.echo("\n=== Generating Reports ===")
        
        # Generate batch report
        try:
            from pathlib import Path as PathlibPath
            audit_db_path = PathlibPath("logs/audit.db")
            if audit_db_path.exists():
                reporter = BatchReporter(str(audit_db_path))
                summary = reporter.get_batch_summary()
                
                # Save batch report
                output_dir = PathlibPath("output")
                output_dir.mkdir(exist_ok=True)
                report_file = output_dir / f"batch_report_{time.strftime('%Y%m%d_%H%M%S')}.txt"
                report_file.write_text(reporter.generate_text_report(summary))
                click.echo(f"[OK] Batch Report: {report_file}")
            else:
                click.echo("[WARN] No audit database found for batch report")
        except Exception as e:
            click.echo(f"[ERROR] Failed to generate batch report: {e}")
        
        # Generate performance report
        try:
            output_dir = PathlibPath("output")
            output_dir.mkdir(exist_ok=True)
            perf_file, json_file = profiler.save_report(str(output_dir))
            click.echo(f"[OK] Performance Report: {perf_file}")
        except Exception as e:
            click.echo(f"[ERROR] Failed to generate performance report: {e}")


if __name__ == "__main__":
    main()
