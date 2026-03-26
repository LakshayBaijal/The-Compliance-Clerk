"""
Deterministic extractor for eChallan documents.
Uses regex patterns to extract structured data from traffic fines.
"""

import re
from typing import Optional, Dict, Tuple
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger
from src.schemas import EchallanData

logger = get_logger(__name__)


class EchallanExtractor:
    """Extracts data from eChallan documents using pattern matching."""
    
    def __init__(self):
        """Initialize with regex patterns for eChallan fields."""
        self.patterns = {
            "challan_number": [
                r'challan\s*(?:no\.?|number)\s*[:=]?\s*([A-Z0-9\-]+)',
                r'(?:ticket|challan)\s*#\s*([A-Z0-9\-]+)'
            ],
            "vehicle_reg_number": [
                r'(?:vehicle\s*)?(?:reg(?:istration)?|registration)\s*(?:no\.?|number)\s*[:=]?\s*([A-Z0-9\-]+)',
                r'reg\s*#\s*([A-Z0-9\-]+)',
                r'([A-Z]{2}\-\d{2}\-[A-Z]{2}\-\d{4})'  # Standard India format
            ],
            "violation_code": [
                r'violation\s*(?:code|section)\s*[:=]?\s*([A-Z0-9]+)',
                r'(?:code|section)\s*[:=]?\s*([A-Z0-9]{2,})'
            ],
            "violation_description": [
                r'violation\s*(?:desc|description)\s*[:=]?\s*([^\n]+)',
                r'(?:offence|violation)\s*[:=]?\s*([^\n]+)'
            ],
            "amount_due": [
                r'(?:amount|fine|penalty)\s*(?:due)?[:=]?\s*(?:(?:rs|inr|₹)\.?\s*)?(\d+(?:\.\d{2})?)',
                r'₹\s*(\d+(?:\.\d{2})?)',
                r'([0-9]+)\s*(?:rs|inr|rupees)'
            ],
            "payment_status": [
                r'(?:payment\s*)?status\s*[:=]?\s*(pending|paid|dispute[d]?)',
                r'status\s*[:=]?\s*(active|inactive|cleared|outstanding)'
            ],
            "payment_due_date": [
                r'(?:payment\s*)?(?:due\s*)?date\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'due\s*[:=]?\s*(\d{4}-\d{2}-\d{2})'
            ],
            "officer_id": [
                r'officer\s*(?:id|code)\s*[:=]?\s*([A-Z0-9\-]+)',
                r'(?:constable|officer)\s*#\s*([A-Z0-9\-]+)'
            ],
            "issuing_date": [
                r'(?:issued|issue)\s*(?:date|on)\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'(?:date|issued)\s*[:=]?\s*(\d{4}-\d{2}-\d{2})'
            ]
        }
    
    def _extract_field(self, text: str, field_name: str) -> Tuple[Optional[str], float]:
        """
        Extract a single field using its patterns.
        
        Args:
            text: Text to search in
            field_name: Name of field to extract
        
        Returns:
            Tuple of (extracted_value, confidence)
        """
        if field_name not in self.patterns:
            return None, 0.0
        
        for pattern in self.patterns[field_name]:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                confidence = 0.95 if len(pattern) < 50 else 0.85  # Simpler patterns = higher confidence
                logger.debug(f"Extracted {field_name}: {value} (confidence: {confidence})")
                return value, confidence
        
        return None, 0.0
    
    def extract(self, text: str) -> Dict:
        """
        Extract all eChallan fields from text.
        
        Args:
            text: Text to extract from
        
        Returns:
            Dictionary with extracted data and field confidences
        """
        logger.info("Starting eChallan extraction")
        
        # Extract all fields
        challan_number, conf_challan = self._extract_field(text, "challan_number")
        vehicle_reg, conf_vehicle = self._extract_field(text, "vehicle_reg_number")
        violation_code, conf_vcode = self._extract_field(text, "violation_code")
        violation_desc, conf_vdesc = self._extract_field(text, "violation_description")
        amount_due, conf_amount = self._extract_field(text, "amount_due")
        payment_status, conf_payment = self._extract_field(text, "payment_status")
        payment_due_date, conf_due_date = self._extract_field(text, "payment_due_date")
        officer_id, conf_officer = self._extract_field(text, "officer_id")
        issuing_date, conf_issue_date = self._extract_field(text, "issuing_date")
        
        # Calculate overall confidence
        all_confidences = [
            conf_challan, conf_vehicle, conf_vcode, conf_vdesc,
            conf_amount, conf_payment, conf_due_date, conf_officer, conf_issue_date
        ]
        extracted_count = sum(1 for c in all_confidences if c > 0)
        overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        # Convert amount to float if present
        amount_float = None
        if amount_due:
            try:
                amount_float = float(amount_due)
            except ValueError:
                pass
        
        # Create EchallanData object
        echallan_data = EchallanData(
            challan_number=challan_number,
            vehicle_reg_number=vehicle_reg,
            violation_code=violation_code,
            violation_description=violation_desc,
            amount_due=amount_float,
            amount_currency="INR" if amount_due else None,
            payment_status=payment_status,
            payment_due_date=payment_due_date,
            officer_id=officer_id,
            issuing_date=issuing_date
        )
        
        logger.info(f"eChallan extraction complete - confidence: {overall_confidence:.2f}")
        
        return {
            "data": echallan_data,
            "overall_confidence": overall_confidence,
            "extracted_fields": extracted_count,
            "total_fields": len(all_confidences),
            "field_confidences": {
                "challan_number": conf_challan,
                "vehicle_reg_number": conf_vehicle,
                "violation_code": conf_vcode,
                "violation_description": conf_vdesc,
                "amount_due": conf_amount,
                "payment_status": conf_payment,
                "payment_due_date": conf_due_date,
                "officer_id": conf_officer,
                "issuing_date": conf_issue_date
            }
        }


def extract_echallan(text: str) -> Dict:
    """
    Convenient function to extract eChallan data.
    
    Args:
        text: Text to extract from
    
    Returns:
        Dictionary with extraction results
    """
    extractor = EchallanExtractor()
    return extractor.extract(text)
