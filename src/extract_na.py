"""
Deterministic extractor for NA Permission/Lease documents.
Uses regex patterns to extract structured data from property permission documents.
"""

import re
from typing import Optional, Dict, List, Tuple
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger
from src.schemas import NAPermissionData

logger = get_logger(__name__)


class NAPermissionExtractor:
    """Extracts data from NA Permission/Lease documents using pattern matching."""
    
    def __init__(self):
        """Initialize with regex patterns for NA Permission fields."""
        self.patterns = {
            "property_id": [
                r'property\s*(?:id|code|number)\s*[:=]?\s*([A-Z0-9\-]+)',
                r'property\s*#\s*([A-Z0-9\-]+)'
            ],
            "plot_number": [
                r'plot\s*(?:no\.?|number|s\.?no\.?)\s*[:=]?\s*([A-Z0-9\-\.]+)',
                r'plot\s*#\s*([A-Z0-9\-\.]+)'
            ],
            "lease_deed_number": [
                r'(?:lease\s*)?deed\s*(?:no\.?|number)\s*[:=]?\s*([A-Z0-9\-]+)',
                r'deed\s*#\s*([A-Z0-9\-]+)'
            ],
            "property_address": [
                r'(?:address|location)\s*[:=]?\s*([^\n]+)',
                r'property\s*(?:address|location)\s*[:=]?\s*([^\n]+)'
            ],
            "property_area": [
                r'(?:area|size)\s*[:=]?\s*(\d+(?:\.\d{2})?)\s*(?:sq\.?ft|sqft)',
                r'(\d+(?:\.\d{2})?)\s*sq\.?ft'
            ],
            "property_type": [
                r'(?:property|land)\s*type\s*[:=]?\s*([^\n]+)',
                r'type\s*[:=]?\s*(residential|commercial|industrial|agricultural)'
            ],
            "owner_name": [
                r'owner\s*(?:name)?\s*[:=]?\s*([^\n]+)',
                r'(?:owner|proprieter)\s*[:=]?\s*([^\n]+)'
            ],
            "owner_contact": [
                r'(?:owner\s*)?(?:contact|phone|mobile|email)\s*[:=]?\s*([^\n]+)',
                r'(?:phone|mobile|email)\s*[:=]?\s*([^\n]+)'
            ],
            "issuing_authority": [
                r'(?:issuing|issued\s*by)\s*(?:authority|department)\s*[:=]?\s*([^\n]+)',
                r'authority\s*[:=]?\s*([^\n]+)'
            ],
            "permission_type": [
                r'permission\s*type\s*[:=]?\s*([^\n]+)',
                r'type\s*(?:of\s*)?permission\s*[:=]?\s*([^\n]+)'
            ],
            "permission_date": [
                r'(?:permission|issued)\s*(?:date|on)\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'issued\s*[:=]?\s*(\d{4}-\d{2}-\d{2})'
            ],
            "expiry_date": [
                r'(?:expiry|expiration|expires|valid\s*upto)\s*(?:date)?\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'expiry\s*[:=]?\s*(\d{4}-\d{2}-\d{2})'
            ],
            "permission_status": [
                r'(?:permission\s*)?status\s*[:=]?\s*(active|inactive|expired|revoked)',
                r'status\s*[:=]?\s*(active|inactive)'
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
                confidence = 0.95 if len(pattern) < 50 else 0.85
                logger.debug(f"Extracted {field_name}: {value} (confidence: {confidence})")
                return value, confidence
        
        return None, 0.0
    
    def _extract_restrictions(self, text: str) -> Tuple[List[str], float]:
        """
        Extract restrictions/conditions from text.
        
        Args:
            text: Text to search in
        
        Returns:
            Tuple of (list of restrictions, confidence)
        """
        restrictions = []
        
        # Look for restrictions/conditions sections
        patterns = [
            r'restrictions?\s*[:=]?\s*([^\n]+)',
            r'conditions?\s*[:=]?\s*([^\n]+)',
            r'terms?\s*[:=]?\s*([^\n]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            restrictions.extend(matches)
        
        confidence = 0.8 if restrictions else 0.0
        return restrictions, confidence
    
    def extract(self, text: str) -> Dict:
        """
        Extract all NA Permission fields from text.
        
        Args:
            text: Text to extract from
        
        Returns:
            Dictionary with extracted data and field confidences
        """
        logger.info("Starting NA Permission extraction")
        
        # Extract all fields
        property_id, conf_prop_id = self._extract_field(text, "property_id")
        plot_number, conf_plot = self._extract_field(text, "plot_number")
        lease_deed, conf_deed = self._extract_field(text, "lease_deed_number")
        address, conf_address = self._extract_field(text, "property_address")
        area, conf_area = self._extract_field(text, "property_area")
        prop_type, conf_type = self._extract_field(text, "property_type")
        owner, conf_owner = self._extract_field(text, "owner_name")
        contact, conf_contact = self._extract_field(text, "owner_contact")
        authority, conf_authority = self._extract_field(text, "issuing_authority")
        perm_type, conf_perm_type = self._extract_field(text, "permission_type")
        perm_date, conf_perm_date = self._extract_field(text, "permission_date")
        expiry, conf_expiry = self._extract_field(text, "expiry_date")
        status, conf_status = self._extract_field(text, "permission_status")
        restrictions, conf_restrictions = self._extract_restrictions(text)
        
        # Calculate overall confidence
        all_confidences = [
            conf_prop_id, conf_plot, conf_deed, conf_address, conf_area,
            conf_type, conf_owner, conf_contact, conf_authority, conf_perm_type,
            conf_perm_date, conf_expiry, conf_status, conf_restrictions
        ]
        extracted_count = sum(1 for c in all_confidences if c > 0)
        overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        # Convert area to float if present
        area_float = None
        if area:
            try:
                area_float = float(area)
            except ValueError:
                pass
        
        # Create NAPermissionData object
        na_data = NAPermissionData(
            property_id=property_id,
            plot_number=plot_number,
            lease_deed_number=lease_deed,
            property_address=address,
            property_area=area_float,
            property_area_unit="sq.ft" if area else None,
            property_type=prop_type,
            owner_name=owner,
            owner_contact=contact,
            issuing_authority=authority,
            permission_type=perm_type,
            permission_date=perm_date,
            expiry_date=expiry,
            permission_status=status,
            restrictions=restrictions if restrictions else None
        )
        
        logger.info(f"NA Permission extraction complete - confidence: {overall_confidence:.2f}")
        
        return {
            "data": na_data,
            "overall_confidence": overall_confidence,
            "extracted_fields": extracted_count,
            "total_fields": len(all_confidences),
            "field_confidences": {
                "property_id": conf_prop_id,
                "plot_number": conf_plot,
                "lease_deed_number": conf_deed,
                "property_address": conf_address,
                "property_area": conf_area,
                "property_type": conf_type,
                "owner_name": conf_owner,
                "owner_contact": conf_contact,
                "issuing_authority": conf_authority,
                "permission_type": conf_perm_type,
                "permission_date": conf_perm_date,
                "expiry_date": conf_expiry,
                "permission_status": conf_status
            }
        }


def extract_na_permission(text: str) -> Dict:
    """
    Convenient function to extract NA Permission data.
    
    Args:
        text: Text to extract from
    
    Returns:
        Dictionary with extraction results
    """
    extractor = NAPermissionExtractor()
    return extractor.extract(text)
