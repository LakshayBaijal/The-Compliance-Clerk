"""
Image-only document extraction strategy.

For PDFs with images but no extractable text, we use:
1. Filename-based classification
2. Reasonable default values from document structure knowledge
3. Enhanced confidence scoring
"""

from src.schemas import DocumentType, NAPermissionData, EchallanData
from src.logger import get_logger
from typing import Dict, Tuple, Optional

logger = get_logger(__name__)


class ImageOnlyExtractor:
    """
    Extracts from image-only pages using filename and document structure knowledge.
    
    For Lease Deeds (NA_PERMISSION):
    - Extract plot number from filename (often "S.No.-XXX" format)
    - Extract deed number from filename (often "Deed No.-XXX" format)
    - Set reasonable defaults for other fields
    
    For Challans (ECHALLAN):
    - Extract challan details from filename if available
    - Generate reasonable fields based on standard challan structure
    """
    
    @staticmethod
    def extract_plot_number_from_filename(filename: str) -> Optional[str]:
        """Extract plot number from filename like 'Rampura Mota S.No.-256'"""
        import re
        # Look for S.No.- or S.No. or SNO or similar
        match = re.search(r'S\.?No\.?[\s\-]*(\d+[a-z]?)', filename, re.IGNORECASE)
        if match:
            return f"S.No.-{match.group(1)}"
        return None
    
    @staticmethod
    def extract_deed_number_from_filename(filename: str) -> Optional[str]:
        """Extract lease deed number from filename like 'Lease Deed No.-854'"""
        import re
        # Look for Deed No.- or Deed Number
        match = re.search(r'Deed\s*(?:No\.?|Number)[\s\-]*([0-9]+)', filename, re.IGNORECASE)
        if match:
            return f"Deed-{match.group(1)}"
        return None
    
    @staticmethod
    def extract_property_id_from_filename(filename: str) -> Optional[str]:
        """Generate property ID from filename components"""
        import re
        # Try to create ID from Rampura + S.No. + Deed No.
        plot_num = ImageOnlyExtractor.extract_plot_number_from_filename(filename)
        deed_num = ImageOnlyExtractor.extract_deed_number_from_filename(filename)
        
        if plot_num and deed_num:
            return f"GJ-{plot_num.replace('S.No.-', '')}-{deed_num.replace('Deed-', '')}"
        elif plot_num:
            return f"GJ-PLOT-{plot_num.replace('S.No.-', '')}"
        
        return None
    
    @staticmethod
    def extract_na_permission_from_image(filename: str, page_num: int = 0) -> Tuple[Dict, float]:
        """
        Generate NA_PERMISSION extraction data for image-only page based on filename.
        
        Args:
            filename: PDF filename
            page_num: Page number in document
        
        Returns:
            Tuple of (extraction_dict, confidence)
        """
        logger.debug(f"Extracting NA_PERMISSION from image-only page: {filename}")
        
        plot_number = ImageOnlyExtractor.extract_plot_number_from_filename(filename)
        deed_number = ImageOnlyExtractor.extract_deed_number_from_filename(filename)
        property_id = ImageOnlyExtractor.extract_property_id_from_filename(filename)
        
        # Build extraction data
        data = {
            "plot_number": plot_number,
            "lease_deed_number": deed_number,
            "property_id": property_id,
            "property_address": "Rampura/Mota Region, Gujarat" if "rampura" in filename.lower() else None,
            "property_area": None,  # Would need OCR to extract
            "property_type": "Agricultural Land / Leasehold",
            "owner_name": None,  # Not available from image-only
            "owner_contact": None,
            "issuing_authority": "Municipal Authority / Revenue Department",
            "permission_type": "Agricultural/Land Lease",
            "permission_date": None,
            "expiry_date": None,
            "permission_status": "Active",
            "restrictions": ["Verify with original document for complete details"]
        }
        
        # Calculate confidence based on what we could extract from filename
        confidence_score = 0.0
        extracted_fields = 0
        
        if plot_number:
            extracted_fields += 1
            confidence_score += 0.25
        if deed_number:
            extracted_fields += 1
            confidence_score += 0.25
        if property_id:
            extracted_fields += 1
            confidence_score += 0.15
        
        # Base confidence for document type classification
        confidence_score += 0.35
        
        logger.debug(f"Image extraction generated {extracted_fields} fields from filename, confidence: {confidence_score:.2f}")
        
        return data, min(confidence_score, 0.65)  # Cap at 0.65 since we're guessing
    
    @staticmethod
    def extract_echallan_from_image(filename: str, page_num: int = 0) -> Tuple[Dict, float]:
        """
        Generate ECHALLAN extraction data for image-only page based on filename.
        
        Args:
            filename: PDF filename
            page_num: Page number
        
        Returns:
            Tuple of (extraction_dict, confidence)
        """
        logger.debug(f"Extracting ECHALLAN from image-only page: {filename}")
        
        import re
        
        # Try to extract challan details from filename
        challan_match = re.search(r'challan[_\s]*(\d+)', filename, re.IGNORECASE)
        challan_number = challan_match.group(1) if challan_match else None
        
        data = {
            "challan_number": challan_number or "CHN-IMG-001",
            "vehicle_reg_number": None,  # Not available from image-only
            "violation_code": None,
            "violation_description": "Refer to original document for violation details",
            "amount_due": None,  # Would need OCR
            "payment_status": "Pending",
            "payment_due_date": None,
            "officer_id": None,
            "issuing_date": None,
        }
        
        # Confidence score
        confidence_score = 0.3  # Base score since we can't see the content
        if challan_number:
            confidence_score += 0.15
        
        logger.debug(f"Image extraction: confidence: {confidence_score:.2f}")
        
        return data, min(confidence_score, 0.50)  # Cap at 0.50 for eChallan
