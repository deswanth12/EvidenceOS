"""Evidence Normalization Service (Phase 4 / Module 5).

Converts heterogeneous extracted payloads (Purchase Order, Delivery Challan,
Invoice, Inspection Image, Voice Report) into atomic `NormalizedClaim` objects
that share a common canonical entity and attribute vocabulary, while preserving
exact provenance, confidence, and epistemological status (`FACT` vs `UNCERTAINTY`).
"""

from typing import List

from sqlalchemy.orm import Session

from core.audit.logger import AuditService
from core.db.models import EvidenceRecordModel, NormalizedClaimModel
from core.schemas import (
    DocumentRole,
    EpistemologicalType,
    NormalizedClaim,
    Provenance,
)


class EvidenceNormalizationService:
    """Translates modality-specific extraction payloads into NormalizedClaim records."""

    @staticmethod
    def normalize_case_evidence(
        db: Session,
        case_id: str,
        evidence_records: List[EvidenceRecordModel],
    ) -> List[NormalizedClaim]:
        # Clear prior claims for idempotent re-processing
        db.query(NormalizedClaimModel).filter(NormalizedClaimModel.case_id == case_id).delete()
        db.commit()

        claims: List[NormalizedClaim] = []
        po_dates: List[tuple[str, Provenance, str]] = []
        challan_dates: List[tuple[str, Provenance, str]] = []

        for record in evidence_records:
            payload = record.extracted_payload
            if not payload:
                continue

            prov_dict = payload.get("provenance", {})
            base_prov = Provenance.model_validate(prov_dict)
            role = DocumentRole(record.document_role)

            if role in (DocumentRole.PURCHASE_ORDER, DocumentRole.DELIVERY_CHALLAN, DocumentRole.INVOICE):
                doc_date = payload.get("date")
                items = payload.get("items", [])
                primary_sku = (items[0].get("sku") if items else "SKU-IND-100") or "SKU-IND-100"
                if isinstance(doc_date, str) and len(doc_date) == 10:
                    if role == DocumentRole.PURCHASE_ORDER:
                        po_dates.append((doc_date, base_prov, f"ITEM:{primary_sku.upper()}"))
                    elif role == DocumentRole.DELIVERY_CHALLAN:
                        challan_dates.append((doc_date, base_prov, f"ITEM:{primary_sku.upper()}"))

                for item in items:
                    sku = (item.get("sku") or "SKU-IND-100").upper()
                    entity_key = f"ITEM:{sku}"

                    if role == DocumentRole.PURCHASE_ORDER and item.get("ordered_quantity") is not None:
                        claims.append(
                            NormalizedClaim(
                                case_id=case_id,
                                entity_key=entity_key,
                                attribute="ordered_quantity",
                                value=int(item["ordered_quantity"]),
                                unit="units",
                                epistemic_type=base_prov.epistemic_type,
                                reason=f"Purchase Order {payload.get('document_id')} specifies {item['ordered_quantity']} ordered units for {sku}.",
                                provenance=base_prov,
                            )
                        )
                        if item.get("unit_price") is not None:
                            claims.append(
                                NormalizedClaim(
                                    case_id=case_id,
                                    entity_key=entity_key,
                                    attribute="unit_price",
                                    value=float(item["unit_price"]),
                                    unit=item.get("currency", "USD"),
                                    epistemic_type=base_prov.epistemic_type,
                                    reason=f"Purchase Order {payload.get('document_id')} specifies unit price {item['unit_price']} for {sku}.",
                                    provenance=base_prov,
                                )
                            )

                    if role in (DocumentRole.DELIVERY_CHALLAN, DocumentRole.INVOICE):
                        if item.get("delivered_quantity") is not None:
                            claims.append(
                                NormalizedClaim(
                                    case_id=case_id,
                                    entity_key=entity_key,
                                    attribute="delivered_quantity",
                                    value=int(item["delivered_quantity"]),
                                    unit="units",
                                    epistemic_type=base_prov.epistemic_type,
                                    reason=f"{role.value} {payload.get('document_id')} records {item['delivered_quantity']} delivered units for {sku}.",
                                    provenance=base_prov,
                                )
                            )
                        if item.get("damaged_quantity") is not None:
                            claims.append(
                                NormalizedClaim(
                                    case_id=case_id,
                                    entity_key=entity_key,
                                    attribute="damaged_quantity",
                                    value=int(item["damaged_quantity"]),
                                    unit="units",
                                    epistemic_type=base_prov.epistemic_type,
                                    reason=f"{role.value} {payload.get('document_id')} notes {item['damaged_quantity']} damaged units for {sku}.",
                                    provenance=base_prov,
                                )
                            )

            elif role == DocumentRole.INSPECTION_IMAGE:
                sku = (payload.get("detected_sku") or "UNKNOWN").upper()
                entity_key = f"ITEM:{sku}"
                pkg_cond = payload.get("packaging_condition", "unknown")

                if pkg_cond == "unclear" or base_prov.epistemic_type == EpistemologicalType.UNCERTAINTY:
                    claims.append(
                        NormalizedClaim(
                            case_id=case_id,
                            entity_key=entity_key,
                            attribute="damaged_quantity",
                            value=None,
                            unit="units",
                            epistemic_type=EpistemologicalType.UNCERTAINTY,
                            reason=f"Inspection image ({record.original_filename}) is visually inconclusive: {payload.get('visual_summary')}",
                            provenance=base_prov,
                        )
                    )
                else:
                    dmg_qty = int(payload.get("damaged_quantity", 0))
                    claims.append(
                        NormalizedClaim(
                            case_id=case_id,
                            entity_key=entity_key,
                            attribute="damaged_quantity",
                            value=dmg_qty,
                            unit="units",
                            epistemic_type=EpistemologicalType.FACT,
                            reason=f"Visual inspection of {record.original_filename} shows {dmg_qty} damaged units (packaging: {pkg_cond}).",
                            provenance=base_prov,
                        )
                    )
                    if payload.get("visible_quantity") is not None:
                        claims.append(
                            NormalizedClaim(
                                case_id=case_id,
                                entity_key=entity_key,
                                attribute="visible_quantity",
                                value=int(payload["visible_quantity"]),
                                unit="units",
                                epistemic_type=EpistemologicalType.FACT,
                                reason=f"Visual inspection of {record.original_filename} accounts for {payload['visible_quantity']} total visible units.",
                                provenance=base_prov,
                            )
                        )

            elif role == DocumentRole.VOICE_REPORT:
                sku = (payload.get("sku_mentioned") or "UNKNOWN").upper()
                entity_key = f"ITEM:{sku}"
                claimed_qty = payload.get("claimed_quantity")
                val_to_store = (
                    None
                    if base_prov.epistemic_type == EpistemologicalType.UNCERTAINTY
                    else int(claimed_qty or 0)
                )
                claims.append(
                    NormalizedClaim(
                        case_id=case_id,
                        entity_key=entity_key,
                        attribute="damaged_quantity",
                        value=val_to_store,
                        unit=payload.get("target_object", "units"),
                        epistemic_type=base_prov.epistemic_type,
                        reason=f"Voice report ({record.original_filename}) states {claimed_qty} {payload.get('target_object', 'units')} damaged during {payload.get('event_stage', 'unloading')}.",
                        provenance=base_prov,
                    )
                )

            elif role == DocumentRole.UNKNOWN:
                claims.append(
                    NormalizedClaim(
                        case_id=case_id,
                        entity_key="ITEM:UNKNOWN",
                        attribute="document_relevance",
                        value=None,
                        unit="document",
                        epistemic_type=EpistemologicalType.UNCERTAINTY,
                        reason=f"Uploaded artifact ({record.original_filename}) is unrecognized or irrelevant to procurement dispute verification.",
                        provenance=base_prov,
                    )
                )

        # Check chronological consistency between Purchase Order date and Delivery Challan date
        if po_dates and challan_dates:
            po_date_str, po_prov, po_ent_key = po_dates[0]
            dc_date_str, dc_prov, _ = challan_dates[0]
            if dc_date_str < po_date_str:
                claims.append(
                    NormalizedClaim(
                        case_id=case_id,
                        entity_key=po_ent_key,
                        attribute="timestamp_chronology",
                        value=f"PO:{po_date_str} > DC:{dc_date_str}",
                        unit="date",
                        epistemic_type=EpistemologicalType.UNCERTAINTY,
                        reason=(
                            f"Chronological timestamp conflict: Delivery Challan date ({dc_date_str}) "
                            f"precedes Purchase Order authorization date ({po_date_str})."
                        ),
                        provenance=dc_prov,
                    )
                )

        # Persist claims
        for clm in claims:
            db_clm = NormalizedClaimModel(
                id=clm.claim_id,
                case_id=case_id,
                evidence_id=clm.provenance.evidence_id,
                entity_key=clm.entity_key,
                attribute=clm.attribute,
                value_json=clm.value,
                unit=clm.unit,
                epistemic_type=clm.epistemic_type.value,
                reason=clm.reason,
                provenance_json=clm.provenance.model_dump(mode="json"),
            )
            db.add(db_clm)

        db.commit()

        AuditService.record_event(
            db=db,
            case_id=case_id,
            event_type="EVIDENCE_NORMALIZED",
            stage="normalization",
            details={
                "normalized_claim_count": len(claims),
                "entities_referenced": sorted(list({c.entity_key for c in claims})),
            },
        )
        return claims
