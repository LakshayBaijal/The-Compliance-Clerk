"""
Document classification module for The Compliance Clerk.
Routes PDF pages to appropriate extractors based on document type.
"""

import re
from typing import Optional, List, Dict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger
from src.schemas import DocumentType

logger = get_logger(__name__)


class DocumentClassifier:
    """Classifies PDF pages as eChallan, NA Permission, or Unknown."""
    
    # Keywords for eChallan detection
    ECHALLAN_KEYWORDS = [
        r'\bchallan\b', r'\bticket\b', r'\bfine\b', r'\bviolation\b',
        r'\btraffic\b', r'\boffence\b', r'\bvehicle\s*reg',
        r'\bregistration\s*number\b', r'\bamount\s*due\b',
        r'\bpayment\s*due\b', r'\bofficer\b', r'\bpolice\b',
        r'\bmotor\s*vehicles\b', r'\bspeed\b', r'\bviolated\b'
    ]
    
    # Keywords for NA Permission detection
    NA_PERMISSION_KEYWORDS = [
        r'\blease\b', r'\bpermission\b', r'\bproperty\b',
        r'\bplot\s*number\b', r'\bsurvey\s*number\b',
        r'\barea.*sq.*ft\b', r'\bowner\b', r'\btenant\b',
        r'\bauthority\b', r'\bmunicipality\b', r'\bcorporation\b',
        r'\bindenture\b', r'\bagreement\b', r'\bpermit\b',
        r'\bdeed\b', r'\bproperty\s*id\b'
    ]
    
    def __init__(self):
        """Initialize classifier with compiled regex patterns."""
        self.echallan_patterns = [
            re.compile(kw, re.IGNORECASE) for kw in self.ECHALLAN_KEYWORDS
        ]
        self.na_permission_patterns = [
            re.compile(kw, re.IGNORECASE) for kw in self.NA_PERMISSION_KEYWORDS
        ]
        logger.info("Initialized document classifier")
    
    def classify_text(self, text: str, page_num: int = 0) -> Dict:
        """
        Classify a page based on text content.
        
        Args:
            text: Extracted text from the page
            page_num: Page number for reference
        
        Returns:
            Dictionary with classification results
        """
        if not text or not text.strip():
            logger.debug(f"No text to classify on page {page_num}")
            return {
                "page_num": page_num,
                "document_type": DocumentType.UNKNOWN,
                "confidence": 0.0,
                "has_text": False,
                "classification_method": "no_text"
            }
        
        # Count keyword matches
        echallan_matches = sum(
            1 for pattern in self.echallan_patterns if pattern.search(text)
        )
        na_permission_matches = sum(
            1 for pattern in self.na_permission_patterns if pattern.search(text)
        )
        
        total_keywords_matched = echallan_matches + na_permission_matches
        
        if total_keywords_matched == 0:
            return {
                "page_num": page_num,
                "document_type": DocumentType.UNKNOWN,
                "confidence": 0.0,
                "has_text": True,
                "classification_method": "keyword_match"
            }
        
        # Determine document type and confidence
        if echallan_matches > na_permission_matches:
            confidence = min(echallan_matches / 5.0, 1.0)  # Normalize
            doc_type = DocumentType.ECHALLAN
        elif na_permission_matches > echallan_matches:
            confidence = min(na_permission_matches / 6.0, 1.0)  # Normalize
            doc_type = DocumentType.NA_PERMISSION
        else:
            # Equal matches - check specific patterns
            if any(pattern.search(text) for pattern in self.echallan_patterns[:3]):
                doc_type = DocumentType.ECHALLAN
            else:
                doc_type = DocumentType.NA_PERMISSION
            confidence = 0.5
        
        return {
            "page_num": page_num,
            "document_type": doc_type,
            "confidence": confidence,
            "has_text": True,
            "echallan_matches": echallan_matches,
            "na_permission_matches": na_permission_matches,
            "classification_method": "keyword_match"
        }
    
    def classify_with_structure(self, text: str, page_num: int = 0) -> Dict:
        """
        Classify using both text content and document structure.
        
        Args:
            text: Extracted text from the page
            page_num: Page number for reference
        
        Returns:
            Dictionary with improved classification results
        """
        # Start with text-based classification
        classification = self.classify_text(text, page_num)
        
        if classification["document_type"] == DocumentType.UNKNOWN:
            return classification
        
        # Look for structural patterns
        lines = text.split('\n')
        
        # Check if document looks like a form (multiple field patterns)
        if classification["document_type"] == DocumentType.ECHALLAN:
            # Check for challan-specific structure
            challan_patterns = [
                r'challan.*number',
                r'vehicle.*registration',
                r'violation.*code',
                r'amount.*due',
                r'payment.*status'
            ]
            structure_matches = sum(
                1 for pattern in challan_patterns 
                if any(re.search(pattern, line, re.IGNORECASE) for line in lines)
            )
            
            if structure_matches >= 3:
                # High confidence - looks like actual form
                classification["confidence"] = min(classification["confidence"] + 0.2, 1.0)
                classification["structure_matches"] = structure_matches
        
        elif classification["document_type"] == DocumentType.NA_PERMISSION:
            # Check for permission document structure
            permission_patterns = [
                r'property.*id|plot.*number',
                r'owner.*name|tenant.*name',
                r'issuing.*authority',
                r'permission.*date|expiry.*date',
                r'area.*sq'
            ]
            structure_matches = sum(
                1 for pattern in permission_patterns 
                if any(re.search(pattern, line, re.IGNORECASE) for line in lines)
            )
            
            if structure_matches >= 3:
                classification["confidence"] = min(classification["confidence"] + 0.2, 1.0)
                classification["structure_matches"] = structure_matches
        
        classification["classification_method"] = "structure_analysis"
        return classification
    
    def route_to_extractor(self, classification: Dict) -> str:
        """
        Determine which extractor should be used.
        
        Args:
            classification: Classification result dictionary
        
        Returns:
            Extractor module name to use
        """
        if classification["document_type"] == DocumentType.ECHALLAN:
            return "extract_echallan"
        elif classification["document_type"] == DocumentType.NA_PERMISSION:
            return "extract_na"
        else:
            return "fallback_ocr"


def classify_page(text: str, page_num: int = 0, use_structure: bool = True) -> Dict:
    """
    Classify a single page.
    
    Args:
        text: Extracted text from the page
        page_num: Page number
        use_structure: Whether to use structure analysis
    
    Returns:
        Classification result dictionary
    """
    classifier = DocumentClassifier()
    
    if use_structure:
        return classifier.classify_with_structure(text, page_num)
    else:
        return classifier.classify_text(text, page_num)


def classify_document(pages_content: List[Dict]) -> List[Dict]:
    """
    Classify all pages in a document.
    
    Args:
        pages_content: List of page content dictionaries from PDFIngestor
    
    Returns:
        List of classification results
    """
    classifier = DocumentClassifier()
    classifications = []
    
    for page_content in pages_content:
        text = page_content.get("text", "")
        page_num = page_content.get("page_num", 0)
        
        classification = classifier.classify_with_structure(text, page_num)
        classifications.append(classification)
    
    logger.info(f"Classified {len(classifications)} pages")
    return classifications


def get_extraction_routing(classifications: List[Dict]) -> Dict[str, List[int]]:
    """
    Get routing instructions for extraction.
    Groups page numbers by extractor type.
    
    Args:
        classifications: List of classification results
    
    Returns:
        Dictionary mapping extractor types to lists of page numbers
    """
    routing = {
        "extract_echallan": [],
        "extract_na": [],
        "fallback_ocr": []
    }
    
    for classification in classifications:
        if classification["confidence"] >= 0.7:
            # High confidence - use specific extractor
            if classification["document_type"] == DocumentType.ECHALLAN:
                routing["extract_echallan"].append(classification["page_num"])
            elif classification["document_type"] == DocumentType.NA_PERMISSION:
                routing["extract_na"].append(classification["page_num"])
        else:
            # Low confidence - use OCR fallback
            routing["fallback_ocr"].append(classification["page_num"])
    
    logger.info(f"Routing: {len(routing['extract_echallan'])} eChallan, "
                f"{len(routing['extract_na'])} NA Permission, "
                f"{len(routing['fallback_ocr'])} OCR fallback")
    
    return routing
