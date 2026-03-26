"""
Unit tests for Pydantic schemas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schemas import (
    DocumentType, EchallanData, NAPermissionData,
    ExtractionResult, BatchResult
)


def test_document_type_enum():
    """Test document type enumeration."""
    assert DocumentType.ECHALLAN.value == "eChallan"
    assert DocumentType.NA_PERMISSION.value == "NA/Lease Permission"
    print("[PASS] Document type enum correct")


def test_echallan_data_creation():
    """Test creating eChallan data."""
    challan = EchallanData(
        challan_number="CH-2024-001",
        vehicle_reg_number="DL-01-AB-1234",
        violation_code="MV101",
        violation_description="Speeding",
        amount_due=500.0,
        amount_currency="INR",
        payment_status="pending"
    )
    
    assert challan.challan_number == "CH-2024-001"
    assert challan.vehicle_reg_number == "DL-01-AB-1234"
    assert challan.amount_due == 500.0
    print("[PASS] eChallan data creation works")


def test_na_permission_data_creation():
    """Test creating NA Permission data."""
    permission = NAPermissionData(
        property_id="PROP-001",
        plot_number="A-1-2-3",
        property_address="123 Main Street",
        property_area=5000.0,
        property_area_unit="sq.ft",
        owner_name="John Doe",
        permission_status="active"
    )
    
    assert permission.property_id == "PROP-001"
    assert permission.property_area == 5000.0
    print("[PASS] NA Permission data creation works")


def test_extraction_result_creation():
    """Test creating extraction result."""
    result = ExtractionResult(
        file_name="test.pdf",
        page_num=1,
        document_type=DocumentType.ECHALLAN,
        echallan_data=EchallanData(
            challan_number="CH-001",
            amount_due=500.0
        ),
        confidence=0.95,
        is_valid=True
    )
    
    assert result.file_name == "test.pdf"
    assert result.confidence == 0.95
    assert result.document_type == DocumentType.ECHALLAN
    print("[PASS] Extraction result creation works")


def test_batch_result_creation():
    """Test creating batch result."""
    batch = BatchResult(
        total_files=2,
        total_pages=10,
        successful_extractions=9,
        failed_extractions=1,
        echallan_count=7,
        na_permission_count=2
    )
    
    assert batch.total_pages == 10
    assert batch.success_rate == 90.0
    print("[PASS] Batch result creation works")


def test_schema_json_serialization():
    """Test JSON serialization."""
    result = ExtractionResult(
        file_name="test.pdf",
        page_num=1,
        document_type=DocumentType.ECHALLAN,
        echallan_data=EchallanData(challan_number="CH-001"),
        confidence=0.95
    )
    
    json_str = result.model_dump_json()
    assert "test.pdf" in json_str
    assert "CH-001" in json_str
    print("[PASS] JSON serialization works")


def test_schema_optional_fields():
    """Test optional fields in schemas."""
    # All fields optional
    challan = EchallanData()
    assert challan.challan_number is None
    
    # Can set some fields
    challan = EchallanData(challan_number="CH-001")
    assert challan.challan_number == "CH-001"
    assert challan.amount_due is None
    print("[PASS] Optional fields work correctly")


if __name__ == "__main__":
    print("Running schema tests...\n")
    test_document_type_enum()
    test_echallan_data_creation()
    test_na_permission_data_creation()
    test_extraction_result_creation()
    test_batch_result_creation()
    test_schema_json_serialization()
    test_schema_optional_fields()
    print("\n[SUCCESS] All schema tests passed!")
