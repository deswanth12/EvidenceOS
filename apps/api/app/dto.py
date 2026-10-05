"""Typed request and response DTO models for EvidenceOS REST API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.schemas import DecisionOutcome, DocumentRole, EvidenceGraph


class CreateCaseRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    supplier_name: Optional[str] = None
    buyer_name: Optional[str] = None
    po_number: Optional[str] = None
    max_auto_approve_damage_ratio: float = Field(default=0.25, ge=0.0, le=1.0)
    min_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class ManualEvidenceInputRequest(BaseModel):
    filename: str = Field(default="manual_inspection_note.txt")
    document_role: DocumentRole = Field(default=DocumentRole.VOICE_REPORT)
    text_content: str = Field(..., min_length=2, max_length=20000)


class HumanReviewOverrideRequest(BaseModel):
    outcome: DecisionOutcome
    reviewer: str = Field(..., min_length=2, max_length=128)
    notes: str = Field(..., min_length=5, max_length=4000)
    accepted_quantity: Optional[int] = Field(default=None, ge=0)
    verified_damaged_quantity: Optional[int] = Field(default=None, ge=0)


class EvidenceItemResponse(BaseModel):
    id: str
    case_id: str
    original_filename: str
    safe_filename: str
    mime_type: str
    modality: str
    document_role: str
    file_size_bytes: int
    sha256_hash: str
    perceptual_hash: Optional[str] = None
    extracted_payload: Optional[Dict[str, Any]] = None
    extraction_metadata: Optional[Dict[str, Any]] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None


class CaseSummaryResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    supplier_name: Optional[str] = None
    buyer_name: Optional[str] = None
    po_number: Optional[str] = None
    status: str
    pipeline_checklist: Dict[str, Any]
    evidence_count: int
    conflict_count: int
    historical_warning_count: int
    latest_decision_outcome: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CaseDetailResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    supplier_name: Optional[str] = None
    buyer_name: Optional[str] = None
    po_number: Optional[str] = None
    status: str
    contract_sla_config: Dict[str, Any]
    pipeline_checklist: Dict[str, Any]
    evidence_items: List[EvidenceItemResponse]
    claims: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    historical_warnings: List[Dict[str, Any]]
    latest_decision: Optional[Dict[str, Any]] = None
    graph: EvidenceGraph
    created_at: datetime
    updated_at: datetime
