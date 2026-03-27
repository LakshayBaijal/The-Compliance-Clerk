"""
Validation and normalization module for extracted document data.

Handles:
- Field normalization (currency, area units, date formats)
- Schema validation against Pydantic models
- Cross-field validation rules
- Missing field handling
"""

import re
import logging
from typing import Dict, Any, Tuple, List
from datetime import datetime
from src.schemas import (
    DocumentType,
    EchallanData,
    NAPermissionData,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


class Validator:
    """Validates and normalizes extracted document fields."""

    # Confidence reduction for validation failures
    VALIDATION_PENALTY = 0.10  # Reduce confidence by 10% per validation issue

    @staticmethod
    def normalize_amount(amount_str: str) -> Tuple[float, str]:
        """
        Normalize currency amount to float and extract currency.

        Args:
            amount_str: String like "₹1000", "Rs. 500", "INR 2000.50"

        Returns:
            Tuple of (float_amount, currency_code)
        """
        if not amount_str or amount_str == "null":
            return None, None

        try:
            # Extract currency code first
            currency_match = re.search(r"\b(INR|USD|EUR|GBP)\b", amount_str, re.IGNORECASE)
            currency = currency_match.group(1).upper() if currency_match else "INR"

            # Extract numeric part (including decimal point)
            numeric_match = re.search(r"(\d+(?:\.\d{2})?)", amount_str)
            if numeric_match:
                amount = float(numeric_match.group(1))
            else:
                return None, None

            logger.debug(f"Normalized amount '{amount_str}' → {amount} {currency}")
            return amount, currency

        except (ValueError, AttributeError):
            logger.warning(f"Failed to normalize amount: {amount_str}")
            return None, None

    @staticmethod
    def normalize_area(area_str: str) -> Tuple[float, str]:
        """
        Normalize area measurement to float and extract unit.

        Args:
            area_str: String like "5000 sq.ft", "2.5 acres", "500 sqm"

        Returns:
            Tuple of (float_area, unit)
        """
        if not area_str or area_str == "null":
            return None, None

        try:
            # Extract unit
            unit_match = re.search(
                r"\b(sq\.?ft|sqft|sq\.?m|sqm|acres?|hectares?)\b",
                area_str,
                re.IGNORECASE,
            )
            unit = unit_match.group(1).lower() if unit_match else "sq.ft"

            # Extract numeric part
            numeric_match = re.search(r"(\d+(?:\.\d+)?)", area_str)
            area = float(numeric_match.group(1)) if numeric_match else None

            if area is None:
                return None, None

            logger.debug(f"Normalized area '{area_str}' → {area} {unit}")
            return area, unit

        except (ValueError, AttributeError):
            logger.warning(f"Failed to normalize area: {area_str}")
            return None, None

    @staticmethod
    def normalize_date(date_str: str) -> str:
        """
        Normalize date string to ISO format (YYYY-MM-DD).

        Args:
            date_str: Date in various formats

        Returns:
            ISO format date string or None
        """
        if not date_str or date_str == "null":
            return None

        try:
            # Common date patterns
            patterns = [
                r"(\d{4})-(\d{1,2})-(\d{1,2})",  # YYYY-MM-DD
                r"(\d{1,2})/(\d{1,2})/(\d{4})",  # DD/MM/YYYY
                r"(\d{1,2})-(\w{3,9})-(\d{4})",  # DD-Mon-YYYY
            ]

            for pattern in patterns:
                match = re.search(pattern, date_str)
                if match:
                    if len(match.groups()[0]) == 4:  # YYYY first
                        year, month, day = match.groups()
                    else:  # DD first
                        day, month, year = match.groups()
                        # Handle month names
                        if not month.isdigit():
                            month_map = {
                                "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                                "may": 5, "jun": 6, "jul": 7, "aug": 8,
                                "sep": 9, "oct": 10, "nov": 11, "dec": 12,
                            }
                            month = month_map.get(month[:3].lower(), 1)

                    dt = datetime(int(year), int(month), int(day))
                    iso_date = dt.strftime("%Y-%m-%d")
                    logger.debug(f"Normalized date '{date_str}' → {iso_date}")
                    return iso_date

            logger.warning(f"Could not normalize date: {date_str}")
            return None

        except (ValueError, AttributeError) as e:
            logger.warning(f"Date normalization error: {e}")
            return None

    @staticmethod
    def normalize_phone(phone_str: str) -> str:
        """
        Normalize phone number (India format: 10 digits).

        Args:
            phone_str: Phone number with various formats

        Returns:
            Cleaned 10-digit phone number or None
        """
        if not phone_str:
            return None

        try:
            # Remove all non-digit characters
            digits = re.sub(r"\D", "", phone_str)

            # Keep only last 10 digits (remove country code if present)
            if len(digits) >= 10:
                phone = digits[-10:]
                logger.debug(f"Normalized phone '{phone_str}' → {phone}")
                return phone

            return None

        except Exception as e:
            logger.warning(f"Phone normalization error: {e}")
            return None

    def validate_echallan(
        self, data: Dict[str, Any]
    ) -> Tuple[EchallanData, float, List[str]]:
        """
        Validate and normalize eChallan data.

        Args:
            data: Extracted eChallan dictionary

        Returns:
            Tuple of (EchallanData object, adjusted_confidence, list of issues)
        """
        issues = []
        confidence_adjustments = 0.0

        # Normalize amount
        if data.get("amount_due"):
            amount, currency = self.normalize_amount(str(data["amount_due"]))
            if amount:
                data["amount_due"] = amount
            else:
                issues.append("Invalid amount_due format")
                confidence_adjustments += self.VALIDATION_PENALTY

        # Normalize dates
        for date_field in ["payment_due_date", "issuing_date"]:
            if data.get(date_field):
                normalized = self.normalize_date(str(data[date_field]))
                if normalized:
                    data[date_field] = normalized
                else:
                    issues.append(f"Invalid {date_field} format")
                    confidence_adjustments += self.VALIDATION_PENALTY

        # Cross-field validation
        if data.get("payment_due_date") and data.get("issuing_date"):
            try:
                due = datetime.fromisoformat(data["payment_due_date"])
                issued = datetime.fromisoformat(data["issuing_date"])
                if due < issued:
                    issues.append(
                        "payment_due_date is before issuing_date (logical error)"
                    )
                    confidence_adjustments += self.VALIDATION_PENALTY
            except (ValueError, AttributeError):
                pass

        # Validate vehicle registration format (India: XX-DD-XX-NNNN)
        if data.get("vehicle_reg_number"):
            if not re.match(r"^[A-Z]{2}-\d{2}-[A-Z]{2}-\d{4}$", str(data["vehicle_reg_number"])):
                issues.append("vehicle_reg_number format invalid (expected XX-DD-XX-NNNN)")
                confidence_adjustments += self.VALIDATION_PENALTY / 2  # Soft penalty

        # Create Pydantic model
        try:
            validated = EchallanData(**data)
            logger.info(f"eChallan validated: {len(issues)} issues found")
            return validated, -confidence_adjustments, issues

        except Exception as e:
            logger.error(f"eChallan validation failed: {e}")
            issues.append(f"Schema validation error: {str(e)}")
            return EchallanData(), -confidence_adjustments - 0.20, issues

    def validate_na_permission(
        self, data: Dict[str, Any]
    ) -> Tuple[NAPermissionData, float, List[str]]:
        """
        Validate and normalize NA/Lease Permission data.

        Args:
            data: Extracted NA Permission dictionary

        Returns:
            Tuple of (NAPermissionData object, adjusted_confidence, list of issues)
        """
        issues = []
        confidence_adjustments = 0.0

        # Normalize area (use 'area' or 'property_area')
        area_field = "property_area" if "property_area" in data else "area"
        if data.get(area_field):
            area, unit = self.normalize_area(str(data[area_field]))
            if area:
                data[area_field] = area
                data["property_area_unit"] = unit
            else:
                issues.append(f"Invalid {area_field} format")
                confidence_adjustments += self.VALIDATION_PENALTY

        # Normalize dates
        for date_field in ["permission_date", "expiry_date", "last_updated"]:
            if data.get(date_field):
                normalized = self.normalize_date(str(data[date_field]))
                if normalized:
                    data[date_field] = normalized
                else:
                    issues.append(f"Invalid {date_field} format")
                    confidence_adjustments += self.VALIDATION_PENALTY

        # Cross-field validation: expiry_date > permission_date
        if data.get("permission_date") and data.get("expiry_date"):
            try:
                perm = datetime.fromisoformat(data["permission_date"])
                exp = datetime.fromisoformat(data["expiry_date"])
                if exp <= perm:
                    issues.append(
                        "expiry_date must be after permission_date (logical error)"
                    )
                    confidence_adjustments += self.VALIDATION_PENALTY
            except (ValueError, AttributeError):
                pass

        # Validate phone if present
        if data.get("owner_contact"):
            normalized_phone = self.normalize_phone(str(data["owner_contact"]))
            if normalized_phone:
                data["owner_contact"] = normalized_phone

        # Validate restrictions is a list
        if data.get("restrictions") and not isinstance(data["restrictions"], list):
            data["restrictions"] = [str(data["restrictions"])]

        # Create Pydantic model
        try:
            validated = NAPermissionData(**data)
            logger.info(f"NA Permission validated: {len(issues)} issues found")
            return validated, -confidence_adjustments, issues

        except Exception as e:
            logger.error(f"NA Permission validation failed: {e}")
            issues.append(f"Schema validation error: {str(e)}")
            return NAPermissionData(), -confidence_adjustments - 0.20, issues

    def validate_batch(
        self,
        results: List[Dict[str, Any]],
        doc_type: DocumentType,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Validate a batch of extraction results.

        Args:
            results: List of extraction result dictionaries
            doc_type: DocumentType (ECHALLAN or NA_PERMISSION)

        Returns:
            Tuple of (validated_results, summary_stats)
        """
        validated_results = []
        stats = {
            "total": len(results),
            "validated": 0,
            "with_issues": 0,
            "total_issues": 0,
            "avg_confidence_adjustment": 0.0,
        }

        total_adjustment = 0.0

        for result in results:
            try:
                if doc_type == DocumentType.ECHALLAN:
                    data = result.get("echallan_data", {})
                    validated, adj, issues = self.validate_echallan(data)
                elif doc_type == DocumentType.NA_PERMISSION:
                    data = result.get("na_data", {})
                    validated, adj, issues = self.validate_na_permission(data)
                else:
                    continue

                result["validated_data"] = validated.model_dump()
                result["validation_issues"] = issues
                result["confidence_adjustment"] = adj
                total_adjustment += adj

                validated_results.append(result)
                stats["validated"] += 1

                if issues:
                    stats["with_issues"] += 1
                    stats["total_issues"] += len(issues)

            except Exception as e:
                logger.error(f"Batch validation error: {e}")

        if stats["validated"] > 0:
            stats["avg_confidence_adjustment"] = total_adjustment / stats["validated"]

        logger.info(f"Batch validation complete: {stats}")
        return validated_results, stats
