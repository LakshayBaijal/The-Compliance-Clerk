"""
Unit tests for document classification module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.classify import (
    DocumentClassifier, classify_page, classify_document,
    get_extraction_routing
)
from src.schemas import DocumentType


def test_classifier_initialization():
    """Test classifier initialization."""
    classifier = DocumentClassifier()
    assert classifier.echallan_patterns is not None
    assert classifier.na_permission_patterns is not None
    assert len(classifier.echallan_patterns) > 10
    assert len(classifier.na_permission_patterns) > 10
    print(f"[PASS] Classifier initialized with {len(classifier.echallan_patterns)} "
          f"echallan and {len(classifier.na_permission_patterns)} NA permission patterns")


def test_classify_echallan_text():
    """Test classification of eChallan text."""
    echallan_text = """
    TRAFFIC CHALLAN RECEIPT
    Challan Number: CH-2024-001
    Vehicle Registration: DL-01-AB-1234
    Violation Code: MV101
    Violation: Speeding in restricted zone
    Date: 2024-03-20
    Fine Amount: INR 500
    Payment Status: Pending
    Officer ID: TRF-2024-001
    """
    
    result = classify_page(echallan_text, page_num=0)
    assert result["document_type"] == DocumentType.ECHALLAN
    assert result["confidence"] > 0.5
    assert result["has_text"] is True
    print(f"[PASS] eChallan classification - confidence: {result['confidence']:.2f}")


def test_classify_na_permission_text():
    """Test classification of NA Permission text."""
    na_text = """
    LEASE PERMISSION DOCUMENT
    Property ID: PROP-2024-001
    Plot Number: A-1-2-3
    Address: 123 Main Street, New Delhi
    Owner Name: John Doe
    Area: 5000 sq.ft
    Permission Type: Residential Lease
    Issuing Authority: Municipal Corporation
    Issued Date: 2024-01-15
    Expiry Date: 2025-01-14
    Status: Active
    """
    
    result = classify_page(na_text, page_num=1)
    assert result["document_type"] == DocumentType.NA_PERMISSION
    assert result["confidence"] > 0.5
    assert result["has_text"] is True
    print(f"[PASS] NA Permission classification - confidence: {result['confidence']:.2f}")


def test_classify_unknown_text():
    """Test classification of unknown text."""
    unknown_text = "This is some random text that doesn't match any known document type."
    
    result = classify_page(unknown_text, page_num=2)
    assert result["document_type"] == DocumentType.UNKNOWN
    assert result["confidence"] == 0.0
    print("[PASS] Unknown text classified correctly")


def test_classify_empty_text():
    """Test classification of empty text."""
    result = classify_page("", page_num=3)
    assert result["document_type"] == DocumentType.UNKNOWN
    assert result["has_text"] is False
    print("[PASS] Empty text handled correctly")


def test_route_to_extractor():
    """Test routing logic."""
    classifier = DocumentClassifier()
    
    # Test eChallan routing
    echallan_class = {
        "page_num": 0,
        "document_type": DocumentType.ECHALLAN,
        "confidence": 0.9
    }
    router = classifier.route_to_extractor(echallan_class)
    assert router == "extract_echallan"
    
    # Test NA Permission routing
    na_class = {
        "page_num": 1,
        "document_type": DocumentType.NA_PERMISSION,
        "confidence": 0.85
    }
    router = classifier.route_to_extractor(na_class)
    assert router == "extract_na"
    
    # Test Unknown routing
    unknown_class = {
        "page_num": 2,
        "document_type": DocumentType.UNKNOWN,
        "confidence": 0.0
    }
    router = classifier.route_to_extractor(unknown_class)
    assert router == "fallback_ocr"
    
    print("[PASS] Routing logic works correctly")


def test_classify_document():
    """Test classifying multiple pages."""
    pages_content = [
        {
            "page_num": 0,
            "text": "CHALLAN CH-001 VIOLATION TRAFFIC OFFICER PAYMENT DUE"
        },
        {
            "page_num": 1,
            "text": "LEASE PROPERTY OWNER AREA 5000 SQ FT PERMISSION AUTHORITY"
        }
    ]
    
    classifications = classify_document(pages_content)
    assert len(classifications) == 2
    assert classifications[0]["page_num"] == 0
    assert classifications[1]["page_num"] == 1
    print("[PASS] Multiple pages classified")


def test_get_extraction_routing():
    """Test extraction routing."""
    classifications = [
        {
            "page_num": 0,
            "document_type": DocumentType.ECHALLAN,
            "confidence": 0.9
        },
        {
            "page_num": 1,
            "document_type": DocumentType.NA_PERMISSION,
            "confidence": 0.85
        },
        {
            "page_num": 2,
            "document_type": DocumentType.UNKNOWN,
            "confidence": 0.3  # Low confidence
        }
    ]
    
    routing = get_extraction_routing(classifications)
    assert 0 in routing["extract_echallan"]
    assert 1 in routing["extract_na"]
    assert 2 in routing["fallback_ocr"]
    print("[PASS] Extraction routing works")


def test_structure_analysis():
    """Test that structure analysis improves confidence."""
    structured_text = """
    Challan Number: CH-2024-001
    Vehicle Registration Number: DL-01-AB-1234
    Violation Code: MV101
    Amount Due: 500
    Payment Status: Pending
    """
    
    result = classify_page(structured_text, page_num=0, use_structure=True)
    assert result["document_type"] == DocumentType.ECHALLAN
    assert result["confidence"] > 0.7
    assert result["classification_method"] == "structure_analysis"
    print(f"[PASS] Structure analysis improved confidence to {result['confidence']:.2f}")


def test_confidence_threshold():
    """Test confidence-based routing."""
    # High confidence
    high_conf = {
        "page_num": 0,
        "document_type": DocumentType.ECHALLAN,
        "confidence": 0.8
    }
    
    # Low confidence
    low_conf = {
        "page_num": 1,
        "document_type": DocumentType.ECHALLAN,
        "confidence": 0.6
    }
    
    routing = get_extraction_routing([high_conf, low_conf])
    assert 0 in routing["extract_echallan"]  # High confidence
    assert 1 in routing["fallback_ocr"]  # Low confidence (< 0.7)
    print("[PASS] Confidence threshold routing works")


if __name__ == "__main__":
    print("Running document classification tests...\n")
    test_classifier_initialization()
    test_classify_echallan_text()
    test_classify_na_permission_text()
    test_classify_unknown_text()
    test_classify_empty_text()
    test_route_to_extractor()
    test_classify_document()
    test_get_extraction_routing()
    test_structure_analysis()
    test_confidence_threshold()
    print("\n[SUCCESS] All classification tests passed!")
