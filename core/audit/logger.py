"""Tamper-evident append-only audit trail service (Module 13).

Records every uploaded evidence item, processing event, extracted fact,
conflict detection, rule evaluation, decision, and human override.
Chains each audit event using SHA-256 over the previous event's hash.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.db.models import AuditLogModel
from core.schemas import new_id


def _compute_event_hash(
    case_id: str,
    event_type: str,
    actor: str,
    stage: str,
    status: str,
    details: Dict[str, Any],
    previous_hash: Optional[str],
    timestamp_iso: str,
) -> str:
    payload = {
        "case_id": case_id,
        "event_type": event_type,
        "actor": actor,
        "stage": stage,
        "status": status,
        "details": details,
        "previous_hash": previous_hash or "GENESIS",
        "timestamp": timestamp_iso,
    }
    serialized = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


class AuditService:
    """Service for recording and verifying immutable case audit trails."""

    @staticmethod
    def record_event(
        db: Session,
        case_id: str,
        event_type: str,
        stage: str,
        details: Dict[str, Any],
        actor: str = "system",
        status: str = "success",
        duration_ms: Optional[float] = None,
        model_used: Optional[str] = None,
    ) -> AuditLogModel:
        last_event = (
            db.query(AuditLogModel)
            .filter(AuditLogModel.case_id == case_id)
            .order_by(AuditLogModel.sequence_num.desc(), AuditLogModel.created_at.desc(), AuditLogModel.id.desc())
            .first()
        )
        sequence_num = (last_event.sequence_num + 1) if (last_event and last_event.sequence_num is not None) else 1
        previous_hash = last_event.event_hash if last_event else "GENESIS"
        now = datetime.now(timezone.utc)
        event_hash = _compute_event_hash(
            case_id=case_id,
            event_type=event_type,
            actor=actor,
            stage=stage,
            status=status,
            details=details,
            previous_hash=previous_hash,
            timestamp_iso=now.isoformat(),
        )
        entry = AuditLogModel(
            id=new_id("aud"),
            case_id=case_id,
            sequence_num=sequence_num,
            event_type=event_type,
            actor=actor,
            stage=stage,
            status=status,
            duration_ms=duration_ms,
            model_used=model_used,
            details=details,
            previous_event_hash=previous_hash,
            event_hash=event_hash,
            created_at=now,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def list_case_audit_trail(db: Session, case_id: str) -> List[AuditLogModel]:
        return (
            db.query(AuditLogModel)
            .filter(AuditLogModel.case_id == case_id)
            .order_by(AuditLogModel.sequence_num.asc(), AuditLogModel.created_at.asc(), AuditLogModel.id.asc())
            .all()
        )

    @staticmethod
    def verify_chain_integrity(db: Session, case_id: str) -> Dict[str, Any]:
        events = AuditService.list_case_audit_trail(db, case_id)
        expected_prev = "GENESIS"
        for idx, ev in enumerate(events):
            if ev.previous_event_hash != expected_prev:
                return {
                    "valid": False,
                    "event_count": len(events),
                    "broken_at_index": idx,
                    "broken_event_id": ev.id,
                }
            expected_prev = ev.event_hash
        return {
            "valid": True,
            "event_count": len(events),
            "head_hash": expected_prev if events else None,
        }
