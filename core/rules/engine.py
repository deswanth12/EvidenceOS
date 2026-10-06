"""Deterministic Contract & SLA Rule Engine (Phase 7 / Module 10).

Separation Principle:
AI extracts, classifies, and links evidence.
Deterministic Python code performs ALL arithmetic, contract threshold checks,
corroboration checks, and SLA evaluations. No LLM is ever allowed to compute
settlement quantities or override contract rules.
"""

from typing import Any, Dict, List, Tuple

from core.config import get_settings
from core.schemas import (
    EpistemologicalType,
    EvidenceConflict,
    HistoricalMatchWarning,
    ResolvedEntity,
    RuleEvaluationTrace,
)


class DeterministicRuleEngine:
    """Evaluates explicit B2B procurement and delivery rules with full rule traces."""

    @staticmethod
    def evaluate_rules(
        entities: List[ResolvedEntity],
        conflicts: List[EvidenceConflict],
        historical_warnings: List[HistoricalMatchWarning],
        contract_config: Dict[str, Any],
    ) -> Tuple[List[RuleEvaluationTrace], Dict[str, Any]]:
        settings = get_settings()
        max_damage_ratio = float(
            contract_config.get("max_auto_approve_damage_ratio", settings.sla_max_auto_approve_damage_ratio)
        )
        min_confidence = float(
            contract_config.get("min_confidence_threshold", settings.sla_min_confidence_threshold)
        )

        traces: List[RuleEvaluationTrace] = []

        # Aggregate quantities across resolved line items
        ordered_qty = 0
        delivered_qty = 0
        has_po = False
        has_challan = False
        unit_price = 250.0
        image_damaged_qty = None
        voice_damaged_qty = None
        challan_damaged_qty = 0
        has_uncertain_evidence = False
        min_observed_conf = 1.0
        all_evidence_ids: List[str] = []

        for ent in entities:
            all_evidence_ids.extend(ent.linked_evidence_ids)
            attrs = ent.attributes_by_source

            for rel in attrs.get("document_relevance", []):
                min_observed_conf = min(min_observed_conf, float(rel.get("confidence", 0.25)))
                if rel.get("epistemic_type") == "UNCERTAINTY":
                    has_uncertain_evidence = True

            for o in attrs.get("ordered_quantity", []):
                has_po = True
                if isinstance(o.get("value"), int):
                    ordered_qty += o["value"]
                min_observed_conf = min(min_observed_conf, float(o.get("confidence", 1.0)))

            for d in attrs.get("delivered_quantity", []):
                has_challan = True
                if isinstance(d.get("value"), int):
                    delivered_qty += d["value"]
                min_observed_conf = min(min_observed_conf, float(d.get("confidence", 1.0)))

            for p in attrs.get("unit_price", []):
                if isinstance(p.get("value"), (int, float)):
                    unit_price = float(p["value"])

            for dm in attrs.get("damaged_quantity", []):
                min_observed_conf = min(min_observed_conf, float(dm.get("confidence", 1.0)))
                if dm.get("epistemic_type") == "UNCERTAINTY" or dm.get("value") is None:
                    has_uncertain_evidence = True
                else:
                    role = dm.get("document_role")
                    val = int(dm["value"])
                    if role == "inspection_image":
                        image_damaged_qty = val if image_damaged_qty is None else max(image_damaged_qty, val)
                    elif role == "voice_report":
                        voice_damaged_qty = val if voice_damaged_qty is None else max(voice_damaged_qty, val)
                    elif role == "delivery_challan":
                        challan_damaged_qty = max(challan_damaged_qty, val)

        all_evidence_ids = sorted(list(set(all_evidence_ids)))

        # RULE 1: Minimum Evidence Sufficiency & Confidence Check
        has_po_and_challan = has_po and has_challan and ordered_qty > 0 and delivered_qty > 0
        rule1_passed = has_po_and_challan and (not has_uncertain_evidence) and (min_observed_conf >= min_confidence)
        traces.append(
            RuleEvaluationTrace(
                rule_id="RULE_01_EVIDENCE_SUFFICIENCY",
                rule_name="Evidence Completeness & Confidence Threshold",
                passed=rule1_passed,
                epistemic_type=EpistemologicalType.RULE,
                inputs_used={
                    "has_purchase_order": has_po,
                    "has_delivery_challan": has_challan,
                    "ordered_quantity": ordered_qty,
                    "delivered_quantity": delivered_qty,
                    "min_observed_confidence": round(min_observed_conf, 3),
                    "required_min_confidence": min_confidence,
                    "has_uncertain_evidence": has_uncertain_evidence,
                },
                evidence_ids=all_evidence_ids,
                explanation=(
                    f"All primary evidence sources meet the minimum confidence threshold ({min_observed_conf:.2f} >= {min_confidence:.2f})."
                    if rule1_passed
                    else f"Evidence sufficiency check failed: observed minimum confidence {min_observed_conf:.2f} (threshold {min_confidence:.2f}), missing primary document, or inconclusive visual evidence."
                ),
            )
        )

        # RULE 2: Ordered vs Delivered Quantity Reconciliation
        rule2_passed = has_po and has_challan and ordered_qty > 0 and ordered_qty == delivered_qty
        traces.append(
            RuleEvaluationTrace(
                rule_id="RULE_02_DELIVERY_COMPLETENESS",
                rule_name="Purchase Order vs. Delivery Challan Quantity Match",
                passed=rule2_passed,
                epistemic_type=EpistemologicalType.RULE,
                inputs_used={
                    "ordered_quantity": ordered_qty,
                    "delivered_quantity": delivered_qty,
                    "shortage_quantity": max(0, ordered_qty - delivered_qty),
                },
                evidence_ids=all_evidence_ids,
                explanation=(
                    f"Delivered quantity ({delivered_qty} units) matches Purchase Order quantity ({ordered_qty} units)."
                    if rule2_passed
                    else f"Delivery discrepancy: Ordered {ordered_qty} units, but Delivery Challan reports {delivered_qty} units."
                ),
            )
        )

        # RULE 3: Cross-Modal Damage Corroboration
        # If damage is claimed (>0), visual evidence and voice/document evidence must agree without conflict
        claimed_candidates = [
            v for v in [image_damaged_qty, voice_damaged_qty, challan_damaged_qty] if v is not None and v > 0
        ]
        max_claimed_damage = max(claimed_candidates) if claimed_candidates else 0

        if max_claimed_damage == 0:
            verified_damaged_qty = 0
            rule3_passed = not has_uncertain_evidence
            rule3_expl = "Zero damaged units reported across all documents, images, and voice logs."
        else:
            has_corroborator = (
                (voice_damaged_qty is not None and voice_damaged_qty == image_damaged_qty)
                or (challan_damaged_qty > 0 and challan_damaged_qty == image_damaged_qty)
            )
            if (
                image_damaged_qty is not None
                and image_damaged_qty > 0
                and has_corroborator
                and (voice_damaged_qty is None or voice_damaged_qty == image_damaged_qty)
                and (challan_damaged_qty == 0 or challan_damaged_qty == image_damaged_qty)
                and not has_uncertain_evidence
            ):
                verified_damaged_qty = image_damaged_qty
                rule3_passed = True
                rule3_expl = (
                    f"Physical damage of {verified_damaged_qty} units is corroborated across visual inspection "
                    f"and receiving reports."
                )
            else:
                verified_damaged_qty = image_damaged_qty or 0
                rule3_passed = False
                rule3_expl = (
                    f"Unresolved discrepancy or missing corroboration on damaged units "
                    f"(Image={image_damaged_qty}, Voice={voice_damaged_qty}, Challan={challan_damaged_qty})."
                )

        traces.append(
            RuleEvaluationTrace(
                rule_id="RULE_03_CROSS_MODAL_DAMAGE_CORROBORATION",
                rule_name="Multi-Modal Physical Damage Corroboration",
                passed=rule3_passed,
                epistemic_type=EpistemologicalType.RULE,
                inputs_used={
                    "image_damaged_quantity": image_damaged_qty,
                    "voice_damaged_quantity": voice_damaged_qty,
                    "challan_damaged_quantity": challan_damaged_qty,
                    "verified_damaged_quantity": verified_damaged_qty,
                },
                evidence_ids=all_evidence_ids,
                explanation=rule3_expl,
            )
        )

        # RULE 4: Contract SLA Damage Ratio Threshold
        damage_ratio = (verified_damaged_qty / ordered_qty) if ordered_qty > 0 else 0.0
        rule4_passed = damage_ratio <= max_damage_ratio
        traces.append(
            RuleEvaluationTrace(
                rule_id="RULE_04_CONTRACT_SLA_THRESHOLD",
                rule_name="Contract SLA Maximum Auto-Approval Damage Ratio",
                passed=rule4_passed,
                epistemic_type=EpistemologicalType.RULE,
                inputs_used={
                    "verified_damaged_quantity": verified_damaged_qty,
                    "ordered_quantity": ordered_qty,
                    "damage_ratio": round(damage_ratio, 4),
                    "sla_max_damage_ratio": max_damage_ratio,
                },
                evidence_ids=all_evidence_ids,
                explanation=(
                    f"Damage ratio ({damage_ratio * 100:.1f}%) is within contract auto-settlement threshold ({max_damage_ratio * 100:.1f}%)."
                    if rule4_passed
                    else f"Damage ratio ({damage_ratio * 100:.1f}%) exceeds contract auto-settlement threshold ({max_damage_ratio * 100:.1f}%)."
                ),
            )
        )

        # RULE 5: Historical Evidence Uniqueness Check
        rule5_passed = len(historical_warnings) == 0
        traces.append(
            RuleEvaluationTrace(
                rule_id="RULE_05_HISTORICAL_EVIDENCE_UNIQUENESS",
                rule_name="Cryptographic & Perceptual Historical Uniqueness Check",
                passed=rule5_passed,
                epistemic_type=EpistemologicalType.RULE,
                inputs_used={
                    "historical_warning_count": len(historical_warnings),
                    "warning_ids": [w.match_id for w in historical_warnings],
                },
                evidence_ids=all_evidence_ids,
                explanation=(
                    "No reused or perceptually duplicate evidence found across historical dispute cases."
                    if rule5_passed
                    else f"Potentially reused evidence detected ({len(historical_warnings)} match(es) against prior cases)."
                ),
            )
        )

        accepted_qty = max(0, delivered_qty - verified_damaged_qty)
        disputed_qty = max(0, ordered_qty - accepted_qty)
        payout_adjustment = round(disputed_qty * unit_price, 2)

        computed_metrics = {
            "ordered_quantity": ordered_qty,
            "delivered_quantity": delivered_qty,
            "verified_damaged_quantity": verified_damaged_qty,
            "max_claimed_damage": max_claimed_damage,
            "accepted_quantity": accepted_qty,
            "disputed_quantity": disputed_qty,
            "unit_price": unit_price,
            "recommended_payout_adjustment_usd": payout_adjustment,
            "min_observed_confidence": round(min_observed_conf, 3),
            "has_uncertain_evidence": has_uncertain_evidence,
            "all_evidence_ids": all_evidence_ids,
        }
        return traces, computed_metrics
