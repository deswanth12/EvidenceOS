"""Database models and session management for EvidenceOS."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from core.config import get_settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CaseModel(Base):
    """Represents a B2B delivery or procurement dispute case in VeriDock."""

    __tablename__ = "cases"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    supplier_name = Column(String(255), nullable=True)
    buyer_name = Column(String(255), nullable=True)
    po_number = Column(String(128), nullable=True, index=True)
    status = Column(String(64), nullable=False, default="created")
    contract_sla_config = Column(JSON, nullable=False, default=dict)
    pipeline_Checklist = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    evidence_items = relationship("EvidenceRecordModel", back_populates="case", cascade="all, delete-orphan")
    claims = relationship("NormalizedClaimModel", back_populates="case", cascade="all, delete-orphan")
    entities = relationship("ResolvedEntityModel", back_populates="case", cascade="all, delete-orphan")
    conflicts = relationship("ConflictRecordModel", back_populates="case", cascade="all, delete-orphan")
    historical_warnings = relationship("HistoricalMatchModel", back_populates="case", cascade="all, delete-orphan")
    decisions = relationship("DecisionRecordModel", back_populates="case", cascade="all, delete-orphan")
    audit_events = relationship("AuditLogModel", back_populates="case", cascade="all, delete-orphan")


class EvidenceRecordModel(Base):
    """Immutable metadata and extraction record for an uploaded piece of evidence."""

    __tablename__ = "evidence_records"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    safe_filename = Column(String(255), nullable=False)
    storage_key = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=False)
    modality = Column(String(32), nullable=False)
    document_role = Column(String(64), nullable=False, default="unknown")
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    perceptual_hash = Column(String(64), nullable=True, index=True)
    extracted_payload = Column(JSON, nullable=True)
    extraction_metadata = Column(JSON, nullable=True)
    embedding_vector = Column(JSON, nullable=True)  # Stored as float array; pgvector compatible
    uploaded_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    case = relationship("CaseModel", back_populates="evidence_items")


class NormalizedClaimModel(Base):
    """Atomic normalized claim with provenance."""

    __tablename__ = "normalized_claims"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(String(64), nullable=False, index=True)
    entity_key = Column(String(128), nullable=False, index=True)
    attribute = Column(String(128), nullable=False)
    value_json = Column(JSON, nullable=False)
    unit = Column(String(64), nullable=True)
    epistemic_type = Column(String(32), nullable=False)
    reason = Column(Text, nullable=False)
    provenance_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("CaseModel", back_populates="claims")


class ResolvedEntityModel(Base):
    """Cross-modal resolved entity."""

    __tablename__ = "resolved_entities"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    canonical_key = Column(String(128), nullable=False)
    display_name = Column(String(255), nullable=False)
    sku = Column(String(128), nullable=True)
    linked_evidence_ids = Column(JSON, nullable=False, default=list)
    linked_claim_ids = Column(JSON, nullable=False, default=list)
    attributes_by_source = Column(JSON, nullable=False, default=dict)
    resolution_method = Column(String(128), nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)

    case = relationship("CaseModel", back_populates="entities")


class ConflictRecordModel(Base):
    """Detected contradiction across evidence items."""

    __tablename__ = "conflict_records"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    conflict_type = Column(String(128), nullable=False)
    severity = Column(String(32), nullable=False)
    entity_key = Column(String(128), nullable=False)
    attribute = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    competing_values = Column(JSON, nullable=False)
    epistemic_type = Column(String(32), nullable=False, default="UNCERTAINTY")
    detected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("CaseModel", back_populates="conflicts")


class HistoricalMatchModel(Base):
    """Record of cryptographic or perceptual similarity with prior case evidence."""

    __tablename__ = "historical_matches"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    current_evidence_id = Column(String(64), nullable=False)
    historical_case_id = Column(String(64), nullable=False)
    historical_evidence_id = Column(String(64), nullable=False)
    match_type = Column(String(64), nullable=False)
    similarity_score = Column(Float, nullable=False)
    hamming_distance = Column(Integer, nullable=True)
    warning_message = Column(Text, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("CaseModel", back_populates="historical_warnings")


class DecisionRecordModel(Base):
    """Evidence-backed decision or human review override."""

    __tablename__ = "decision_records"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    outcome = Column(String(64), nullable=False)
    epistemic_status = Column(String(32), nullable=False)
    overall_confidence = Column(Float, nullable=False)
    ordered_quantity = Column(Integer, nullable=False, default=0)
    delivered_quantity = Column(Integer, nullable=False, default=0)
    verified_damaged_quantity = Column(Integer, nullable=False, default=0)
    accepted_quantity = Column(Integer, nullable=False, default=0)
    disputed_quantity = Column(Integer, nullable=False, default=0)
    recommended_payout_adjustment_usd = Column(Float, nullable=False, default=0.0)
    summary_reason = Column(Text, nullable=False)
    detailed_explanation = Column(JSON, nullable=False, default=list)
    next_action = Column(Text, nullable=False)
    rule_traces = Column(JSON, nullable=False, default=list)
    supporting_evidence_ids = Column(JSON, nullable=False, default=list)
    conflict_ids = Column(JSON, nullable=False, default=list)
    historical_warning_ids = Column(JSON, nullable=False, default=list)
    is_human_override = Column(Boolean, nullable=False, default=False)
    human_reviewer = Column(String(128), nullable=True)
    human_override_notes = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("CaseModel", back_populates="decisions")


class AuditLogModel(Base):
    """Append-only tamper-evident audit trail entry."""

    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_num = Column(Integer, nullable=False, default=1, index=True)
    event_type = Column(String(128), nullable=False)
    actor = Column(String(128), nullable=False, default="system")
    stage = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="success")
    duration_ms = Column(Float, nullable=True)
    model_used = Column(String(128), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    previous_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False)
    timestamp_iso = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("CaseModel", back_populates="audit_events")


_engine = None
_SessionLocal = None


def get_engine(database_url: Optional[str] = None):
    global _engine
    if _engine is None or database_url is not None:
        settings = get_settings()
        url = database_url or settings.database_url
        if url.startswith("sqlite:///"):
            db_file = url.replace("sqlite:///", "")
            if db_file != ":memory:":
                Path(db_file).parent.mkdir(parents=True, exist_ok=True)
            connect_args: Dict[str, Any] = {"check_same_thread": False}
        else:
            connect_args = {}
        _engine = create_engine(url, connect_args=connect_args, future=True)
    return _engine


def init_db(database_url: Optional[str] = None) -> None:
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    # Ensure backwards compatibility for existing SQLite databases missing sequence_num or timestamp_iso
    try:
        with engine.begin() as conn:
            result = conn.exec_driver_sql("PRAGMA table_info(audit_logs)").fetchall()
            cols = [r[1] for r in result]
            if "sequence_num" not in cols and len(cols) > 0:
                conn.exec_driver_sql("ALTER TABLE audit_logs ADD COLUMN sequence_num INTEGER DEFAULT 1")
                cases = conn.exec_driver_sql("SELECT DISTINCT case_id FROM audit_logs").fetchall()
                for (cid,) in cases:
                    rows = conn.exec_driver_sql(
                        "SELECT id FROM audit_logs WHERE case_id = ? ORDER BY rowid ASC", (cid,)
                    ).fetchall()
                    for idx, (rid,) in enumerate(rows, start=1):
                        conn.exec_driver_sql(
                            "UPDATE audit_logs SET sequence_num = ? WHERE id = ?", (idx, rid)
                        )
            if "timestamp_iso" not in cols and len(cols) > 0:
                conn.exec_driver_sql("ALTER TABLE audit_logs ADD COLUMN timestamp_iso VARCHAR(64)")
    except Exception:
        pass


def get_session_factory(database_url: Optional[str] = None):
    global _SessionLocal
    if _SessionLocal is None or database_url is not None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
