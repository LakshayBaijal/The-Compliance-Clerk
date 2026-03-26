"""
Pydantic schemas for The Compliance Clerk.
Defines data models for eChallan and NA Permission documents.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """Supported document types."""
    ECHALLAN = "eChallan"
    NA_PERMISSION = "NA/Lease Permission"
    UNKNOWN = "Unknown"


class EchallanData(BaseModel):
    """Schema for e-Challan (traffic fine) data."""
    
    # Identifiers
    challan_number: Optional[str] = Field(None, description="Unique challan number")
    vehicle_reg_number: Optional[str] = Field(None, description="Vehicle registration")
    
    # Violation
    violation_code: Optional[str] = Field(None, description="Violation code")
    violation_description: Optional[str] = Field(None, description="Description of violation")
    violation_date: Optional[str] = Field(None, description="Date of violation (YYYY-MM-DD)")
    violation_location: Optional[str] = Field(None, description="Where violation occurred")
    
    # Fine
    amount_due: Optional[float] = Field(None, description="Amount due")
    amount_currency: Optional[str] = Field(None, description="Currency (INR, USD)")
    payment_status: Optional[str] = Field(None, description="Payment status")
    payment_due_date: Optional[str] = Field(None, description="Payment due date")
    
    # Officer
    issued_by: Optional[str] = Field(None, description="Officer/authority")
    officer_id: Optional[str] = Field(None, description="Officer ID")
    issuing_date: Optional[str] = Field(None, description="Date issued")
    
    # Additional
    remarks: Optional[str] = Field(None, description="Additional remarks")


class NAPermissionData(BaseModel):
    """Schema for NA/Lease Permission data."""
    
    # Property
    property_id: Optional[str] = Field(None, description="Property ID")
    plot_number: Optional[str] = Field(None, description="Plot number")
    lease_deed_number: Optional[str] = Field(None, description="Lease deed number")
    
    # Details
    property_address: Optional[str] = Field(None, description="Property address")
    property_area: Optional[float] = Field(None, description="Area in sq.ft")
    property_area_unit: Optional[str] = Field(None, description="Unit of measurement")
    property_type: Optional[str] = Field(None, description="Type (residential/commercial)")
    
    # Ownership
    owner_name: Optional[str] = Field(None, description="Owner name")
    owner_contact: Optional[str] = Field(None, description="Owner contact")
    issuing_authority: Optional[str] = Field(None, description="Authority")
    
    # Permission
    permission_type: Optional[str] = Field(None, description="Type of permission")
    permission_date: Optional[str] = Field(None, description="Date granted")
    expiry_date: Optional[str] = Field(None, description="Expiry date")
    permission_status: Optional[str] = Field(None, description="Status (active/expired)")
    
    # Additional
    restrictions: Optional[List[str]] = Field(None, description="Restrictions")
    remarks: Optional[str] = Field(None, description="Additional remarks")


class ExtractionResult(BaseModel):
    """Complete extraction result for a document page."""
    
    # Tracking
    file_name: str = Field(..., description="Source PDF filename")
    page_num: int = Field(..., description="Page number")
    document_type: DocumentType = Field(..., description="Document type")
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Data
    echallan_data: Optional[EchallanData] = Field(None)
    na_permission_data: Optional[NAPermissionData] = Field(None)
    
    # Quality
    confidence: float = Field(..., description="Extraction confidence (0-1)")
    is_valid: bool = Field(default=True, description="Passed validation")
    validation_errors: List[str] = Field(default_factory=list)
    
    # Processing
    text_extracted: bool = Field(default=True)
    ocr_applied: bool = Field(default=False)
    llm_used: bool = Field(default=False)
    tokens_used: int = Field(default=0)
    processing_time_ms: float = Field(default=0)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BatchResult(BaseModel):
    """Results for a batch of documents."""
    
    total_files: int = Field(default=0)
    total_pages: int = Field(default=0)
    successful_extractions: int = Field(default=0)
    failed_extractions: int = Field(default=0)
    
    echallan_count: int = Field(default=0)
    na_permission_count: int = Field(default=0)
    
    total_tokens_used: int = Field(default=0)
    total_processing_time_ms: float = Field(default=0)
    
    extraction_results: List[ExtractionResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_pages == 0:
            return 0.0
        return (self.successful_extractions / self.total_pages) * 100
