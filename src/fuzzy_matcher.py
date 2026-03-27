"""
Fuzzy matching module for compliance document extraction.
Handles typo correction and partial field matching.
"""

from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger(__name__)


class FuzzyMatcher:
    """Fuzzy matching for field extraction and typo correction."""
    
    # Common vehicle type typos/variations
    VEHICLE_TYPES = {
        "car": ["car", "cars", "automobile", "auto", "sedan", "coupe"],
        "motorcycle": ["motorcycle", "bike", "motorbike", "two wheeler", "2-wheeler"],
        "truck": ["truck", "trucks", "lorry", "hgv"],
        "bus": ["bus", "buses", "coach"],
        "auto_rickshaw": ["auto", "autorickshaw", "three wheeler", "3-wheeler", "tuk-tuk"],
        "scooter": ["scooter", "scooty"],
        "van": ["van", "minivan"],
        "commercial": ["commercial", "commercial vehicle", "cv"]
    }
    
    # Common violation/violation type typos
    VIOLATION_TYPES = {
        "speeding": ["speeding", "over speed", "overspeed", "speed violation"],
        "parking": ["parking", "illegal parking", "wrong parking"],
        "red_light": ["red light", "signal violation", "signal jump"],
        "lane_violation": ["lane violation", "lane change", "wrong lane"],
        "pollution": ["pollution", "emission", "puc"],
        "documentation": ["documentation", "doc", "license", "registration"],
        "helmet": ["helmet", "safety helmet", "no helmet"],
        "seat_belt": ["seat belt", "seatbelt", "no seatbelt"],
        "insurance": ["insurance", "no insurance"],
        "driving_behavior": ["driving behavior", "rash driving", "dangerous driving"]
    }
    
    # Common permission/document types
    PERMISSION_TYPES = {
        "lease": ["lease", "lease deed", "tenancy", "rental"],
        "sale": ["sale", "sale deed", "purchase"],
        "mortgage": ["mortgage", "loan"],
        "transfer": ["transfer", "transfer of ownership"],
        "na": ["na", "non-agricultural", "non agricultural"],
        "conversion": ["conversion", "land conversion"]
    }
    
    PAYMENT_STATUS = {
        "paid": ["paid", "cleared", "settled", "complete", "completed"],
        "pending": ["pending", "outstanding", "due", "unpaid"],
        "partial": ["partial", "part paid", "partially paid"],
        "disputed": ["disputed", "under dispute", "contestation"]
    }
    
    @staticmethod
    def similarity_ratio(a: str, b: str) -> float:
        """
        Calculate similarity ratio between two strings.
        
        Args:
            a: First string
            b: Second string
        
        Returns:
            Similarity ratio (0-1)
        """
        a_clean = a.lower().strip()
        b_clean = b.lower().strip()
        return SequenceMatcher(None, a_clean, b_clean).ratio()
    
    @staticmethod
    def best_match(text: str, candidates: List[str], threshold: float = 0.6) -> Optional[str]:
        """
        Find best matching candidate for text.
        
        Args:
            text: Input text to match
            candidates: List of candidate strings
            threshold: Minimum similarity threshold (0-1)
        
        Returns:
            Best matching candidate or None if no match above threshold
        """
        if not text or not candidates:
            return None
        
        text_clean = text.lower().strip()
        
        best_score = 0
        best_candidate = None
        
        for candidate in candidates:
            score = FuzzyMatcher.similarity_ratio(text_clean, candidate.lower())
            if score > best_score:
                best_score = score
                best_candidate = candidate
        
        return best_candidate if best_score >= threshold else None
    
    @classmethod
    def match_vehicle_type(cls, text: str, threshold: float = 0.6) -> Optional[str]:
        """
        Match vehicle type with typo correction.
        
        Args:
            text: Vehicle type text
            threshold: Minimum similarity threshold
        
        Returns:
            Canonical vehicle type or None
        """
        if not text:
            return None
        
        for canonical, variations in cls.VEHICLE_TYPES.items():
            match = cls.best_match(text, variations, threshold)
            if match:
                return canonical
        
        return None
    
    @classmethod
    def match_violation_type(cls, text: str, threshold: float = 0.6) -> Optional[str]:
        """
        Match violation type with typo correction.
        
        Args:
            text: Violation type text
            threshold: Minimum similarity threshold
        
        Returns:
            Canonical violation type or None
        """
        if not text:
            return None
        
        for canonical, variations in cls.VIOLATION_TYPES.items():
            match = cls.best_match(text, variations, threshold)
            if match:
                return canonical
        
        return None
    
    @classmethod
    def match_permission_type(cls, text: str, threshold: float = 0.6) -> Optional[str]:
        """
        Match permission/deed type with typo correction.
        
        Args:
            text: Permission type text
            threshold: Minimum similarity threshold
        
        Returns:
            Canonical permission type or None
        """
        if not text:
            return None
        
        for canonical, variations in cls.PERMISSION_TYPES.items():
            match = cls.best_match(text, variations, threshold)
            if match:
                return canonical
        
        return None
    
    @classmethod
    def match_payment_status(cls, text: str, threshold: float = 0.6) -> Optional[str]:
        """
        Match payment status with typo correction.
        
        Args:
            text: Payment status text
            threshold: Minimum similarity threshold
        
        Returns:
            Canonical payment status or None
        """
        if not text:
            return None
        
        for canonical, variations in cls.PAYMENT_STATUS.items():
            match = cls.best_match(text, variations, threshold)
            if match:
                return canonical
        
        return None
    
    @staticmethod
    def extract_phone_fuzzy(text: str) -> Optional[str]:
        """
        Extract phone number with fuzzy matching.
        Handles common typos like O instead of 0, l instead of 1.
        
        Args:
            text: Text containing phone number
        
        Returns:
            Cleaned phone number or None
        """
        if not text:
            return None
        
        # First, replace common character confusions
        text_clean = text.lower()
        text_clean = text_clean.replace('o', '0')  # Letter O -> digit 0
        text_clean = text_clean.replace('l', '1')  # Letter L -> digit 1
        text_clean = text_clean.replace('s', '5')  # Letter S -> digit 5
        text_clean = text_clean.replace('z', '2')  # Letter Z -> digit 2
        
        # Extract 10-digit number
        match = re.search(r'\b(\d{10})\b', text_clean)
        if match:
            return match.group(1)
        
        # Also try 12-digit (with country code)
        match = re.search(r'\b(\d{12})\b', text_clean)
        if match:
            return match.group(1)
        
        return None
    
    @staticmethod
    def extract_amount_fuzzy(text: str) -> Optional[float]:
        """
        Extract amount with fuzzy matching.
        Handles common formatting variations.
        
        Args:
            text: Text containing amount
        
        Returns:
            Amount as float or None
        """
        if not text:
            return None
        
        # Remove common currency symbols and text
        text_clean = text.replace('Rs', '').replace('₹', '').replace('rupees', '')
        text_clean = text_clean.replace(',', '')  # Remove thousand separator
        
        # Extract number (with decimal)
        match = re.search(r'(\d+\.?\d*)', text_clean)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        
        return None
    
    @staticmethod
    def extract_date_fuzzy(text: str) -> Optional[str]:
        """
        Extract date with fuzzy matching.
        Handles various date formats.
        
        Args:
            text: Text containing date
        
        Returns:
            Standardized date string (DD/MM/YYYY) or None
        """
        if not text:
            return None
        
        text_clean = text.strip()
        
        # Common date patterns
        patterns = [
            # DD/MM/YYYY or DD-MM-YYYY
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', lambda m: f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"),
            # YYYY-MM-DD (ISO format)
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}"),
            # DD Month YYYY
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})', 
             lambda m: f"{int(m.group(1)):02d}/{_month_to_num(m.group(2))}/{m.group(3)}"),
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                return formatter(match)
        
        return None
    
    @staticmethod
    def normalize_field(field_name: str, value: str) -> Tuple[Optional[str], float]:
        """
        Normalize extracted field value with confidence score.
        
        Args:
            field_name: Name of the field (e.g., 'vehicle_type', 'amount')
            value: Extracted value
        
        Returns:
            Tuple of (normalized_value, confidence)
        """
        if not value:
            return None, 0.0
        
        field_lower = field_name.lower()
        
        if "vehicle" in field_lower and "type" in field_lower:
            match = FuzzyMatcher.match_vehicle_type(value, threshold=0.5)
            return match, 0.8 if match else 0.0
        
        elif "violation" in field_lower or "offense" in field_lower:
            match = FuzzyMatcher.match_violation_type(value, threshold=0.5)
            return match, 0.8 if match else 0.0
        
        elif "permission" in field_lower or "deed" in field_lower:
            match = FuzzyMatcher.match_permission_type(value, threshold=0.5)
            return match, 0.8 if match else 0.0
        
        elif "payment" in field_lower and "status" in field_lower:
            match = FuzzyMatcher.match_payment_status(value, threshold=0.5)
            return match, 0.8 if match else 0.0
        
        elif "phone" in field_lower or "contact" in field_lower or "mobile" in field_lower:
            phone = FuzzyMatcher.extract_phone_fuzzy(value)
            return phone, 0.9 if phone else 0.0
        
        elif "amount" in field_lower or "fine" in field_lower or "price" in field_lower:
            amount = FuzzyMatcher.extract_amount_fuzzy(value)
            return str(amount) if amount else None, 0.9 if amount else 0.0
        
        elif "date" in field_lower:
            date = FuzzyMatcher.extract_date_fuzzy(value)
            return date, 0.9 if date else 0.5
        
        # Default: return original value with neutral confidence
        return value, 0.5


def _month_to_num(month: str) -> str:
    """Convert month name to number."""
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    return months.get(month.lower()[:3], '00')
