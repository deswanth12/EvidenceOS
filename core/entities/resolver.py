"""Entity Resolution Service (Phase 5 / Module 6).

Connects Purchase Order items, Delivery Challan items, Invoice items,
Image visual observations, and Voice claims to canonical resolved entities
using exact SKU matching and cosine similarity over semantic token embeddings.
"""

import math
import re
from collections import defaultdict
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from core.ai.provider import compute_deterministic_embedding
from core.audit.logger import AuditService
from core.db.models import EvidenceRecordModel, ResolvedEntityModel
from core.schemas import EpistemologicalType, NormalizedClaim, ResolvedEntity


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return round(dot / (n1 * n2), 4)


def _normalize_ocr_sku(raw_sku: str) -> str:
    """Normalize common OCR character confusions inside SKU codes (e.g. SKU_1ND_2O2 -> SKU-IND-202)."""
    s = re.sub(r"[\s_]+", "-", raw_sku.strip().upper())
    parts = s.split("-")
    norm_parts: List[str] = []
    for idx, p in enumerate(parts):
        if idx == 1 and p in ("1ND", "LND", "I0D"):
            norm_parts.append("IND")
        elif idx >= 2:
            # In numeric SKU suffix segments, replace O->0, I/L->1, S->5
            fixed = (
                p.replace("O", "0")
                .replace("I", "1")
                .replace("L", "1")
            )
            norm_parts.append(fixed)
        else:
            norm_parts.append(p)
    return "-".join(norm_parts)


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


class EntityResolutionService:
    """Resolves cross-modal evidence claims into unified canonical entities."""

    @staticmethod
    def resolve_entities(
        db: Session,
        case_id: str,
        evidence_records: List[EvidenceRecordModel],
        claims: List[NormalizedClaim],
        resolver_mode: str = "v1_frozen",
    ) -> List[ResolvedEntity]:
        db.query(ResolvedEntityModel).filter(ResolvedEntityModel.case_id == case_id).delete()
        db.commit()

        if resolver_mode == "v2_context_aware":
            # Step 1: Collect canonical PO/Challan SKUs first and canonicalize OCR-corrupted SKU references
            doc_skus = sorted(
                {
                    _normalize_ocr_sku(c.entity_key.replace("ITEM:", ""))
                    for c in claims
                    if c.entity_key.startswith("ITEM:")
                    and c.entity_key != "ITEM:UNKNOWN"
                    and c.provenance.document_role.value in ("purchase_order", "delivery_challan", "invoice")
                }
            )
            for clm in claims:
                if clm.entity_key.startswith("ITEM:") and clm.entity_key != "ITEM:UNKNOWN":
                    raw_s = clm.entity_key.replace("ITEM:", "")
                    norm_s = _normalize_ocr_sku(raw_s)
                    if norm_s in doc_skus:
                        clm.entity_key = f"ITEM:{norm_s}"
                    elif doc_skus:
                        # Check edit distance <= 1 against known document SKUs
                        best_match = min(doc_skus, key=lambda ds: _levenshtein_distance(norm_s, ds))
                        if _levenshtein_distance(norm_s, best_match) <= 1:
                            clm.entity_key = f"ITEM:{best_match}"

        known_skus = sorted(
            {
                c.entity_key.replace("ITEM:", "")
                for c in claims
                if c.entity_key.startswith("ITEM:") and c.entity_key != "ITEM:UNKNOWN"
            }
        )
        default_sku = known_skus[0] if known_skus else "SKU-IND-100"

        # In v2_context_aware mode, determine which known SKUs have positive damage claims in Voice/Challan
        non_image_damaged_skus = sorted(
            {
                c.entity_key.replace("ITEM:", "")
                for c in claims
                if c.entity_key.startswith("ITEM:")
                and c.entity_key != "ITEM:UNKNOWN"
                and c.attribute == "damaged_quantity"
                and isinstance(c.value, int)
                and c.value > 0
                and c.provenance.document_role.value in ("voice_report", "delivery_challan")
            }
        )

        grouped_claims: Dict[str, List[NormalizedClaim]] = defaultdict(list)
        for clm in claims:
            key = clm.entity_key
            if key == "ITEM:UNKNOWN":
                if resolver_mode == "v2_context_aware" and len(known_skus) > 1:
                    if len(non_image_damaged_skus) == 1:
                        # Exactly one SKU has a corroborating damage report; link blind visual claim to it
                        target_sku = non_image_damaged_skus[0]
                        key = f"ITEM:{target_sku}"
                        clm.entity_key = key
                    elif len(non_image_damaged_skus) > 1 or (
                        clm.attribute == "damaged_quantity"
                        and isinstance(clm.value, int)
                        and clm.value > 0
                        and len(non_image_damaged_skus) == 0
                    ):
                        # Ambiguous multi-SKU visual damage attribution without barcode or unique corroborator
                        key = f"ITEM:{default_sku}"
                        clm.entity_key = key
                        clm.epistemic_type = EpistemologicalType.UNCERTAINTY
                        clm.provenance.confidence = min(clm.provenance.confidence, 0.55)
                    else:
                        key = f"ITEM:{default_sku}"
                        clm.entity_key = key
                else:
                    key = f"ITEM:{default_sku}"
                    clm.entity_key = key
            grouped_claims[key].append(clm)

        # Map product display names from document extractions
        sku_names: Dict[str, str] = {}
        for rec in evidence_records:
            payload = rec.extracted_payload or {}
            for it in payload.get("items", []):
                s = (it.get("sku") or "").upper()
                if resolver_mode == "v2_context_aware":
                    s = _normalize_ocr_sku(s)
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
            method_name = (
                "context_aware_fuzzy_and_corroborated_sku_link"
                if resolver_mode == "v2_context_aware"
                else "exact_sku_and_vector_cosine_link"
            )

            entity = ResolvedEntity(
                case_id=case_id,
                entity_type="line_item",
                canonical_key=canonical_key,
                display_name=display_name,
                sku=sku_code,
                linked_evidence_ids=evidence_ids,
                linked_claim_ids=claim_ids,
                attributes_by_source=dict(attributes_by_source),
                resolution_method=method_name,
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
