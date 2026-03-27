"""
CSV exporter for compliance document extraction results.

Generates a single CSV file with extracted data in the format:
Sr.no | Village | Survey No. | Area in NA Order | Dated | NA Order No. | 
Lease Deed Doc. No. | Lease Area | Lease Start | Lease End | Status
"""

import logging
import csv
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ComplianceCSVExporter:
    """Exports extraction results in CSV format for compliance documents."""

    # Expected columns for Lease Deed (NA Permission)
    NA_PERMISSION_COLUMNS = [
        "Sr.no.",
        "Village",
        "Survey No.",
        "Area in NA Order",
        "Dated",
        "NA Order No.",
        "Lease Deed Doc. No.",
        "Lease Area",
        "Lease Start",
        "Lease End",
        "Status",
    ]

    # Expected columns for Challan
    ECHALLAN_COLUMNS = [
        "Sr.no.",
        "Vehicle Reg.",
        "Challan No.",
        "Violation",
        "Amount Due",
        "Date Issued",
        "Due Date",
        "Status",
        "Payment Status",
    ]

    def __init__(self):
        """Initialize CSV exporter."""
        logger.info("Compliance CSV Exporter initialized")

    def export_compliance_format(
        self,
        results: List[Dict[str, Any]],
        output_path: Path,
    ) -> Path:
        """
        Export extraction results in CSV format.
        
        Creates separate CSV files for each document type if both are present.

        Args:
            results: List of extraction result dictionaries
            output_path: Path to write CSV file (base name, type suffix added if needed)

        Returns:
            Path to created CSV file (or first file if multiple created)
        """
        # Separate results by document type
        na_permission_results = [r for r in results if r.get("document_type") == "NA_PERMISSION"]
        echallan_results = [r for r in results if r.get("document_type") == "ECHALLAN"]

        created_paths = []

        # Export NA Permission data
        if na_permission_results:
            na_rows = self._prepare_na_permission_rows(na_permission_results)
            
            # If we have both types, add suffix to filename
            if echallan_results:
                base_name = output_path.stem
                na_path = output_path.parent / f"{base_name}_lease_deeds.csv"
            else:
                na_path = output_path
            
            with open(na_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.NA_PERMISSION_COLUMNS)
                writer.writeheader()
                writer.writerows(na_rows)
            
            logger.info(f"Exported NA Permission data to CSV: {na_path}")
            created_paths.append(na_path)

        # Export eChallan data
        if echallan_results:
            echallan_rows = self._prepare_echallan_rows(echallan_results)
            
            # If we have both types, add suffix to filename
            if na_permission_results:
                base_name = output_path.stem
                echallan_path = output_path.parent / f"{base_name}_challans.csv"
            else:
                echallan_path = output_path
            
            with open(echallan_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.ECHALLAN_COLUMNS)
                writer.writeheader()
                writer.writerows(echallan_rows)
            
            logger.info(f"Exported eChallan data to CSV: {echallan_path}")
            created_paths.append(echallan_path)

        return created_paths[0] if created_paths else output_path

    def _prepare_na_permission_rows(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Prepare NA Permission (Lease Deed) rows for CSV export.

        Args:
            results: List of extraction results

        Returns:
            List of dictionaries ready for CSV writing
        """
        rows = []
        sr_no = 1

        for result in results:
            # Use na_data field (contains validated extraction data)
            na_data = result.get("na_data", {})
            filename = result.get("file_name", "")
            status = result.get("status", "failed").upper()

            row = {
                "Sr.no.": sr_no,
                "Village": self._extract_village(filename) or na_data.get("property_address"),
                "Survey No.": na_data.get("plot_number") or self._extract_survey_no(na_data),
                "Area in NA Order": na_data.get("property_area"),
                "Dated": na_data.get("permission_date"),
                "NA Order No.": na_data.get("property_id"),
                "Lease Deed Doc. No.": na_data.get("lease_deed_number"),
                "Lease Area": na_data.get("property_area"),
                "Lease Start": na_data.get("permission_date"),
                "Lease End": na_data.get("expiry_date"),
                "Status": status,
            }

            rows.append(row)
            sr_no += 1

        return rows

    def _prepare_echallan_rows(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare eChallan rows for CSV export.

        Args:
            results: List of extraction results

        Returns:
            List of dictionaries ready for CSV writing
        """
        rows = []
        sr_no = 1

        for result in results:
            # Use echallan_data field (contains validated extraction data)
            echallan_data = result.get("echallan_data", {})
            status = result.get("status", "failed").upper()
            payment_status = "PAID" if echallan_data.get("paid") else "UNPAID"

            row = {
                "Sr.no.": sr_no,
                "Vehicle Reg.": echallan_data.get("vehicle_registration") or echallan_data.get("vehicle_reg"),
                "Challan No.": echallan_data.get("challan_number") or echallan_data.get("challan_no"),
                "Violation": echallan_data.get("violation_code") or echallan_data.get("violation"),
                "Amount Due": echallan_data.get("amount_due") or echallan_data.get("amount"),
                "Date Issued": echallan_data.get("issue_date") or echallan_data.get("date_issued"),
                "Due Date": echallan_data.get("due_date"),
                "Status": status,
                "Payment Status": payment_status,
            }

            rows.append(row)
            sr_no += 1

        return rows

    def _extract_village(self, filename: str) -> str:
        """
        Extract village name from filename.

        Args:
            filename: The PDF filename

        Returns:
            Village name or empty string
        """
        # Extract text before "S.No." or "Survey"
        parts = filename.split(" ")
        if len(parts) > 0:
            # Find the part before S.No. or Survey
            for i, part in enumerate(parts):
                if "S.No" in part or "Survey" in part.lower():
                    return " ".join(parts[:i]).replace(".pdf", "").strip()
        return filename.replace(".pdf", "").strip()

    def _extract_survey_no(self, data: Dict[str, Any]) -> str:
        """
        Extract survey number from extracted data.

        Args:
            data: Extracted data dictionary

        Returns:
            Survey number or empty string
        """
        # Try to find survey number in extracted fields
        for field in ["survey_no", "surveyno", "survey_number"]:
            if field in data and data[field]:
                return str(data[field])
        return ""

    def _get_status(self, confidence: float) -> str:
        """
        Determine extraction status based on confidence.

        Args:
            confidence: Confidence score (0-1)

        Returns:
            Status string (SUCCESS, PARTIAL, or FAILED)
        """
        if confidence >= 0.75:
            return "SUCCESS"
        elif confidence >= 0.5:
            return "PARTIAL"
        else:
            return "FAILED"
