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
        # These patterns are designed to work with OCR'd text (imperfect matches)
        self.patterns = {
            "challan_number": [
                r'challan\s*(?:no\.?|num?ber|no\.?)\s*[:=]?\s*([A-Z0-9\-/]+)',
                r'(?:ticket|challan|ref)\s*#?\s*[:=]?\s*([A-Z0-9\-/]{4,})',
                r'(?:citation|reference|ticket)\s*(?:no\.?)\s*[:=]?\s*([A-Z0-9\-/]+)',
                r'^(?:challan|ticket|citation)\s*(?:no\.?|#)\s*[:=]?\s*([A-Z0-9\-/]+)',
            ],
            "vehicle_reg_number": [
                r'(?:vehicle\s*)?(?:reg(?:istration)?|registration|plate|number)\s*(?:no\.?|num?ber)\s*[:=]?\s*([A-Z0-9\-/]+)',
                r'(?:registration|reg)\b\s*(?:no\.?|num?ber|#)?\s*[:=]?\s*([A-Z0-9\-/]*\d[A-Z0-9\-/]*)',
                r'([A-Z]{2}\s*[-/]?\s*\d{2}\s*[-/]?\s*[A-Z]{2}\s*[-/]?\s*\d{4})',  # India format with spaces
                r'(?:vehicle\s*)?(?:no\.?|number)\s*[:=]?\s*([A-Z0-9\-/]+)',
            ],
            "violation_code": [
                r'(?:violation|offence|section|code)\s*(?:code|section|no\.?|num?ber)?\s*[:=]?\s*([A-Z0-9\-/]+)',
                r'(?:motor\s*)?(?:vehicles\s*)?(?:act|rule).*?(?:section|sec\.?)\s*(\d+)',
                r'^(?:code|section)\s*[:=]?\s*([A-Z0-9]{2,})',
            ],
            "violation_description": [
                r'(?:violation|offence|description|reason|fine)\s*(?:desc|description)?\s*[:=]?\s*([^\n:]+)',
                r'(?:offence|violation)\s*[:=]?\s*([^\n:]+)',
                r'(?:reason|description)\s*[:=]?\s*([^\n:]+)',
                r'(?:over?-?speed|jump.*?red|no.*?helmet|drunk.*?drive|wrong.*?lane)',  # Common violations
            ],
            "amount_due": [
                r'(?:amount|fine|penalty|fee)\s*(?:due)?[:=]?\s*(?:(?:rs|inr|₹)\.?\s*)?(\d+(?:\.\d{2})?)',
                r'₹\s*(\d+(?:\.\d{2})?)',
                r'(?:rupees?|rs|inr)\s*(?:[:=])?\s*(\d+(?:\.\d{2})?)',
                r'(?:total|amount|fine)\s*(?:is|:)?\s*(?:rs|inr|₹)?\s*(\d+(?:\.\d{2})?)',
            ],
            "payment_status": [
                r'(?:payment\s*)?status\s*[:=]?\s*(pending|paid|dispute[d]?|outstanding|cleared)',
                r'(?:status|payment)\s*[:=]?\s*(active|inactive|cleared|paid|pending)',
            ],
            "payment_due_date": [
                r'(?:payment\s*)?(?:due|deadline)\s*(?:date|by)?\s*[:=]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})',
                r'(?:on|by|date)\s*[:=]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})',
                r'(\d{4}[-/\.]\d{2}[-/\.]\d{2})',
            ],
            "officer_id": [
                r'(?:officer|constable|badge|id)\s*(?:id|code|#|no\.?)?\s*[:=]?\s*([A-Z0-9\-/]+)',
                r'(?:issued\s*)?by\s*(?:officer|constable)\s*(?:id|#|no\.?)?\s*[:=]?\s*([A-Z0-9\-/]+)',
            ],
            "issuing_date": [
                r'(?:issued|issue|dated|on)\s*(?:date|on)?\s*[:=]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})',
                r'(?:date|issued)\s*[:=]?\s*(\d{4}[-/\.]\d{2}[-/\.]\d{2})',
                r'^(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})',  # Start of line
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
        
        for idx, pattern in enumerate(self.patterns[field_name]):
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                
                # Confidence decreases with pattern index (earlier patterns are more reliable)
                pattern_confidence = 0.95 - (idx * 0.1)
                
                # Reduce confidence based on value quality
                if not value or len(value) < 2:
                    pattern_confidence *= 0.5
                elif len(value) > 100:
                    pattern_confidence *= 0.7  # Long values are less reliable
                
                logger.debug(f"Extracted {field_name}: {value} (confidence: {pattern_confidence:.2f})")
                return value, pattern_confidence
        
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
        
        # Weight fields by importance: core fields (challan, vehicle, violation, amount) > secondary
        field_scores = {
            "challan_number": (conf_challan, 0.20),      # Critical
            "vehicle_reg_number": (conf_vehicle, 0.20),  # Critical
            "violation_code": (conf_vcode, 0.15),        # Important
            "violation_description": (conf_vdesc, 0.15), # Important
            "amount_due": (conf_amount, 0.15),           # Important
            "payment_status": (conf_payment, 0.05),      # Secondary
            "payment_due_date": (conf_due_date, 0.05),   # Secondary
            "officer_id": (conf_officer, 0.03),          # Optional
            "issuing_date": (conf_issue_date, 0.02)      # Optional
        }
        
        # Calculate weighted confidence
        weighted_sum = sum(score * weight for score, weight in field_scores.values())
        overall_confidence = weighted_sum
        
        # Boost if critical fields are present
        critical_count = (1 if challan_number else 0) + (1 if vehicle_reg else 0)
        if critical_count == 2:
            overall_confidence = min(1.0, overall_confidence + 0.15)
        elif critical_count == 0:
            overall_confidence *= 0.4  # Penalize missing critical fields
        
        overall_confidence = max(0.0, min(1.0, overall_confidence))
        
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
            "extracted_fields": sum(1 for v in [challan_number, vehicle_reg, violation_code, 
                                               violation_desc, amount_due, payment_status,
                                               payment_due_date, officer_id, issuing_date] if v),
            "total_fields": 9,
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
