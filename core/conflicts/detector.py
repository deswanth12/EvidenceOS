"""Conflict Detection Engine (Phase 6 / Module 8).

Detects and surfaces contradictions across Purchase Orders, Delivery Challans,
Inspection Images, and Voice Reports:
1. Ordered vs Delivered quantity shortages (`SHORT_DELIVERY_MISMATCH`)
2. Damage quantity contradictions across modalities (`DAMAGE_QUANTITY_CONTRADICTION`)
   e.g., Voice claims 5 damaged vs Image supports 2 damaged vs Challan states 0
3. Visually inconclusive / weak evidence where a claim is asserted (`UNCORROBORATED_CLAIM`)
"""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from core.audit.logger import AuditService
from core.db.models import ConflictRecordModel
from core.schemas import (
    ConflictSeverity,
    EpistemologicalType,
    EvidenceConflict,
    ResolvedEntity,
)


class ConflictDetectionService:
    """Identifies cross-modal contradictions and records them with full provenance."""

    @staticmethod
    def detect_conflicts(
        db: Session,
        case_id: str,
        entities: List[ResolvedEntity],
    ) -> List[EvidenceConflict]:
        db.query(ConflictRecordModel).filter(ConflictRecordModel.case_id == case_id).delete()
        db.commit()

        conflicts: List[EvidenceConflict] = []

        for ent in entities:
            attrs = ent.attributes_by_source
            ordered_list: List[Dict[str, Any]] = attrs.get("ordered_quantity", [])
            delivered_list: List[Dict[str, Any]] = attrs.get("delivered_quantity", [])
            damaged_list: List[Dict[str, Any]] = attrs.get("damaged_quantity", [])

            # 1. Check Ordered vs Delivered discrepancy (e.g., PO says 10 units, Challan says 8 units)
            if ordered_list and delivered_list:
                ord_val = ordered_list[0].get("value")
                del_val = delivered_list[0].get("value")
                if isinstance(ord_val, int) and isinstance(del_val, int) and ord_val != del_val:
                    competing = [
                        {
                            "evidence_id": ordered_list[0]["evidence_id"],
                            "document_role": ordered_list[0]["document_role"],
                            "attribute": "ordered_quantity",
                            "value": ord_val,
                            "confidence": ordered_list[0]["confidence"],
                            "location": ordered_list[0].get("location"),
                        },
                        {
                            "evidence_id": delivered_list[0]["evidence_id"],
                            "document_role": delivered_list[0]["document_role"],
                            "attribute": "delivered_quantity",
                            "value": del_val,
                            "confidence": delivered_list[0]["confidence"],
                            "location": delivered_list[0].get("location"),
                        },
                    ]
                    conflicts.append(
                        EvidenceConflict(
                            case_id=case_id,
                            conflict_type="SHORT_DELIVERY_MISMATCH",
                            severity=ConflictSeverity.HIGH,
                            entity_key=ent.canonical_key,
                            attribute="delivered_vs_ordered_quantity",
                            description=(
                                f"Quantity discrepancy for {ent.canonical_key}: "
                                f"Purchase Order specifies {ord_val} units, whereas Delivery Challan reports {del_val} units delivered."
                            ),
                            competing_values=competing,
                            epistemic_type=EpistemologicalType.UNCERTAINTY,
                        )
                    )

            # 2. Check Damaged Quantity contradictions across modalities
            if damaged_list:
                concrete_dmg = [d for d in damaged_list if isinstance(d.get("value"), int)]
                uncertain_dmg = [d for d in damaged_list if d.get("value") is None or d.get("epistemic_type") == "UNCERTAINTY"]

                # Check if someone claims > 0 damage while image/other source is UNCERTAIN / weak
                positive_claims = [d for d in concrete_dmg if (d.get("value") or 0) > 0]
                if positive_claims and uncertain_dmg:
                    competing = positive_claims + uncertain_dmg
                    conflicts.append(
                        EvidenceConflict(
                            case_id=case_id,
                            conflict_type="INSUFFICIENT_VISUAL_CORROBORATION",
                            severity=ConflictSeverity.HIGH,
                            entity_key=ent.canonical_key,
                            attribute="damaged_quantity",
                            description=(
                                f"Damage claim of {positive_claims[0]['value']} units ({positive_claims[0]['document_role']}) "
                                f"cannot be corroborated because visual evidence ({uncertain_dmg[0]['evidence_id']}) is inconclusive or low-confidence."
                            ),
                            competing_values=competing,
                            epistemic_type=EpistemologicalType.UNCERTAINTY,
                        )
                    )

                # Check if concrete damaged quantities disagree across sources
                # Note: A clean delivery challan generated at dispatch often has 0 damaged, while unloading inspection
                # image + voice both report 2 damaged. If Image and Voice AGREE on damage > 0, and Challan is 0,
                # only flag a conflict if Image and Voice disagree with each other OR if Challan also claims a different non-zero number,
                # OR if Voice claims damage but Image says 0.
                by_role: Dict[str, List[Dict[str, Any]]] = {}
                for d in concrete_dmg:
                    by_role.setdefault(d["document_role"], []).append(d)

                img_vals = [d["value"] for d in by_role.get("inspection_image", [])]
                voice_vals = [d["value"] for d in by_role.get("voice_report", [])]
                challan_vals = [d["value"] for d in by_role.get("delivery_challan", [])]

                # Case A: Voice and Image directly disagree (e.g., Voice says 5 damaged, Image supports 2 damaged)
                if img_vals and voice_vals and set(img_vals) != set(voice_vals):
                    conflicts.append(
                        EvidenceConflict(
                            case_id=case_id,
                            conflict_type="DAMAGE_QUANTITY_CONTRADICTION",
                            severity=ConflictSeverity.CRITICAL,
                            entity_key=ent.canonical_key,
                            attribute="damaged_quantity",
                            description=(
                                f"Cross-modal damage contradiction for {ent.canonical_key}: "
                                f"Voice report claims {voice_vals[0]} damaged units, whereas visual inspection image supports {img_vals[0]} damaged units."
                            ),
                            competing_values=concrete_dmg,
                            epistemic_type=EpistemologicalType.UNCERTAINTY,
                        )
                    )
                # Case B: Challan reports non-zero damage that disagrees with Image or Voice
                elif challan_vals and challan_vals[0] > 0:
                    other_vals = set(img_vals + voice_vals)
                    if other_vals and challan_vals[0] not in other_vals:
                        conflicts.append(
                            EvidenceConflict(
                                case_id=case_id,
                                conflict_type="DAMAGE_QUANTITY_CONTRADICTION",
                                severity=ConflictSeverity.HIGH,
                                entity_key=ent.canonical_key,
                                attribute="damaged_quantity",
                                description=(
                                    f"Delivery Challan reports {challan_vals[0]} damaged units, conflicting with inspection evidence ({sorted(list(other_vals))})."
                                ),
                                competing_values=concrete_dmg,
                                epistemic_type=EpistemologicalType.UNCERTAINTY,
                            )
                        )
                # Case C: Voice claims damage > 0, but no inspection image exists at all
                elif voice_vals and voice_vals[0] > 0 and not img_vals and not uncertain_dmg:
                    conflicts.append(
                        EvidenceConflict(
                            case_id=case_id,
                            conflict_type="UNCORROBORATED_VOICE_CLAIM",
                            severity=ConflictSeverity.HIGH,
                            entity_key=ent.canonical_key,
                            attribute="damaged_quantity",
                            description=(
                                f"Voice report claims {voice_vals[0]} damaged units for {ent.canonical_key}, "
                                "but no photographic evidence was provided to corroborate physical damage."
                            ),
                            competing_values=concrete_dmg,
                            epistemic_type=EpistemologicalType.UNCERTAINTY,
                        )
                    )

        for cnf in conflicts:
            db_cnf = ConflictRecordModel(
                id=cnf.conflict_id,
                case_id=case_id,
                conflict_type=cnf.conflict_type,
                severity=cnf.severity.value,
                entity_key=cnf.entity_key,
                attribute=cnf.attribute,
                description=cnf.description,
                competing_values=cnf.competing_values,
                epistemic_type=cnf.epistemic_type.value,
                detected_at=cnf.detected_at,
            )
            db.add(db_cnf)

        db.commit()

        AuditService.record_event(
            db=db,
            case_id=case_id,
            event_type="CONFLICTS_ANALYZED",
            stage="conflict_detection",
            details={
                "conflict_count": len(conflicts),
                "conflict_types": [c.conflict_type for c in conflicts],
            },
        )
        return conflicts
