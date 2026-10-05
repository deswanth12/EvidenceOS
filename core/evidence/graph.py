"""Evidence Graph Builder (Phase 5 / Module 7).

Constructs a directed provenance and relationship graph connecting:
Case -> Shipment / Evidence Documents -> Resolved Line Items -> Extracted Claims -> Conflicts -> Decision.
"""

from typing import List, Optional

from core.db.models import EvidenceRecordModel
from core.schemas import (
    CaseDecision,
    EpistemologicalType,
    EvidenceConflict,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    NormalizedClaim,
    ResolvedEntity,
)


class EvidenceGraphBuilder:
    """Builds a serializable graph representation of all evidence, entities, claims, conflicts, and decisions."""

    @staticmethod
    def build_graph(
        case_id: str,
        case_title: str,
        evidence_records: List[EvidenceRecordModel],
        entities: List[ResolvedEntity],
        claims: List[NormalizedClaim],
        conflicts: List[EvidenceConflict],
        decision: Optional[CaseDecision] = None,
    ) -> EvidenceGraph:
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        # Root Shipment / Case node
        shipment_node_id = f"shipment_{case_id}"
        nodes.append(
            GraphNode(
                id=shipment_node_id,
                label=f"Shipment Case: {case_title}",
                node_type="case",
                epistemic_type=EpistemologicalType.FACT,
                metadata={"case_id": case_id},
            )
        )

        # Evidence nodes
        for rec in evidence_records:
            nodes.append(
                GraphNode(
                    id=rec.id,
                    label=f"{rec.document_role.replace('_', ' ').title()} ({rec.original_filename})",
                    node_type="evidence",
                    epistemic_type=EpistemologicalType.FACT,
                    metadata={
                        "modality": rec.modality,
                        "document_role": rec.document_role,
                        "sha256_hash": rec.sha256_hash[:12],
                        "perceptual_hash": rec.perceptual_hash,
                        "filename": rec.original_filename,
                    },
                )
            )
            edges.append(
                GraphEdge(
                    source=rec.id,
                    target=shipment_node_id,
                    relation="REFERS_TO_SHIPMENT",
                )
            )

        # Resolved Entity nodes
        entity_by_key = {}
        for ent in entities:
            entity_by_key[ent.canonical_key] = ent.entity_id
            nodes.append(
                GraphNode(
                    id=ent.entity_id,
                    label=f"{ent.display_name} [{ent.sku}]",
                    node_type="entity",
                    epistemic_type=EpistemologicalType.INFERENCE,
                    metadata={
                        "canonical_key": ent.canonical_key,
                        "sku": ent.sku,
                        "confidence": ent.confidence,
                    },
                )
            )
            edges.append(
                GraphEdge(
                    source=shipment_node_id,
                    target=ent.entity_id,
                    relation="CONTAINS_ITEM",
                )
            )
            for ev_id in ent.linked_evidence_ids:
                edges.append(
                    GraphEdge(
                        source=ev_id,
                        target=ent.entity_id,
                        relation="EVIDENCES_ITEM",
                    )
                )

        # Claim nodes
        for clm in claims:
            nodes.append(
                GraphNode(
                    id=clm.claim_id,
                    label=f"{clm.attribute}: {clm.value} ({clm.provenance.document_role.value})",
                    node_type="claim",
                    epistemic_type=clm.epistemic_type,
                    metadata={
                        "attribute": clm.attribute,
                        "value": clm.value,
                        "reason": clm.reason,
                        "confidence": clm.provenance.confidence,
                        "evidence_id": clm.provenance.evidence_id,
                    },
                )
            )
            edges.append(
                GraphEdge(
                    source=clm.provenance.evidence_id,
                    target=clm.claim_id,
                    relation="EXTRACTED_CLAIM",
                )
            )
            target_ent_id = entity_by_key.get(clm.entity_key)
            if target_ent_id:
                edges.append(
                    GraphEdge(
                        source=clm.claim_id,
                        target=target_ent_id,
                        relation="DESCRIBES_ENTITY",
                    )
                )

        # Conflict nodes
        for cnf in conflicts:
            nodes.append(
                GraphNode(
                    id=cnf.conflict_id,
                    label=f"Conflict: {cnf.conflict_type}",
                    node_type="conflict",
                    epistemic_type=EpistemologicalType.UNCERTAINTY,
                    metadata={
                        "severity": cnf.severity.value,
                        "description": cnf.description,
                        "competing_values": cnf.competing_values,
                    },
                )
            )
            target_ent_id = entity_by_key.get(cnf.entity_key)
            if target_ent_id:
                edges.append(
                    GraphEdge(
                        source=cnf.conflict_id,
                        target=target_ent_id,
                        relation="CONTRADICTION_ON_ENTITY",
                    )
                )
            for comp in cnf.competing_values:
                ev_id = comp.get("evidence_id")
                if ev_id:
                    edges.append(
                        GraphEdge(
                            source=ev_id,
                            target=cnf.conflict_id,
                            relation="CONFLICTING_SOURCE",
                        )
                    )

        # Decision node
        if decision:
            nodes.append(
                GraphNode(
                    id=decision.decision_id,
                    label=f"Decision: {decision.outcome.value.upper()}",
                    node_type="decision",
                    epistemic_type=decision.epistemic_status,
                    metadata={
                        "outcome": decision.outcome.value,
                        "confidence": decision.overall_confidence,
                        "summary_reason": decision.summary_reason,
                    },
                )
            )
            edges.append(
                GraphEdge(
                    source=shipment_node_id,
                    target=decision.decision_id,
                    relation="RESOLVED_BY_DECISION",
                )
            )
            for cnf in conflicts:
                edges.append(
                    GraphEdge(
                        source=cnf.conflict_id,
                        target=decision.decision_id,
                        relation="INFLUENCES_DECISION",
                    )
                )

        return EvidenceGraph(case_id=case_id, nodes=nodes, edges=edges)
