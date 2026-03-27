"""
Tests for Validation module covering normalization, schema validation, cross-field rules.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validate import Validator
from src.schemas import DocumentType


def test_normalize_amount_rupees():
    """Test amount normalization with rupee symbols."""
    print("Running Validation tests...\n")

    validator = Validator()
    amount, currency = validator.normalize_amount("₹1000")
    assert amount == 1000.0
    assert currency == "INR"
    print("[PASS] Amount normalization: ₹1000 → 1000.0 INR")


def test_normalize_amount_with_code():
    """Test amount normalization with currency code."""
    validator = Validator()
    amount, currency = validator.normalize_amount("INR 2500.50")
    assert amount == 2500.50
    assert currency == "INR"
    print("[PASS] Amount normalization: INR 2500.50 → 2500.50 INR")


def test_normalize_amount_invalid():
    """Test amount normalization with invalid input."""
    validator = Validator()
    amount, currency = validator.normalize_amount("invalid")
    assert amount is None
    assert currency is None
    print("[PASS] Invalid amount returns None gracefully")


def test_normalize_area_sqft():
    """Test area normalization with square feet."""
    validator = Validator()
    area, unit = validator.normalize_area("5000 sq.ft")
    assert area == 5000.0
    assert unit == "sq.ft"
    print("[PASS] Area normalization: 5000 sq.ft → 5000.0 sq.ft")


def test_normalize_area_decimal():
    """Test area normalization with decimal value."""
    validator = Validator()
    area, unit = validator.normalize_area("2.5 acres")
    assert area == 2.5
    assert unit == "acres"
    print("[PASS] Area normalization: 2.5 acres → 2.5 acres")


def test_normalize_area_invalid():
    """Test area normalization with invalid input."""
    validator = Validator()
    area, unit = validator.normalize_area("no_number_here")
    assert area is None
    print("[PASS] Invalid area returns None gracefully")


def test_normalize_date_iso():
    """Test date normalization with ISO format."""
    validator = Validator()
    normalized = validator.normalize_date("2026-03-27")
    assert normalized == "2026-03-27"
    print("[PASS] Date normalization: 2026-03-27 → 2026-03-27 (ISO)")


def test_normalize_date_ddmmyyyy():
    """Test date normalization with DD/MM/YYYY format."""
    validator = Validator()
    normalized = validator.normalize_date("27/03/2026")
    assert normalized == "2026-03-27"
    print("[PASS] Date normalization: 27/03/2026 → 2026-03-27")


def test_normalize_date_with_month_name():
    """Test date normalization with month name."""
    validator = Validator()
    normalized = validator.normalize_date("27-Mar-2026")
    assert normalized == "2026-03-27"
    print("[PASS] Date normalization: 27-Mar-2026 → 2026-03-27")


def test_normalize_date_invalid():
    """Test date normalization with invalid input."""
    validator = Validator()
    normalized = validator.normalize_date("invalid_date")
    assert normalized is None
    print("[PASS] Invalid date returns None gracefully")


def test_normalize_phone():
    """Test phone normalization."""
    validator = Validator()
    phone = validator.normalize_phone("91-9876-543210")
    assert phone == "9876543210"
    assert len(phone) == 10
    print("[PASS] Phone normalization: 91-9876-543210 → 9876543210")


def test_normalize_phone_short():
    """Test phone normalization with short number."""
    validator = Validator()
    phone = validator.normalize_phone("12345")
    assert phone is None
    print("[PASS] Short phone returns None")


def test_validate_echallan_valid():
    """Test eChallan validation with complete valid data."""
    validator = Validator()
    data = {
        "challan_number": "CH001",
        "vehicle_reg_number": "MH-02-AB-1234",
        "violation_code": "V01",
        "amount_due": "₹2000",
        "payment_status": "pending",
        "issuing_date": "2026-01-15",
        "payment_due_date": "2026-02-15",
    }
    validated, confidence_adj, issues = validator.validate_echallan(data)
    assert len(issues) == 0
    assert confidence_adj == 0.0
    assert validated.challan_number == "CH001"
    print("[PASS] Valid eChallan validates with 0 issues")


def test_validate_echallan_with_normalization():
    """Test eChallan validation with field normalization."""
    validator = Validator()
    data = {
        "challan_number": "CH002",
        "vehicle_reg_number": "MH-02-AB-5678",
        "amount_due": "₹3500.50",
        "issuing_date": "15/01/2026",
        "payment_due_date": "15/02/2026",
    }
    validated, confidence_adj, issues = validator.validate_echallan(data)
    assert len(issues) == 0
    assert validated.amount_due == 3500.50
    print("[PASS] eChallan normalized: rupee symbol stripped, date ISO formatted")


def test_validate_echallan_date_logic_error():
    """Test eChallan validation with illogical date order."""
    validator = Validator()
    data = {
        "challan_number": "CH003",
        "vehicle_reg_number": "MH-02-AB-9999",
        "issuing_date": "2026-02-15",
        "payment_due_date": "2026-01-15",  # Before issuing date!
    }
    validated, confidence_adj, issues = validator.validate_echallan(data)
    assert len(issues) > 0
    assert any("payment_due_date" in issue for issue in issues)
    assert confidence_adj < 0.0
    print("[PASS] eChallan rejects illogical date order, confidence reduced")


def test_validate_echallan_invalid_vehicle_format():
    """Test eChallan validation with invalid vehicle registration format."""
    validator = Validator()
    data = {
        "challan_number": "CH004",
        "vehicle_reg_number": "INVALID_REG",  # Wrong format
        "amount_due": "₹1000",
    }
    validated, confidence_adj, issues = validator.validate_echallan(data)
    assert len(issues) > 0
    assert any("vehicle_reg_number" in issue for issue in issues)
    print("[PASS] eChallan rejects invalid vehicle registration format")


def test_validate_na_permission_valid():
    """Test NA Permission validation with complete valid data."""
    validator = Validator()
    data = {
        "property_id": "PROP001",
        "plot_number": "123",
        "owner_name": "John Doe",
        "property_area": 5000,
        "permission_date": "2024-01-01",
        "expiry_date": "2026-01-01",
        "authority": "Municipal Authority",
        "restrictions": ["No commercial use", "Residential only"],
    }
    validated, confidence_adj, issues = validator.validate_na_permission(data)
    assert len(issues) == 0
    assert confidence_adj == 0.0
    assert validated.property_area == 5000.0
    print("[PASS] Valid NA Permission validates with 0 issues")


def test_validate_na_permission_with_normalization():
    """Test NA Permission validation with field normalization."""
    validator = Validator()
    data = {
        "property_id": "PROP002",
        "property_area": "2.5 acres",
        "permission_date": "01/01/2024",
        "expiry_date": "01/01/2026",
        "owner_contact": "91-9876543210",
    }
    validated, confidence_adj, issues = validator.validate_na_permission(data)
    assert len(issues) == 0
    assert validated.property_area == 2.5
    assert validated.owner_contact == "9876543210"
    print("[PASS] NA Permission normalized: area, dates, phone formatted")


def test_validate_na_permission_date_logic_error():
    """Test NA Permission validation with illogical expiry date."""
    validator = Validator()
    data = {
        "property_id": "PROP003",
        "permission_date": "2026-01-01",
        "expiry_date": "2025-01-01",  # Before permission date!
    }
    validated, confidence_adj, issues = validator.validate_na_permission(data)
    assert len(issues) > 0
    assert any("expiry_date" in issue for issue in issues)
    assert confidence_adj < 0.0
    print("[PASS] NA Permission rejects illogical date order, confidence reduced")


def test_validate_na_permission_restrictions_conversion():
    """Test NA Permission converts single restriction to list."""
    validator = Validator()
    data = {
        "property_id": "PROP004",
        "restrictions": "No commercial use",  # String, should become list
    }
    validated, confidence_adj, issues = validator.validate_na_permission(data)
    assert isinstance(validated.restrictions, list)
    print("[PASS] NA Permission converts single restriction string to list")


def test_validate_batch_echallan():
    """Test batch validation for eChallan documents."""
    validator = Validator()
    results = [
        {
            "echallan_data": {
                "challan_number": "CH101",
                "vehicle_reg_number": "MH-02-AB-1111",
                "amount_due": "₹1500",
            }
        },
        {
            "echallan_data": {
                "challan_number": "CH102",
                "vehicle_reg_number": "INVALID",
                "amount_due": "₹2000",
            }
        },
        {
            "echallan_data": {
                "challan_number": "CH103",
                "vehicle_reg_number": "MH-02-AB-3333",
                "amount_due": "invalid_amount",
            }
        },
    ]

    validated_results, stats = validator.validate_batch(
        results, DocumentType.ECHALLAN
    )

    assert stats["total"] == 3
    assert stats["validated"] == 3
    assert stats["with_issues"] >= 2  # Second and third have issues
    print(
        f"[PASS] Batch validation: {stats['total']} total, {stats['validated']} validated, "
        f"{stats['with_issues']} with issues, {stats['total_issues']} total issues"
    )


def test_validate_batch_na_permission():
    """Test batch validation for NA Permission documents."""
    validator = Validator()
    results = [
        {
            "na_data": {
                "property_id": "PROP201",
                "area": "4000 sq.ft",
                "permission_date": "2024-01-01",
                "expiry_date": "2026-01-01",
            }
        },
        {
            "na_data": {
                "property_id": "PROP202",
                "area": "invalid_area",
                "permission_date": "2026-01-01",
                "expiry_date": "2024-01-01",  # Illogical
            }
        },
    ]

    validated_results, stats = validator.validate_batch(
        results, DocumentType.NA_PERMISSION
    )

    assert stats["total"] == 2
    assert stats["validated"] == 2
    assert stats["with_issues"] >= 1  # Second has issues
    print(
        f"[PASS] Batch NA validation: {stats['total']} total, {stats['with_issues']} with issues"
    )


def test_confidence_adjustment_accumulation():
    """Test that confidence adjustments accumulate for multiple issues."""
    validator = Validator()
    data = {
        "challan_number": "CH999",
        "vehicle_reg_number": "INVALID_FORMAT",
        "amount_due": "garbage_amount",
        "issuing_date": "not_a_date",
        "payment_due_date": "also_not_a_date",
    }
    validated, confidence_adj, issues = validator.validate_echallan(data)
    assert len(issues) >= 3  # Multiple normalization failures
    assert confidence_adj < -0.20  # Significant confidence reduction
    print(f"[PASS] Multiple issues accumulate: {len(issues)} issues, "
          f"{confidence_adj:.2f} confidence adjustment")


if __name__ == "__main__":
    test_normalize_amount_rupees()
    test_normalize_amount_with_code()
    test_normalize_amount_invalid()
    test_normalize_area_sqft()
    test_normalize_area_decimal()
    test_normalize_area_invalid()
    test_normalize_date_iso()
    test_normalize_date_ddmmyyyy()
    test_normalize_date_with_month_name()
    test_normalize_date_invalid()
    test_normalize_phone()
    test_normalize_phone_short()
    test_validate_echallan_valid()
    test_validate_echallan_with_normalization()
    test_validate_echallan_date_logic_error()
    test_validate_echallan_invalid_vehicle_format()
    test_validate_na_permission_valid()
    test_validate_na_permission_with_normalization()
    test_validate_na_permission_date_logic_error()
    test_validate_na_permission_restrictions_conversion()
    test_validate_batch_echallan()
    test_validate_batch_na_permission()
    test_confidence_adjustment_accumulation()

    print("\n[SUCCESS] All validation tests passed!")
