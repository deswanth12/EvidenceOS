"""Deterministic Decision Engine & End-to-End Case Pipeline (Phase 7 / Module 11 & 14).

Produces evidence-backed decisions (`APPROVED`, `PARTIALLY_APPROVED`, `DISPUTED`,
`MANUAL_REVIEW_REQUIRED`, `INSUFFICIENT_EVIDENCE`) with complete provenance,
explanations, and support for human reviewer overrides.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.audit.logger import AuditService
from core.conflicts.detector import ConflictDetectionService
from core.db.models import CaseModel, DecisionRecordModel, EvidenceRecordModel
from core.entities.resolver import EntityResolutionService
from core.extraction.service import MultimodalExtractionService
from core.matching.historical import HistoricalMatchingService
from core.normalization.service import EvidenceNormalizationService
from core.rules.engine import DeterministicRuleEngine
from core.schemas import (
    CaseDecision,
    DecisionOutcome,
    EpistemologicalType,
    EvidenceConflict,
    HistoricalMatchWarning,
    ResolvedEntity,
)


class DecisionEngineService:
    """Computes final deterministic decision from rules, conflicts, and historical matches."""

    @staticmethod
    def compute_decision(
        db: Session,
        case_id: str,
        entities: List[ResolvedEntity],
        conflicts: List[EvidenceConflict],
        historical_warnings: List[HistoricalMatchWarning],
        contract_config: Dict[str, Any],
        use_rule_engine: bool = True,
    ) -> CaseDecision:
        db.query(DecisionRecordModel).filter(
            DecisionRecordModel.case_id == case_id,
            DecisionRecordModel.is_human_override.is_(False),
        ).delete()
        db.commit()

        rule_traces, metrics = DeterministicRuleEngine.evaluate_rules(
            entities=entities,
            conflicts=conflicts,
            historical_warnings=historical_warnings,
            contract_config=contract_config,
        )

        ordered_qty = metrics["ordered_quantity"]
        delivered_qty = metrics["delivered_quantity"]
        verified_dmg = metrics["verified_damaged_quantity"]
        max_claimed_dmg = metrics["max_claimed_damage"]
        accepted_qty = metrics["accepted_quantity"]
        disputed_qty = metrics["disputed_quantity"]
        payout_adj = metrics["recommended_payout_adjustment_usd"]
        min_conf = metrics["min_observed_confidence"]
        has_uncertain = metrics["has_uncertain_evidence"]
        evidence_ids = metrics["all_evidence_ids"]

        detailed_explanation: List[str] = []
        for tr in rule_traces:
            status_tag = "PASS" if tr.passed else "FAIL"
            detailed_explanation.append(f"[{tr.rule_id}: {status_tag}] {tr.explanation}")

        if not use_rule_engine:
            # System C (Semantic AI Only without Deterministic Rule Engine):
            # Relies on extracted quantities and direct contradictions only; does not enforce
            # SLA damage ratio caps, strict cross-modal corroboration, or uncertainty abstention rules.
            direct_contradictions = [
                c
                for c in conflicts
                if c.conflict_type
                in ("SHORT_DELIVERY_MISMATCH", "OVER_DELIVERY_MISMATCH", "DAMAGE_QUANTITY_CONTRADICTION")
            ]
            if not evidence_ids or (ordered_qty == 0 and delivered_qty == 0):
                outcome = DecisionOutcome.INSUFFICIENT_EVIDENCE
                epistemic = EpistemologicalType.UNCERTAINTY
                summary = "System C (AI-Only): No valid quantities extracted."
                next_action = "Upload procurement documents."
            elif direct_contradictions:
                outcome = DecisionOutcome.MANUAL_REVIEW_REQUIRED
                epistemic = EpistemologicalType.INFERENCE
                summary = f"System C (AI-Only): Direct quantity contradiction detected ({direct_contradictions[0].conflict_type})."
                next_action = "Review conflicting claims."
            elif max_claimed_dmg > 0:
                outcome = DecisionOutcome.PARTIALLY_APPROVED
                epistemic = EpistemologicalType.INFERENCE
                verified_dmg = max_claimed_dmg
                accepted_qty = max(0, (delivered_qty or ordered_qty) - verified_dmg)
                disputed_qty = max(0, ordered_qty - accepted_qty)
                min_conf = max(min_conf, 0.86)
                summary = f"System C (AI-Only): Auto-approving partial damage claim of {verified_dmg} units without deterministic rule gating."
                next_action = "Settle partial claim."
            else:
                outcome = DecisionOutcome.APPROVED
                epistemic = EpistemologicalType.INFERENCE
                min_conf = max(min_conf, 0.88)
                summary = "System C (AI-Only): Approved based on extracted quantities without deterministic rule gating."
                next_action = "Release payment."
            rule_traces = []
        else:
            # Decision state machine (100% deterministic - System D)
            if not evidence_ids:
                outcome = DecisionOutcome.INSUFFICIENT_EVIDENCE
                epistemic = EpistemologicalType.UNCERTAINTY
                summary = "No evidence artifacts have been uploaded to this case."
                next_action = "Upload Purchase Order, Delivery Challan, and inspection evidence."

            elif historical_warnings:
                outcome = DecisionOutcome.MANUAL_REVIEW_REQUIRED
                epistemic = EpistemologicalType.UNCERTAINTY
                summary = (
                    f"Manual review required: { historical_warnings[0].warning_message } "
                    "Automated settlement is suspended pending human audit of original files."
                )
                next_action = "Inspect flagged historical evidence side-by-side in the Conflict & Provenance panel."

            elif has_uncertain or min_conf < 0.75:
                outcome = DecisionOutcome.MANUAL_REVIEW_REQUIRED
                epistemic = EpistemologicalType.UNCERTAINTY
                summary = (
                    f"Manual review required due to insufficient or low-confidence evidence "
                    f"(minimum confidence {min_conf:.2f}). Claimed damage of {max_claimed_dmg} units cannot be verified automatically."
                )
                next_action = "Request higher-resolution inspection photographs or perform human adjudicator review."

            elif conflicts:
                outcome = DecisionOutcome.MANUAL_REVIEW_REQUIRED
                epistemic = EpistemologicalType.UNCERTAINTY
                conflict_summaries = "; ".join(c.description for c in conflicts)
                summary = (
                    f"Manual review required: {len(conflicts)} cross-modal contradiction(s) detected. "
                    f"{conflict_summaries}"
                )
                next_action = "Reconcile conflicting quantities across Purchase Order, Challan, Voice, and Image evidence."

            elif ordered_qty > 0 and delivered_qty == ordered_qty and verified_dmg == 0 and max_claimed_dmg == 0 and all(tr.passed for tr in rule_traces):
                outcome = DecisionOutcome.APPROVED
                epistemic = EpistemologicalType.RULE
                summary = (
                    f"Approved for full settlement: All {ordered_qty} ordered units were delivered intact "
                    "with 0 damaged units verified across documents, images, and voice reports."
                )
                next_action = "Release full invoice payment to supplier."

            elif (
                ordered_qty > 0
                and delivered_qty == ordered_qty
                and verified_dmg > 0
                and all(tr.passed for tr in rule_traces)
            ):
                outcome = DecisionOutcome.PARTIALLY_APPROVED
                epistemic = EpistemologicalType.RULE
                summary = (
                    f"Partially approved: {delivered_qty} of {ordered_qty} ordered units delivered, "
                    f"with {verified_dmg} damaged units corroborated across visual and voice inspection. "
                    f"Approve {accepted_qty} intact units and credit buyer ${payout_adj:.2f} for {disputed_qty} damaged units."
                )
                next_action = f"Issue credit note for ${payout_adj:.2f} ({disputed_qty} damaged units) and settle remaining {accepted_qty} units."

            else:
                outcome = DecisionOutcome.MANUAL_REVIEW_REQUIRED
                epistemic = EpistemologicalType.UNCERTAINTY
                summary = "Manual review required: SLA thresholds or quantity checks did not pass automatic settlement rules."
                next_action = "Assign to procurement dispute specialist for manual determination."

        decision = CaseDecision(
            case_id=case_id,
            outcome=outcome,
            epistemic_status=epistemic,
            overall_confidence=min_conf,
            ordered_quantity=ordered_qty,
            delivered_quantity=delivered_qty,
            verified_damaged_quantity=verified_dmg,
            accepted_quantity=accepted_qty,
            disputed_quantity=disputed_qty,
            recommended_payout_adjustment_usd=payout_adj,
            summary_reason=summary,
            detailed_explanation=detailed_explanation,
            next_action=next_action,
            rule_traces=rule_traces,
            supporting_evidence_ids=evidence_ids,
            conflict_ids=[c.conflict_id for c in conflicts],
            historical_warning_ids=[w.match_id for w in historical_warnings],
        )

        db_dec = DecisionRecordModel(
            id=decision.decision_id,
            case_id=case_id,
            outcome=decision.outcome.value,
            epistemic_status=decision.epistemic_status.value,
            overall_confidence=decision.overall_confidence,
            ordered_quantity=decision.ordered_quantity,
            delivered_quantity=decision.delivered_quantity,
            verified_damaged_quantity=decision.verified_damaged_quantity,
            accepted_quantity=decision.accepted_quantity,
            disputed_quantity=decision.disputed_quantity,
            recommended_payout_adjustment_usd=decision.recommended_payout_adjustment_usd,
            summary_reason=decision.summary_reason,
            detailed_explanation=decision.detailed_explanation,
            next_action=decision.next_action,
            rule_traces=[r.model_dump(mode="json") for r in decision.rule_traces],
            supporting_evidence_ids=decision.supporting_evidence_ids,
            conflict_ids=decision.conflict_ids,
            historical_warning_ids=decision.historical_warning_ids,
            is_human_override=False,
            decided_at=decision.decided_at,
        )
        db.add(db_dec)
        db.commit()

        AuditService.record_event(
            db=db,
            case_id=case_id,
            event_type="DECISION_COMPUTED",
            stage="decision_engine",
            details={
                "decision_id": decision.decision_id,
                "outcome": decision.outcome.value,
                "epistemic_status": decision.epistemic_status.value,
                "ordered_quantity": decision.ordered_quantity,
                "delivered_quantity": decision.delivered_quantity,
                "verified_damaged_quantity": decision.verified_damaged_quantity,
                "accepted_quantity": decision.accepted_quantity,
                "disputed_quantity": decision.disputed_quantity,
                "recommended_payout_adjustment_usd": decision.recommended_payout_adjustment_usd,
            },
        )
        return decision

    @staticmethod
    def record_human_override(
        db: Session,
        case_id: str,
        outcome: DecisionOutcome,
        reviewer: str,
        notes: str,
        accepted_quantity: Optional[int] = None,
        verified_damaged_quantity: Optional[int] = None,
    ) -> DecisionRecordModel:
        latest = (
            db.query(DecisionRecordModel)
            .filter(DecisionRecordModel.case_id == case_id)
            .order_by(DecisionRecordModel.decided_at.desc())
            .first()
        )
        ordered_q = latest.ordered_quantity if latest else 0
        delivered_q = latest.delivered_quantity if latest else 0
        dmg_q = verified_damaged_quantity if verified_damaged_quantity is not None else (latest.verified_damaged_quantity if latest else 0)
        acc_q = accepted_quantity if accepted_quantity is not None else max(0, delivered_q - dmg_q)
        disp_q = max(0, ordered_q - acc_q)

        from core.schemas import new_id

        override_rec = DecisionRecordModel(
            id=new_id("dec"),
            case_id=case_id,
            outcome=outcome.value,
            epistemic_status=EpistemologicalType.RULE.value,
            overall_confidence=1.0,
            ordered_quantity=ordered_q,
            delivered_quantity=delivered_q,
            verified_damaged_quantity=dmg_q,
            accepted_quantity=acc_q,
            disputed_quantity=disp_q,
            recommended_payout_adjustment_usd=latest.recommended_payout_adjustment_usd if latest else 0.0,
            summary_reason=f"Human reviewer ({reviewer}) adjudicated case as {outcome.value.upper()}: {notes}",
            detailed_explanation=(latest.detailed_explanation if latest else [])
            + [f"[HUMAN_REVIEW_OVERRIDE by {reviewer}] {notes}"],
            next_action="Execute human reviewer settlement determination.",
            rule_traces=latest.rule_traces if latest else [],
            supporting_evidence_ids=latest.supporting_evidence_ids if latest else [],
            conflict_ids=latest.conflict_ids if latest else [],
            historical_warning_ids=latest.historical_warning_ids if latest else [],
            is_human_override=True,
            human_reviewer=reviewer,
            human_override_notes=notes,
            decided_at=datetime.now(timezone.utc),
        )
        db.add(override_rec)

        case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
        if case:
            case.status = "human_reviewed"

        db.commit()
        db.refresh(override_rec)

        AuditService.record_event(
            db=db,
            case_id=case_id,
            event_type="HUMAN_REVIEW_OVERRIDE",
            stage="human_review",
            actor=reviewer,
            details={
                "decision_id": override_rec.id,
                "outcome": outcome.value,
                "reviewer": reviewer,
                "notes": notes,
                "accepted_quantity": acc_q,
                "verified_damaged_quantity": dmg_q,
            },
        )
        return override_rec


class CaseVerificationPipeline:
    """Orchestrates the complete EvidenceOS 12-stage pipeline for a case."""

    def __init__(self, extractor: Optional[MultimodalExtractionService] = None) -> None:
        self.extractor = extractor or MultimodalExtractionService()

    def run_case_pipeline(
        self,
        db: Session,
        case_id: str,
        use_rule_engine: bool = True,
        enable_historical_matching: bool = True,
        resolver_mode: str = "v1_frozen",
    ) -> Dict[str, Any]:
        import time

        case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
        if not case:
            raise ValueError(f"Case '{case_id}' not found.")

        case.status = "processing"
        db.commit()

        evidence_records = (
            db.query(EvidenceRecordModel)
            .filter(EvidenceRecordModel.case_id == case_id)
            .order_by(EvidenceRecordModel.uploaded_at.asc())
            .all()
        )

        stage_latencies_ms: Dict[str, float] = {
            "pdf_extraction_ms": 0.0,
            "image_analysis_ms": 0.0,
            "voice_analysis_ms": 0.0,
            "normalization_ms": 0.0,
            "entity_resolution_ms": 0.0,
            "conflict_detection_ms": 0.0,
            "historical_matching_ms": 0.0,
            "rule_and_decision_ms": 0.0,
        }

        # Stage 1-3: Extract each evidence artifact
        has_docs = False
        has_images = False
        has_voice = False
        for rec in evidence_records:
            t_ext = time.perf_counter()
            self.extractor.extract_evidence_record(db, rec)
            dt_ext = (time.perf_counter() - t_ext) * 1000.0
            if rec.document_role in ("purchase_order", "delivery_challan", "invoice"):
                has_docs = True
                stage_latencies_ms["pdf_extraction_ms"] += dt_ext
            elif rec.document_role == "inspection_image":
                has_images = True
                stage_latencies_ms["image_analysis_ms"] += dt_ext
            elif rec.document_role == "voice_report":
                has_voice = True
                stage_latencies_ms["voice_analysis_ms"] += dt_ext

        # Stage 4: Evidence Normalization
        t_norm = time.perf_counter()
        claims = EvidenceNormalizationService.normalize_case_evidence(db, case_id, evidence_records)
        stage_latencies_ms["normalization_ms"] = round((time.perf_counter() - t_norm) * 1000.0, 3)

        # Stage 5: Cross-Modal Entity Resolution
        t_ent = time.perf_counter()
        entities = EntityResolutionService.resolve_entities(
            db, case_id, evidence_records, claims, resolver_mode=resolver_mode
        )
        stage_latencies_ms["entity_resolution_ms"] = round((time.perf_counter() - t_ent) * 1000.0, 3)

        # Stage 6: Conflict Detection & Historical Matching
        t_conf = time.perf_counter()
        conflicts = ConflictDetectionService.detect_conflicts(db, case_id, entities)
        stage_latencies_ms["conflict_detection_ms"] = round((time.perf_counter() - t_conf) * 1000.0, 3)

        t_hist = time.perf_counter()
        if enable_historical_matching:
            historical_warnings = HistoricalMatchingService.match_against_historical_cases(
                db, case_id, evidence_records
            )
        else:
            historical_warnings = []
        stage_latencies_ms["historical_matching_ms"] = round((time.perf_counter() - t_hist) * 1000.0, 3)

        # Stage 7: Deterministic Rule & Decision Engine
        t_dec = time.perf_counter()
        decision = DecisionEngineService.compute_decision(
            db=db,
            case_id=case_id,
            entities=entities,
            conflicts=conflicts,
            historical_warnings=historical_warnings,
            contract_config=case.contract_sla_config or {},
            use_rule_engine=use_rule_engine,
        )
        stage_latencies_ms["rule_and_decision_ms"] = round((time.perf_counter() - t_dec) * 1000.0, 3)
        for k in ("pdf_extraction_ms", "image_analysis_ms", "voice_analysis_ms"):
            stage_latencies_ms[k] = round(stage_latencies_ms[k], 3)

        # Update Case checklist and header metadata from PO if not already set
        for rec in evidence_records:
            payload = rec.extracted_payload or {}
            if rec.document_role == "purchase_order":
                if not case.po_number and payload.get("document_id"):
                    case.po_number = payload["document_id"]
                if not case.supplier_name and payload.get("supplier"):
                    case.supplier_name = payload["supplier"]
                if not case.buyer_name and payload.get("buyer"):
                    case.buyer_name = payload["buyer"]

        case.pipeline_Checklist = {
            "evidence_received": len(evidence_records) > 0,
            "documents_processed": has_docs,
            "images_analyzed": has_images,
            "voice_analyzed": has_voice,
            "evidence_linked": len(entities) > 0,
            "conflicts_detected": len(conflicts) > 0 or len(historical_warnings) > 0,
            "rules_evaluated": len(decision.rule_traces) > 0,
            "decision": decision.outcome.value,
        }
        case.status = "decided"
        db.commit()
        db.refresh(case)

        return {
            "case_id": case.id,
            "status": case.status,
            "checklist": case.pipeline_Checklist,
            "claims_count": len(claims),
            "entities_count": len(entities),
            "conflicts_count": len(conflicts),
            "conflicts": [c.model_dump(mode="json") for c in conflicts],
            "historical_warnings_count": len(historical_warnings),
            "historical_warnings": [w.model_dump(mode="json") for w in historical_warnings],
            "stage_latencies_ms": stage_latencies_ms,
            "decision": decision.model_dump(mode="json"),
        }
