"""REST API routes for VeriDock / EvidenceOS."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from apps.api.app.dto import (
    CaseDetailResponse,
    CaseSummaryResponse,
    CreateCaseRequest,
    EvidenceItemResponse,
    HumanReviewOverrideRequest,
    ManualEvidenceInputRequest,
)
from apps.api.app.security.auth import verify_api_key
from core.audit.logger import AuditService
from core.datasets_generator import get_canonical_benchmark_cases
from core.db.models import (
    CaseModel,
    ConflictRecordModel,
    DecisionRecordModel,
    EvidenceRecordModel,
    HistoricalMatchModel,
    NormalizedClaimModel,
    ResolvedEntityModel,
    get_db,
)
from core.decisions.engine import CaseVerificationPipeline, DecisionEngineService
from core.evidence.graph import EvidenceGraphBuilder
from core.ingestion.service import EvidenceIngestionService, IngestionValidationError
from core.schemas import (
    CaseDecision,
    ConflictSeverity,
    DecisionOutcome,
    EpistemologicalType,
    EvidenceConflict,
    NormalizedClaim,
    Provenance,
    ResolvedEntity,
    RuleEvaluationTrace,
    new_id,
)
from core.storage.provider import get_storage_provider
from evaluation.runner import run_empirical_evaluation

router = APIRouter()


def _serialize_evidence(rec: EvidenceRecordModel) -> EvidenceItemResponse:
    return EvidenceItemResponse(
        id=rec.id,
        case_id=rec.case_id,
        original_filename=rec.original_filename,
        safe_filename=rec.safe_filename,
        mime_type=rec.mime_type,
        modality=rec.modality,
        document_role=rec.document_role,
        file_size_bytes=rec.file_size_bytes,
        sha256_hash=rec.sha256_hash,
        perceptual_hash=rec.perceptual_hash,
        extracted_payload=rec.extracted_payload,
        extraction_metadata=rec.extraction_metadata,
        uploaded_at=rec.uploaded_at,
        processed_at=rec.processed_at,
    )


def _serialize_decision(dec: DecisionRecordModel) -> Dict[str, Any]:
    return {
        "decision_id": dec.id,
        "case_id": dec.case_id,
        "outcome": dec.outcome,
        "epistemic_status": dec.epistemic_status,
        "overall_confidence": dec.overall_confidence,
        "ordered_quantity": dec.ordered_quantity,
        "delivered_quantity": dec.delivered_quantity,
        "verified_damaged_quantity": dec.verified_damaged_quantity,
        "accepted_quantity": dec.accepted_quantity,
        "disputed_quantity": dec.disputed_quantity,
        "recommended_payout_adjustment_usd": dec.recommended_payout_adjustment_usd,
        "summary_reason": dec.summary_reason,
        "detailed_explanation": dec.detailed_explanation,
        "next_action": dec.next_action,
        "rule_traces": dec.rule_traces,
        "supporting_evidence_ids": dec.supporting_evidence_ids,
        "conflict_ids": dec.conflict_ids,
        "historical_warning_ids": dec.historical_warning_ids,
        "is_human_override": dec.is_human_override,
        "human_reviewer": dec.human_reviewer,
        "human_override_notes": dec.human_override_notes,
        "decided_at": dec.decided_at.isoformat() if dec.decided_at else None,
    }


@router.get("/cases", response_model=List[CaseSummaryResponse])
def list_cases(db: Session = Depends(get_db)) -> List[CaseSummaryResponse]:
    cases = db.query(CaseModel).order_by(CaseModel.created_at.desc()).all()
    summaries: List[CaseSummaryResponse] = []
    for c in cases:
        latest_dec = (
            db.query(DecisionRecordModel)
            .filter(DecisionRecordModel.case_id == c.id)
            .order_by(DecisionRecordModel.decided_at.desc())
            .first()
        )
        summaries.append(
            CaseSummaryResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                supplier_name=c.supplier_name,
                buyer_name=c.buyer_name,
                po_number=c.po_number,
                status=c.status,
                pipeline_checklist=c.pipeline_Checklist or {},
                evidence_count=len(c.evidence_items),
                conflict_count=len(c.conflicts),
                historical_warning_count=len(c.historical_warnings),
                latest_decision_outcome=latest_dec.outcome if latest_dec else None,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return summaries


@router.post("/cases", response_model=CaseSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    req: CreateCaseRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(verify_api_key),
) -> CaseSummaryResponse:
    case_id = new_id("case")
    checklist = {
        "evidence_received": False,
        "documents_processed": False,
        "images_analyzed": False,
        "voice_analyzed": False,
        "evidence_linked": False,
        "conflicts_detected": False,
        "rules_evaluated": False,
        "decision": None,
    }
    case = CaseModel(
        id=case_id,
        title=req.title,
        description=req.description,
        supplier_name=req.supplier_name,
        buyer_name=req.buyer_name,
        po_number=req.po_number,
        status="created",
        contract_sla_config={
            "max_auto_approve_damage_ratio": req.max_auto_approve_damage_ratio,
            "min_confidence_threshold": req.min_confidence_threshold,
        },
        pipeline_Checklist=checklist,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    AuditService.record_event(
        db=db,
        case_id=case_id,
        event_type="CASE_CREATED",
        stage="case_init",
        actor=actor,
        details={"title": req.title, "po_number": req.po_number},
    )

    return CaseSummaryResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        supplier_name=case.supplier_name,
        buyer_name=case.buyer_name,
        po_number=case.po_number,
        status=case.status,
        pipeline_checklist=case.pipeline_Checklist,
        evidence_count=0,
        conflict_count=0,
        historical_warning_count=0,
        latest_decision_outcome=None,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("/cases/{case_id}/evidence", response_model=EvidenceItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    document_role: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    actor: str = Depends(verify_api_key),
) -> EvidenceItemResponse:
    content = await file.read()
    ingestor = EvidenceIngestionService()
    try:
        record = ingestor.ingest_file(
            db=db,
            case_id=case_id,
            filename=file.filename or "uploaded_file",
            content=content,
            document_role=document_role,
            declared_mime=file.content_type,
            actor=actor,
        )
        return _serialize_evidence(record)
    except ValueError as exc:
        if isinstance(exc, IngestionValidationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/cases/{case_id}/evidence/manual",
    response_model=EvidenceItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_manual_evidence(
    case_id: str,
    req: ManualEvidenceInputRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(verify_api_key),
) -> EvidenceItemResponse:
    ingestor = EvidenceIngestionService()
    try:
        record = ingestor.ingest_file(
            db=db,
            case_id=case_id,
            filename=req.filename,
            content=req.text_content.encode("utf-8"),
            document_role=req.document_role.value,
            declared_mime="text/plain",
            actor=actor,
        )
        return _serialize_evidence(record)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cases/{case_id}/process")
def process_case(
    case_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    pipeline = CaseVerificationPipeline()
    try:
        return pipeline.run_case_pipeline(db=db, case_id=case_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
def get_case_detail(case_id: str, db: Session = Depends(get_db)) -> CaseDetailResponse:
    case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")

    evidence_records = (
        db.query(EvidenceRecordModel)
        .filter(EvidenceRecordModel.case_id == case_id)
        .order_by(EvidenceRecordModel.uploaded_at.asc())
        .all()
    )
    claim_models = db.query(NormalizedClaimModel).filter(NormalizedClaimModel.case_id == case_id).all()
    entity_models = db.query(ResolvedEntityModel).filter(ResolvedEntityModel.case_id == case_id).all()
    conflict_models = db.query(ConflictRecordModel).filter(ConflictRecordModel.case_id == case_id).all()
    warning_models = db.query(HistoricalMatchModel).filter(HistoricalMatchModel.case_id == case_id).all()
    latest_dec_model = (
        db.query(DecisionRecordModel)
        .filter(DecisionRecordModel.case_id == case_id)
        .order_by(DecisionRecordModel.decided_at.desc())
        .first()
    )

    claims_schema = [
        NormalizedClaim(
            claim_id=c.id,
            case_id=c.case_id,
            entity_key=c.entity_key,
            attribute=c.attribute,
            value=c.value_json,
            unit=c.unit,
            epistemic_type=EpistemologicalType(c.epistemic_type),
            reason=c.reason,
            provenance=Provenance.model_validate(c.provenance_json),
        )
        for c in claim_models
    ]

    entities_schema = [
        ResolvedEntity(
            entity_id=e.id,
            case_id=e.case_id,
            entity_type=e.entity_type,
            canonical_key=e.canonical_key,
            display_name=e.display_name,
            sku=e.sku,
            linked_evidence_ids=e.linked_evidence_ids,
            linked_claim_ids=e.linked_claim_ids,
            attributes_by_source=e.attributes_by_source,
            resolution_method=e.resolution_method,
            confidence=e.confidence,
        )
        for e in entity_models
    ]

    conflicts_schema = [
        EvidenceConflict(
            conflict_id=cf.id,
            case_id=cf.case_id,
            conflict_type=cf.conflict_type,
            severity=ConflictSeverity(cf.severity),
            entity_key=cf.entity_key,
            attribute=cf.attribute,
            description=cf.description,
            competing_values=cf.competing_values,
            epistemic_type=EpistemologicalType(cf.epistemic_type),
            detected_at=cf.detected_at,
        )
        for cf in conflict_models
    ]

    decision_schema = None
    if latest_dec_model:
        decision_schema = CaseDecision(
            decision_id=latest_dec_model.id,
            case_id=latest_dec_model.case_id,
            outcome=DecisionOutcome(latest_dec_model.outcome),
            epistemic_status=EpistemologicalType(latest_dec_model.epistemic_status),
            overall_confidence=latest_dec_model.overall_confidence,
            ordered_quantity=latest_dec_model.ordered_quantity,
            delivered_quantity=latest_dec_model.delivered_quantity,
            verified_damaged_quantity=latest_dec_model.verified_damaged_quantity,
            accepted_quantity=latest_dec_model.accepted_quantity,
            disputed_quantity=latest_dec_model.disputed_quantity,
            recommended_payout_adjustment_usd=latest_dec_model.recommended_payout_adjustment_usd,
            summary_reason=latest_dec_model.summary_reason,
            detailed_explanation=latest_dec_model.detailed_explanation,
            next_action=latest_dec_model.next_action,
            rule_traces=[RuleEvaluationTrace.model_validate(rt) for rt in (latest_dec_model.rule_traces or [])],
            supporting_evidence_ids=latest_dec_model.supporting_evidence_ids,
            conflict_ids=latest_dec_model.conflict_ids,
            historical_warning_ids=latest_dec_model.historical_warning_ids,
            is_human_override=latest_dec_model.is_human_override,
            human_reviewer=latest_dec_model.human_reviewer,
            human_override_notes=latest_dec_model.human_override_notes,
            decided_at=latest_dec_model.decided_at,
        )

    graph = EvidenceGraphBuilder.build_graph(
        case_id=case.id,
        case_title=case.title,
        evidence_records=evidence_records,
        entities=entities_schema,
        claims=claims_schema,
        conflicts=conflicts_schema,
        decision=decision_schema,
    )

    return CaseDetailResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        supplier_name=case.supplier_name,
        buyer_name=case.buyer_name,
        po_number=case.po_number,
        status=case.status,
        contract_sla_config=case.contract_sla_config or {},
        pipeline_checklist=case.pipeline_Checklist or {},
        evidence_items=[_serialize_evidence(r) for r in evidence_records],
        claims=[c.model_dump(mode="json") for c in claims_schema],
        entities=[e.model_dump(mode="json") for e in entities_schema],
        conflicts=[cf.model_dump(mode="json") for cf in conflicts_schema],
        historical_warnings=[
            {
                "match_id": w.id,
                "case_id": w.case_id,
                "current_evidence_id": w.current_evidence_id,
                "historical_case_id": w.historical_case_id,
                "historical_evidence_id": w.historical_evidence_id,
                "match_type": w.match_type,
                "similarity_score": w.similarity_score,
                "hamming_distance": w.hamming_distance,
                "warning_message": w.warning_message,
                "detected_at": w.detected_at.isoformat() if w.detected_at else None,
            }
            for w in warning_models
        ],
        latest_decision=_serialize_decision(latest_dec_model) if latest_dec_model else None,
        graph=graph,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/cases/{case_id}/evidence", response_model=List[EvidenceItemResponse])
def get_case_evidence(case_id: str, db: Session = Depends(get_db)) -> List[EvidenceItemResponse]:
    case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")
    records = (
        db.query(EvidenceRecordModel)
        .filter(EvidenceRecordModel.case_id == case_id)
        .order_by(EvidenceRecordModel.uploaded_at.asc())
        .all()
    )
    return [_serialize_evidence(r) for r in records]


@router.get("/cases/{case_id}/evidence/{evidence_id}/raw")
def download_raw_evidence(case_id: str, evidence_id: str, db: Session = Depends(get_db)) -> Response:
    rec = (
        db.query(EvidenceRecordModel)
        .filter(EvidenceRecordModel.case_id == case_id, EvidenceRecordModel.id == evidence_id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence item not found.")
    storage = get_storage_provider()
    raw_bytes = storage.read(rec.storage_key)
    return Response(
        content=raw_bytes,
        media_type=rec.mime_type,
        headers={"Content-Disposition": f'inline; filename="{rec.safe_filename}"'},
    )


@router.get("/cases/{case_id}/conflicts")
def get_case_conflicts(case_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")
    conflicts = db.query(ConflictRecordModel).filter(ConflictRecordModel.case_id == case_id).all()
    warnings = db.query(HistoricalMatchModel).filter(HistoricalMatchModel.case_id == case_id).all()
    return {
        "case_id": case_id,
        "conflicts": [
            {
                "conflict_id": c.id,
                "conflict_type": c.conflict_type,
                "severity": c.severity,
                "entity_key": c.entity_key,
                "attribute": c.attribute,
                "description": c.description,
                "competing_values": c.competing_values,
                "epistemic_type": c.epistemic_type,
                "detected_at": c.detected_at.isoformat() if c.detected_at else None,
            }
            for c in conflicts
        ],
        "historical_warnings": [
            {
                "match_id": w.id,
                "current_evidence_id": w.current_evidence_id,
                "historical_case_id": w.historical_case_id,
                "historical_evidence_id": w.historical_evidence_id,
                "match_type": w.match_type,
                "similarity_score": w.similarity_score,
                "hamming_distance": w.hamming_distance,
                "warning_message": w.warning_message,
            }
            for w in warnings
        ],
    }


@router.get("/cases/{case_id}/decision")
def get_case_decision(case_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    dec = (
        db.query(DecisionRecordModel)
        .filter(DecisionRecordModel.case_id == case_id)
        .order_by(DecisionRecordModel.decided_at.desc())
        .first()
    )
    if not dec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No decision computed yet for this case.")
    return _serialize_decision(dec)


@router.post("/cases/{case_id}/review")
def submit_human_review_override(
    case_id: str,
    req: HumanReviewOverrideRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")
    override_dec = DecisionEngineService.record_human_override(
        db=db,
        case_id=case_id,
        outcome=req.outcome,
        reviewer=req.reviewer,
        notes=req.notes,
        accepted_quantity=req.accepted_quantity,
        verified_damaged_quantity=req.verified_damaged_quantity,
    )
    return _serialize_decision(override_dec)


@router.get("/cases/{case_id}/audit")
def get_case_audit_trail(case_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")
    events = AuditService.list_case_audit_trail(db, case_id)
    integrity = AuditService.verify_chain_integrity(db, case_id)
    return {
        "case_id": case_id,
        "chain_integrity": integrity,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor": e.actor,
                "stage": e.stage,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "model_used": e.model_used,
                "details": e.details,
                "previous_event_hash": e.previous_event_hash,
                "event_hash": e.event_hash,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.post("/demo/seed")
def seed_canonical_demo_cases(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Seed and process the 5 canonical VeriDock cases if not already present (or reset them)."""
    ingestor = EvidenceIngestionService()
    pipeline = CaseVerificationPipeline()
    specs = get_canonical_benchmark_cases()
    seeded_ids: List[str] = []

    for spec in specs:
        existing = db.query(CaseModel).filter(CaseModel.id == spec["case_id"]).first()
        if existing:
            db.delete(existing)
    db.commit()

    for spec in specs:
        cid = spec["case_id"]
        case = CaseModel(
            id=cid,
            title=spec["title"],
            description=spec["description"],
            supplier_name=spec["supplier_name"],
            buyer_name=spec["buyer_name"],
            po_number=spec["po_number"],
            status="created",
            contract_sla_config={"max_auto_approve_damage_ratio": 0.25, "min_confidence_threshold": 0.75},
            pipeline_Checklist={},
        )
        db.add(case)
        db.commit()

        AuditService.record_event(
            db=db,
            case_id=cid,
            event_type="CASE_CREATED",
            stage="case_init",
            actor="demo_seeder",
            details={"title": spec["title"], "po_number": spec["po_number"]},
        )

        for f in spec["files"]:
            ingestor.ingest_file(
                db=db,
                case_id=cid,
                filename=f["filename"],
                content=f["content"],
                document_role=f["role"],
                actor="demo_seeder",
            )

        pipeline.run_case_pipeline(db=db, case_id=cid)
        seeded_ids.append(cid)

    return {"seeded_cases": len(seeded_ids), "case_ids": seeded_ids}


@router.get("/evaluation/run")
def run_evaluation_endpoint() -> Dict[str, Any]:
    """Execute the empirical evaluation suite and return live metrics."""
    return run_empirical_evaluation()
