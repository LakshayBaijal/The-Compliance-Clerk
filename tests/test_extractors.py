"""
Unit tests for deterministic extractors.
Tests eChallan and NA Permission extraction.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extract_echallan import extract_echallan
from src.extract_na import extract_na_permission


# Sample eChallan text
ECHALLAN_SAMPLE = """
TRAFFIC CHALLAN RECEIPT
Challan Number: CH-2024-001
Vehicle Registration Number: DL-01-AB-1234
Violation Code: MV101
Violation Description: Speeding in restricted zone
Date of Violation: 15-03-2024
Fine Amount: INR 500
Payment Status: Pending
Payment Due Date: 30-03-2024
Officer ID: TRF-2024-001
Issued Date: 16-03-2024
"""

# Sample NA Permission text
NA_PERMISSION_SAMPLE = """
LEASE PERMISSION DOCUMENT
Property ID: PROP-2024-001
Plot Number: A-1-2-3
Lease Deed Number: LD-2024-001
Address: 123 Main Street, New Delhi
Property Area: 5000 sq.ft
Property Type: Residential
Owner Name: John Doe
Owner Contact: 9876543210
Issuing Authority: Municipal Corporation
Permission Type: Residential Lease
Permission Date: 15-01-2024
Expiry Date: 14-01-2025
Permission Status: Active
Restrictions: No commercial use, No alteration without permission
"""


def test_echallan_extraction_basic():
    """Test basic eChallan field extraction."""
    result = extract_echallan(ECHALLAN_SAMPLE)
    
    assert result["data"].challan_number == "CH-2024-001"
    assert result["data"].vehicle_reg_number == "DL-01-AB-1234"
    assert result["overall_confidence"] > 0.7
    print("[PASS] eChallan basic extraction works")


def test_echallan_extraction_fields():
    """Test all eChallan fields extracted."""
    result = extract_echallan(ECHALLAN_SAMPLE)
    
    # Check key fields
    assert result["data"].challan_number is not None
    assert result["data"].vehicle_reg_number is not None
    assert result["data"].violation_code == "MV101"
    assert result["data"].amount_due == 500.0
    assert result["data"].payment_status is not None
    
    print(f"[PASS] eChallan fields extracted - "
          f"{result['extracted_fields']}/{result['total_fields']} fields")


def test_echallan_confidence():
    """Test eChallan confidence scoring."""
    result = extract_echallan(ECHALLAN_SAMPLE)
    
    assert 0 <= result["overall_confidence"] <= 1
    assert result["overall_confidence"] > 0.6
    
    # Check field confidences
    for field, conf in result["field_confidences"].items():
        assert 0 <= conf <= 1
    
    print(f"[PASS] eChallan confidence: {result['overall_confidence']:.2f}")


def test_echallan_empty_text():
    """Test eChallan extraction on empty text."""
    result = extract_echallan("")
    
    assert result["data"].challan_number is None
    assert result["overall_confidence"] == 0.0
    print("[PASS] eChallan handles empty text")


def test_na_permission_extraction_basic():
    """Test basic NA Permission field extraction."""
    result = extract_na_permission(NA_PERMISSION_SAMPLE)
    
    assert result["data"].property_id == "PROP-2024-001"
    assert result["data"].plot_number == "A-1-2-3"
    assert result["overall_confidence"] > 0.7
    print("[PASS] NA Permission basic extraction works")


def test_na_permission_extraction_fields():
    """Test all NA Permission fields extracted."""
    result = extract_na_permission(NA_PERMISSION_SAMPLE)
    
    # Check key fields
    assert result["data"].property_id is not None
    assert result["data"].plot_number is not None
    assert result["data"].property_area == 5000.0
    assert result["data"].owner_name == "John Doe"
    assert result["data"].permission_status is not None
    
    print(f"[PASS] NA Permission fields extracted - "
          f"{result['extracted_fields']}/{result['total_fields']} fields")


def test_na_permission_restrictions():
    """Test NA Permission restrictions extraction."""
    result = extract_na_permission(NA_PERMISSION_SAMPLE)
    
    assert result["data"].restrictions is not None
    assert len(result["data"].restrictions) > 0
    print(f"[PASS] NA Permission restrictions extracted: {len(result['data'].restrictions)} items")


def test_na_permission_confidence():
    """Test NA Permission confidence scoring."""
    result = extract_na_permission(NA_PERMISSION_SAMPLE)
    
    assert 0 <= result["overall_confidence"] <= 1
    assert result["overall_confidence"] > 0.6
    
    # Check field confidences
    for field, conf in result["field_confidences"].items():
        assert 0 <= conf <= 1
    
    print(f"[PASS] NA Permission confidence: {result['overall_confidence']:.2f}")


def test_na_permission_empty_text():
    """Test NA Permission extraction on empty text."""
    result = extract_na_permission("")
    
    assert result["data"].property_id is None
    assert result["overall_confidence"] == 0.0
    print("[PASS] NA Permission handles empty text")


def test_echallan_partial_data():
    """Test eChallan extraction with partial data."""
    partial_text = """
    Challan Number: CH-2024-002
    Vehicle Registration: HR-26-AB-5678
    """
    
    result = extract_echallan(partial_text)
    
    assert result["data"].challan_number == "CH-2024-002"
    assert result["data"].vehicle_reg_number == "HR-26-AB-5678"
    # Other fields should be None
    assert result["data"].amount_due is None
    print("[PASS] eChallan partial data handled correctly")


def test_na_permission_partial_data():
    """Test NA Permission extraction with partial data."""
    partial_text = """
    Property ID: PROP-123
    Owner Name: Jane Smith
    """
    
    result = extract_na_permission(partial_text)
    
    assert result["data"].property_id == "PROP-123"
    assert result["data"].owner_name == "Jane Smith"
    # Other fields should be None
    assert result["data"].plot_number is None
    print("[PASS] NA Permission partial data handled correctly")


if __name__ == "__main__":
    print("Running deterministic extractor tests...\n")
    
    print("--- eChallan Tests ---")
    test_echallan_extraction_basic()
    test_echallan_extraction_fields()
    test_echallan_confidence()
    test_echallan_empty_text()
    test_echallan_partial_data()
    
    print("\n--- NA Permission Tests ---")
    test_na_permission_extraction_basic()
    test_na_permission_extraction_fields()
    test_na_permission_restrictions()
    test_na_permission_confidence()
    test_na_permission_empty_text()
    test_na_permission_partial_data()
    
    print("\n[SUCCESS] All deterministic extractor tests passed!")
