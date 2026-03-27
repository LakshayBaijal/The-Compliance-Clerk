"""
Batch reporting module for compliance document extraction.
Generates comprehensive reports on processing results with analytics.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger
from src.schemas import DocumentType

logger = get_logger(__name__)


class BatchReporter:
    """Generate comprehensive batch processing reports."""
    
    def __init__(self, audit_db_path: str = "audit.db"):
        """Initialize batch reporter."""
        self.audit_db_path = Path(audit_db_path)
        if not self.audit_db_path.exists():
            logger.warning(f"Audit database not found: {audit_db_path}")
    
    def get_batch_summary(self, start_time: Optional[str] = None, 
                         end_time: Optional[str] = None) -> Dict:
        """
        Generate summary statistics for a batch run.
        
        Args:
            start_time: Start timestamp (ISO format)
            end_time: End timestamp (ISO format)
        
        Returns:
            Dictionary with summary statistics
        """
        if not self.audit_db_path.exists():
            return {
                "error": "Audit database not found",
                "total_documents": 0,
                "statistics": {}
            }
        
        try:
            conn = sqlite3.connect(str(self.audit_db_path))
            cursor = conn.cursor()
            
            # Build query with optional time filters
            where_clause = "WHERE 1=1"
            params = []
            
            if start_time:
                where_clause += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                where_clause += " AND timestamp <= ?"
                params.append(end_time)
            
            # Get basic stats
            cursor.execute(f"""
                SELECT 
                    COUNT(DISTINCT file_name) as total_files,
                    COUNT(*) as total_pages,
                    COUNT(DISTINCT document_type) as doc_types
                FROM extraction_logs {where_clause}
            """, params)
            
            file_count, page_count, doc_type_count = cursor.fetchone()
            
            # Get status breakdown
            cursor.execute(f"""
                SELECT status, COUNT(*) as count
                FROM extraction_logs {where_clause}
                GROUP BY status
            """, params)
            
            status_breakdown = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get document type breakdown
            cursor.execute(f"""
                SELECT document_type, COUNT(*) as count
                FROM extraction_logs {where_clause}
                GROUP BY document_type
            """, params)
            
            doc_type_breakdown = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get confidence distribution
            cursor.execute(f"""
                SELECT 
                    CASE 
                        WHEN confidence >= 0.9 THEN '0.9-1.0'
                        WHEN confidence >= 0.75 THEN '0.75-0.9'
                        WHEN confidence >= 0.5 THEN '0.5-0.75'
                        ELSE '<0.5'
                    END as conf_range,
                    COUNT(*) as count,
                    AVG(confidence) as avg_conf
                FROM extraction_logs {where_clause}
                GROUP BY conf_range
                ORDER BY conf_range DESC
            """, params)
            
            confidence_dist = [{
                "range": row[0],
                "count": row[1],
                "average_confidence": round(row[2], 3)
            } for row in cursor.fetchall()]
            
            # Get extraction method stats
            cursor.execute(f"""
                SELECT extraction_method, COUNT(*) as count, AVG(confidence) as avg_conf
                FROM extraction_logs {where_clause}
                GROUP BY extraction_method
            """, params)
            
            method_stats = [{
                "method": row[0],
                "count": row[1],
                "average_confidence": round(row[2], 3)
            } for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "time_range": {
                    "start": start_time or "N/A",
                    "end": end_time or "N/A"
                },
                "totals": {
                    "files": file_count,
                    "pages": page_count,
                    "document_types": doc_type_count
                },
                "status_breakdown": status_breakdown,
                "document_type_breakdown": doc_type_breakdown,
                "confidence_distribution": confidence_dist,
                "extraction_methods": method_stats,
                "success_rate": round(
                    status_breakdown.get("success", 0) / max(page_count, 1) * 100, 2
                ) if page_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to generate batch summary: {e}")
            return {"error": str(e)}
    
    def get_failed_documents_report(self, limit: int = 50) -> List[Dict]:
        """
        Get list of failed or problematic documents.
        
        Args:
            limit: Maximum number of results
        
        Returns:
            List of failed document entries
        """
        if not self.audit_db_path.exists():
            return []
        
        try:
            conn = sqlite3.connect(str(self.audit_db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    file_name,
                    page_num,
                    document_type,
                    confidence,
                    status,
                    extraction_method,
                    timestamp
                FROM extraction_logs
                WHERE status IN ('failed', 'partial')
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get failed documents report: {e}")
            return []
    
    def get_document_summary(self, file_name: str) -> Dict:
        """
        Get processing summary for a specific document.
        
        Args:
            file_name: Name of the document file
        
        Returns:
            Dictionary with document processing details
        """
        if not self.audit_db_path.exists():
            return {}
        
        try:
            conn = sqlite3.connect(str(self.audit_db_path))
            cursor = conn.cursor()
            
            # Get all pages for this document
            cursor.execute("""
                SELECT 
                    page_num,
                    document_type,
                    confidence,
                    status,
                    extraction_method,
                    llm_tokens_used,
                    timestamp
                FROM extraction_logs
                WHERE file_name = ?
                ORDER BY page_num
            """, (file_name,))
            
            pages = []
            total_tokens = 0
            status_counts = defaultdict(int)
            
            for row in cursor.fetchall():
                pages.append({
                    "page": row[0],
                    "type": row[1],
                    "confidence": row[2],
                    "status": row[3],
                    "method": row[4],
                    "tokens": row[5],
                    "timestamp": row[6]
                })
                total_tokens += row[5] or 0
                status_counts[row[3]] += 1
            
            conn.close()
            
            return {
                "file_name": file_name,
                "total_pages": len(pages),
                "pages": pages,
                "status_summary": dict(status_counts),
                "total_tokens_used": total_tokens,
                "average_confidence": round(
                    sum(p["confidence"] for p in pages) / len(pages), 3
                ) if pages else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get document summary: {e}")
            return {}
    
    def get_error_analysis(self) -> Dict:
        """
        Analyze common extraction errors and patterns.
        
        Returns:
            Dictionary with error analysis
        """
        if not self.audit_db_path.exists():
            return {}
        
        try:
            conn = sqlite3.connect(str(self.audit_db_path))
            cursor = conn.cursor()
            
            # Get issues from decision logs
            cursor.execute("""
                SELECT issues, COUNT(*) as count
                FROM decision_logs
                WHERE issues IS NOT NULL AND issues != ''
                GROUP BY issues
                ORDER BY count DESC
                LIMIT 20
            """)
            
            issues = []
            for row in cursor.fetchall():
                try:
                    issue_list = json.loads(row[0])
                    if isinstance(issue_list, list):
                        for issue in issue_list:
                            issues.append({
                                "issue": issue,
                                "count": row[1]
                            })
                except json.JSONDecodeError:
                    issues.append({
                        "issue": row[0],
                        "count": row[1]
                    })
            
            # Get document types with lowest success rates
            cursor.execute("""
                SELECT 
                    document_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful
                FROM extraction_logs
                GROUP BY document_type
                ORDER BY successful DESC
            """)
            
            doc_type_stats = [{
                "type": row[0],
                "total": row[1],
                "successful": row[2],
                "success_rate": round(row[2] / row[1] * 100, 2) if row[1] > 0 else 0
            } for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                "common_issues": issues[:10],
                "document_type_performance": doc_type_stats,
                "total_issues_found": len(issues)
            }
            
        except Exception as e:
            logger.error(f"Failed to get error analysis: {e}")
            return {}
    
    def generate_text_report(self, summary: Optional[Dict] = None) -> str:
        """
        Generate human-readable text report.
        
        Args:
            summary: Batch summary dictionary (if None, will generate new one)
        
        Returns:
            Formatted text report
        """
        if summary is None:
            summary = self.get_batch_summary()
        
        lines = []
        lines.append("=" * 80)
        lines.append("COMPLIANCE DOCUMENT EXTRACTION - BATCH REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary section
        lines.append("SUMMARY STATISTICS")
        lines.append("-" * 80)
        if "error" not in summary:
            lines.append(f"Total Files:           {summary['totals']['files']}")
            lines.append(f"Total Pages:           {summary['totals']['pages']}")
            lines.append(f"Document Types Found:  {summary['totals']['document_types']}")
            lines.append(f"Overall Success Rate:  {summary['success_rate']}%")
            lines.append("")
            
            # Status breakdown
            lines.append("STATUS BREAKDOWN")
            lines.append("-" * 80)
            for status, count in summary['status_breakdown'].items():
                percentage = count / summary['totals']['pages'] * 100 if summary['totals']['pages'] > 0 else 0
                lines.append(f"  {status.upper():15} {count:6} ({percentage:5.1f}%)")
            lines.append("")
            
            # Document type breakdown
            if summary['document_type_breakdown']:
                lines.append("DOCUMENT TYPE BREAKDOWN")
                lines.append("-" * 80)
                for doc_type, count in summary['document_type_breakdown'].items():
                    percentage = count / summary['totals']['pages'] * 100 if summary['totals']['pages'] > 0 else 0
                    lines.append(f"  {doc_type:20} {count:6} ({percentage:5.1f}%)")
                lines.append("")
            
            # Confidence distribution
            if summary['confidence_distribution']:
                lines.append("CONFIDENCE DISTRIBUTION")
                lines.append("-" * 80)
                for dist in summary['confidence_distribution']:
                    lines.append(f"  {dist['range']:12} {dist['count']:6} pages  (avg: {dist['average_confidence']:.3f})")
                lines.append("")
            
            # Extraction methods
            if summary['extraction_methods']:
                lines.append("EXTRACTION METHODS")
                lines.append("-" * 80)
                for method in summary['extraction_methods']:
                    lines.append(f"  {method['method']:15} {method['count']:6} pages  (avg confidence: {method['average_confidence']:.3f})")
                lines.append("")
        else:
            lines.append(f"Error: {summary['error']}")
        
        lines.append("=" * 80)
        return "\n".join(lines)


def generate_batch_report(output_dir: str = "output", audit_db: str = "audit.db"):
    """
    Generate a complete batch report and save to file.
    
    Args:
        output_dir: Directory to save report
        audit_db: Path to audit database
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    reporter = BatchReporter(audit_db)
    
    # Generate summary
    summary = reporter.get_batch_summary()
    
    # Generate text report
    text_report = reporter.generate_text_report(summary)
    
    # Save report
    report_file = output_path / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(text_report)
    
    logger.info(f"Batch report saved: {report_file}")
    
    # Print to console
    print(text_report)
    
    return {
        "report_file": str(report_file),
        "summary": summary
    }
