"""Core epistemological and domain schemas for EvidenceOS / VeriDock.

Core Principle:
Never allow an LLM to silently invent facts. Every conclusion must carry:
- Source
- Evidence reference
- Confidence
- Reason
- Timestamp
- Processing method
- Epistemological status (FACT | INFERENCE | RULE | UNCERTAINTY)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class EpistemologicalType(str, Enum):
    """Distinguishes how a piece of knowledge was established."""

    FACT = "FACT"  # Directly extracted from a single piece of evidence
    INFERENCE = "INFERENCE"  # Derived by combining or linking multiple pieces of evidence
    RULE = "RULE"  # Determined by explicit deterministic business logic
    UNCERTAINTY = "UNCERTAINTY"  # Insufficient, low-confidence, or conflicting evidence


class EvidenceModality(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    JSON = "json"
    CSV = "csv"
    MANUAL = "manual"


class DocumentRole(str, Enum):
    PURCHASE_ORDER = "purchase_order"
    DELIVERY_CHALLAN = "delivery_challan"
    INVOICE = "invoice"
    INSPECTION_IMAGE = "inspection_image"
    VOICE_REPORT = "voice_report"
    INSPECTION_REPORT = "inspection_report"
    TEMPERATURE_LOGGER = "temperature_logger"
    UNKNOWN = "unknown"


class CaseStatus(str, Enum):
    CREATED = "created"
    EVIDENCE_UPLOADED = "evidence_uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DECIDED = "decided"
    HUMAN_REVIEWED = "human_reviewed"
    FAILED = "failed"


class DecisionOutcome(str, Enum):
    APPROVED = "approved"
    PARTIALLY_APPROVED = "partially_approved"
    DISPUTED = "disputed"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Provenance(BaseModel):
    """Strict provenance record attached to every extracted fact, inference, or rule evaluation."""

    evidence_id: str = Field(..., description="Unique ID of the source evidence artifact")
    source_type: EvidenceModality = Field(..., description="Modality of the source evidence")
    document_role: DocumentRole = Field(default=DocumentRole.UNKNOWN)
    location: Optional[str] = Field(
        default=None,
        description="Page number, bounding box, audio timestamp, or JSON path (e.g., 'page:1', '00:02-00:08')",
    )
    extraction_method: str = Field(
        ...,
        description="Identifier of extractor/model used (e.g., 'pypdf+deterministic_parser', 'gemini-2.5-flash', 'dhash_64bit')",
    )
    timestamp: datetime = Field(default_factory=utc_now)
    confidence: float = Field(..., ge=0.0, le=1.0)
    epistemic_type: EpistemologicalType = Field(default=EpistemologicalType.FACT)
    raw_snippet: Optional[str] = Field(
        default=None, description="Verbatim text or visual observation snippet supporting this fact"
    )


class LineItemExtraction(BaseModel):
    """Structured representation of a line item in a PO, Delivery Challan, or Invoice."""

    sku: str = Field(..., description="Normalized or raw SKU / item code")
    name: str = Field(..., description="Product description or item name")
    ordered_quantity: Optional[int] = Field(default=None, ge=0)
    delivered_quantity: Optional[int] = Field(default=None, ge=0)
    damaged_quantity: Optional[int] = Field(default=0, ge=0)
    accepted_quantity: Optional[int] = Field(default=None, ge=0)
    unit_price: Optional[float] = Field(default=None, ge=0.0)
    currency: str = Field(default="USD")

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, v: str) -> str:
        return v.strip().upper()


class DocumentExtractionResult(BaseModel):
    """Structured extraction output for Purchase Orders, Delivery Challans, and Invoices."""

    document_type: DocumentRole
    document_id: str
    po_reference: Optional[str] = None
    shipment_id: Optional[str] = None
    supplier: str
    buyer: str
    date: Optional[str] = None
    items: List[LineItemExtraction] = Field(default_factory=list)
    total_quantity: int = Field(default=0, ge=0)
    damaged_quantity: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    source_evidence_id: str
    provenance: Provenance


class ImageAnalysisResult(BaseModel):
    """Structured visual evidence extraction from product/delivery photos."""

    visible_products: List[str] = Field(default_factory=list)
    detected_sku: Optional[str] = None
    visible_quantity: Optional[int] = Field(default=None, ge=0)
    damaged_quantity: int = Field(default=0, ge=0)
    damage_indicators: List[str] = Field(default_factory=list)
    packaging_condition: str = Field(
        default="unknown",
        description="e.g., 'intact', 'crushed_corner', 'water_damaged', 'torn_seal', 'unclear'",
    )
    visible_labels: List[str] = Field(default_factory=list)
    serial_numbers: List[str] = Field(default_factory=list)
    supports_damage_claim: Optional[bool] = Field(
        default=None,
        description="True if visual evidence clearly shows damage, False if clearly intact, None if inconclusive",
    )
    visual_summary: str
    perceptual_hash: str = Field(..., description="64-bit hex dHash of the image")
    source_evidence_id: str
    provenance: Provenance


class VoiceClaimExtraction(BaseModel):
    """Structured claim extracted from warehouse/driver audio or voice transcript."""

    transcript: str
    claim_type: str = Field(..., description="e.g., 'damage', 'shortage', 'clean_delivery', 'delay'")
    claimed_quantity: int = Field(default=0, ge=0)
    target_object: str = Field(default="units", description="e.g., 'box', 'pallet', 'carton', 'unit'")
    sku_mentioned: Optional[str] = None
    event_stage: str = Field(default="unloading", description="e.g., 'unloading', 'receiving_inspection', 'transit'")
    speaker_role: str = Field(default="receiving_inspector")
    source_evidence_id: str
    provenance: Provenance


class NormalizedClaim(BaseModel):
    """Unified, cross-modal evidence representation (Phase 4).

    Every modality (PDF PO, PDF Challan, Image, Voice, JSON, Manual) is normalized
    into atomic NormalizedClaim statements with full provenance.
    """

    claim_id: str = Field(default_factory=lambda: new_id("clm"))
    case_id: str
    entity_key: str = Field(
        ...,
        description="Canonical entity key resolved across modalities (e.g., 'ITEM:SKU-IND-100' or 'SHIPMENT:MAIN')",
    )
    attribute: str = Field(
        ...,
        description="Normalized attribute name: 'ordered_quantity', 'delivered_quantity', 'damaged_quantity', 'unit_price', 'packaging_condition'",
    )
    value: Any = Field(..., description="Normalized value (int, float, str, bool)")
    unit: Optional[str] = Field(default="units")
    epistemic_type: EpistemologicalType = Field(default=EpistemologicalType.FACT)
    reason: str
    provenance: Provenance


class ResolvedEntity(BaseModel):
    """Entity resolved across Purchase Order, Delivery Challan, Image, and Voice (Phase 5)."""

    entity_id: str = Field(default_factory=lambda: new_id("ent"))
    case_id: str
    entity_type: str = Field(..., description="'line_item' | 'shipment' | 'party'")
    canonical_key: str = Field(..., description="e.g., 'ITEM:SKU-IND-100'")
    display_name: str
    sku: Optional[str] = None
    linked_evidence_ids: List[str] = Field(default_factory=list)
    linked_claim_ids: List[str] = Field(default_factory=list)
    attributes_by_source: Dict[str, Any] = Field(default_factory=dict)
    resolution_method: str = Field(
        default="exact_sku_and_semantic_token_match",
        description="How the entity was matched across documents, images, and voice",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str = Field(..., description="'case' | 'evidence' | 'entity' | 'claim' | 'conflict' | 'decision'")
    epistemic_type: Optional[EpistemologicalType] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("edge"))
    source: str
    target: str
    relation: str = Field(
        ...,
        description="e.g., 'CONTAINS_EVIDENCE', 'EXTRACTED_CLAIM', 'REFERS_TO_ENTITY', 'SUPPORTED_BY', 'CONTRADICTS', 'DETERMINES'",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceGraph(BaseModel):
    case_id: str
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class ConflictSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceConflict(BaseModel):
    """Explicit contradiction surfaced across evidence sources (Phase 6)."""

    conflict_id: str = Field(default_factory=lambda: new_id("cnf"))
    case_id: str
    conflict_type: str = Field(
        ...,
        description="e.g., 'SHORT_DELIVERY_MISMATCH', 'DAMAGE_QUANTITY_CONTRADICTION', 'UNCORROBORATED_VOICE_CLAIM', 'VISUAL_CONTRADICTS_CLAIM'",
    )
    severity: ConflictSeverity
    entity_key: str
    attribute: str
    description: str
    competing_values: List[Dict[str, Any]] = Field(
        ...,
        description="List of {evidence_id, document_role, value, confidence, location}",
    )
    epistemic_type: EpistemologicalType = Field(default=EpistemologicalType.UNCERTAINTY)
    detected_at: datetime = Field(default_factory=utc_now)


class HistoricalMatchWarning(BaseModel):
    """Result of cryptographic or perceptual hash comparison against historical cases."""

    match_id: str = Field(default_factory=lambda: new_id("hmw"))
    case_id: str
    current_evidence_id: str
    historical_case_id: str
    historical_evidence_id: str
    match_type: str = Field(..., description="'exact_sha256' | 'perceptual_dhash'")
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    hamming_distance: Optional[int] = None
    warning_message: str = Field(
        default="Potentially reused evidence detected.",
        description="Neutral, non-accusatory warning message",
    )
    detected_at: datetime = Field(default_factory=utc_now)


class RuleEvaluationTrace(BaseModel):
    """Deterministic contract/SLA rule evaluation record."""

    rule_id: str
    rule_name: str
    passed: bool
    epistemic_type: EpistemologicalType = Field(default=EpistemologicalType.RULE)
    inputs_used: Dict[str, Any]
    evidence_ids: List[str] = Field(default_factory=list)
    explanation: str


class CaseDecision(BaseModel):
    """Final evidence-backed decision produced by the deterministic decision engine (Phase 7)."""

    decision_id: str = Field(default_factory=lambda: new_id("dec"))
    case_id: str
    outcome: DecisionOutcome
    epistemic_status: EpistemologicalType
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    ordered_quantity: int = 0
    delivered_quantity: int = 0
    verified_damaged_quantity: int = 0
    accepted_quantity: int = 0
    disputed_quantity: int = 0
    recommended_payout_adjustment_usd: float = 0.0
    summary_reason: str
    detailed_explanation: List[str] = Field(default_factory=list)
    next_action: str
    rule_traces: List[RuleEvaluationTrace] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    conflict_ids: List[str] = Field(default_factory=list)
    historical_warning_ids: List[str] = Field(default_factory=list)
    is_human_override: bool = False
    human_reviewer: Optional[str] = None
    human_override_notes: Optional[str] = None
    decided_at: datetime = Field(default_factory=utc_now)


class TemperatureReading(BaseModel):
    """Individual timestamped temperature sensor reading."""

    timestamp: datetime
    temperature_celsius: float = Field(..., alias="temperature_c")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    epistemic_type: EpistemologicalType = Field(default=EpistemologicalType.FACT)

    model_config = {
        "populate_by_name": True,
    }


class TemperatureTelemetryPayload(BaseModel):
    """Structured telemetry payload extracted or received from a cold-chain logger."""

    device_id: Optional[str] = None
    sensor_model: Optional[str] = None
    recording_interval_seconds: Optional[int] = None
    readings: List[TemperatureReading] = Field(default_factory=list)
    provenance: Optional[Provenance] = None
