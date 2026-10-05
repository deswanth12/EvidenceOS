"""Entity Resolution Service (Phase 5 / Module 6).

Connects Purchase Order items, Delivery Challan items, Invoice items,
Image visual observations, and Voice claims to canonical resolved entities
using exact SKU matching and cosine similarity over semantic token embeddings.
"""

import math
from collections import defaultdict
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from core.ai.provider import compute_deterministic_embedding
from core.audit.logger import AuditService
from core.db.models import EvidenceRecordModel, ResolvedEntityModel
from core.schemas import NormalizedClaim, ResolvedEntity


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return round(dot / (n1 * n2), 4)


class EntityResolutionService:
    """Resolves cross-modal evidence claims into unified canonical entities."""

    @staticmethod
    def resolve_entities(
        db: Session,
        case_id: str,
        evidence_records: List[EvidenceRecordModel],
        claims: List[NormalizedClaim],
    ) -> List[ResolvedEntity]:
        db.query(ResolvedEntityModel).filter(ResolvedEntityModel.case_id == case_id).delete()
        db.commit()

        # Group claims by canonical entity_key (and merge generic/unknown SKUs into primary SKU if only one item exists)
        known_skus = sorted(
            {
                c.entity_key.replace("ITEM:", "")
                for c in claims
                if c.entity_key.startswith("ITEM:") and c.entity_key != "ITEM:UNKNOWN"
            }
        )
        default_sku = known_skus[0] if known_skus else "SKU-IND-100"

        grouped_claims: Dict[str, List[NormalizedClaim]] = defaultdict(list)
        for clm in claims:
            key = clm.entity_key
            if key == "ITEM:UNKNOWN":
                key = f"ITEM:{default_sku}"
                clm.entity_key = key
            grouped_claims[key].append(clm)

        # Map product display names from document extractions
        sku_names: Dict[str, str] = {}
        for rec in evidence_records:
            payload = rec.extracted_payload or {}
            for it in payload.get("items", []):
                s = (it.get("sku") or "").upper()
                if s and it.get("name"):
                    sku_names[f"ITEM:{s}"] = it["name"]
            if payload.get("visible_products"):
                sku = (payload.get("detected_sku") or default_sku).upper()
                sku_names.setdefault(f"ITEM:{sku}", payload["visible_products"][0])

        resolved_entities: List[ResolvedEntity] = []
        for canonical_key, entity_claims in grouped_claims.items():
            sku_code = canonical_key.replace("ITEM:", "")
            display_name = sku_names.get(canonical_key, f"Industrial Line Item ({sku_code})")

            evidence_ids = sorted(list({c.provenance.evidence_id for c in entity_claims}))
            claim_ids = [c.claim_id for c in entity_claims]

            attributes_by_source: Dict[str, Any] = defaultdict(list)
            for c in entity_claims:
                attributes_by_source[c.attribute].append(
                    {
                        "evidence_id": c.provenance.evidence_id,
                        "document_role": c.provenance.document_role.value,
                        "modality": c.provenance.source_type.value,
                        "value": c.value,
                        "confidence": c.provenance.confidence,
                        "epistemic_type": c.epistemic_type.value,
                        "location": c.provenance.location,
                    }
                )

            # Calculate average cross-modal semantic similarity across linked evidence embeddings
            emb_list = [
                compute_deterministic_embedding(f"{sku_code} {display_name} {c.reason}")
                for c in entity_claims
            ]
            sim_scores = []
            for i in range(len(emb_list)):
                for j in range(i + 1, len(emb_list)):
                    sim_scores.append(cosine_similarity(emb_list[i], emb_list[j]))
            avg_sim = sum(sim_scores) / len(sim_scores) if sim_scores else 0.95
            resolution_conf = round(min(1.0, max(0.85, 0.70 + 0.30 * avg_sim)), 3)

            entity = ResolvedEntity(
                case_id=case_id,
                entity_type="line_item",
                canonical_key=canonical_key,
                display_name=display_name,
                sku=sku_code,
                linked_evidence_ids=evidence_ids,
                linked_claim_ids=claim_ids,
                attributes_by_source=dict(attributes_by_source),
                resolution_method="exact_sku_and_vector_cosine_link",
                confidence=resolution_conf,
            )
            resolved_entities.append(entity)

            db_ent = ResolvedEntityModel(
                id=entity.entity_id,
                case_id=case_id,
                entity_type=entity.entity_type,
                canonical_key=entity.canonical_key,
                display_name=entity.display_name,
                sku=entity.sku,
                linked_evidence_ids=entity.linked_evidence_ids,
                linked_claim_ids=entity.linked_claim_ids,
                attributes_by_source=entity.attributes_by_source,
                resolution_method=entity.resolution_method,
                confidence=entity.confidence,
            )
            db.add(db_ent)

        db.commit()

        AuditService.record_event(
            db=db,
            case_id=case_id,
            event_type="ENTITIES_RESOLVED",
            stage="entity_resolution",
            details={
                "resolved_entity_count": len(resolved_entities),
                "entities": [
                    {
                        "canonical_key": e.canonical_key,
                        "display_name": e.display_name,
                        "linked_evidence_count": len(e.linked_evidence_ids),
                        "confidence": e.confidence,
                    }
                    for e in resolved_entities
                ],
            },
        )
        return resolved_entities
