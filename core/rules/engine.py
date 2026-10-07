"""Deterministic Contract & SLA Rule Engine (Phase 7 / Module 10).

Separation Principle:
AI extracts, classifies, and links evidence.
Deterministic Python code performs ALL arithmetic, contract threshold checks,
corroboration checks, and SLA evaluations. No LLM is ever allowed to compute
settlement quantities or override contract rules.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_settings
from core.schemas import (
    EpistemologicalType,
    EvidenceConflict,
    HistoricalMatchWarning,
    ResolvedEntity,
    RuleEvaluationTrace,
)


def _parse_timestamp(val: Any) -> Optional[datetime]:
    """Parse timestamps from ISO strings, unix timestamps, or datetime objects."""
    if isinstance(val, datetime):
        return val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


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
        temperature_telemetry_entries: List[Dict[str, Any]] = []

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

            for tt in attrs.get("temperature_telemetry", []):
                temperature_telemetry_entries.append(tt)
                min_observed_conf = min(min_observed_conf, float(tt.get("confidence", 1.0)))
                if tt.get("epistemic_type") == "UNCERTAINTY":
                    has_uncertain_evidence = True

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

        # RULE 9: Cold-Chain Temperature Excursion Check (R9)
        requires_cold_chain = bool(contract_config.get("requires_cold_chain", False))
        min_temp_celsius = float(contract_config.get("min_temperature_celsius", 2.0))
        max_temp_celsius = float(contract_config.get("max_temperature_celsius", 8.0))
        max_excursion_duration_minutes = float(contract_config.get("max_excursion_duration_minutes", 60.0))
        excursion_mode = str(contract_config.get("excursion_evaluation_mode", "cumulative")).lower()

        # Gather telemetry readings
        readings_raw = []
        if contract_config.get("temperature_telemetry"):
            cf_val = contract_config["temperature_telemetry"]
            if isinstance(cf_val, list):
                readings_raw.extend(cf_val)
            elif isinstance(cf_val, dict) and "readings" in cf_val:
                readings_raw.extend(cf_val["readings"])

        for entry in temperature_telemetry_entries:
            if isinstance(entry, dict) and "readings" in entry:
                readings_raw.extend(entry["readings"])
            elif isinstance(entry, dict) and "value" in entry:
                val = entry.get("value")
                if isinstance(val, list):
                    readings_raw.extend(val)
                elif isinstance(val, dict) and "readings" in val:
                    readings_raw.extend(val["readings"])
                elif isinstance(val, dict):
                    readings_raw.append(val)
            elif isinstance(entry, dict) and ("temperature_celsius" in entry or "temperature_c" in entry):
                readings_raw.append(entry)

        cold_chain_inputs: Dict[str, Any] = {
            "requires_cold_chain": requires_cold_chain,
            "min_temperature_celsius": min_temp_celsius,
            "max_temperature_celsius": max_temp_celsius,
            "max_excursion_duration_minutes": max_excursion_duration_minutes,
            "excursion_evaluation_mode": excursion_mode,
            "telemetry_reading_count": len(readings_raw),
        }

        r9_passed = True
        r9_epistemic_type = EpistemologicalType.RULE
        r9_explanation = ""
        total_excursion_minutes = 0.0
        max_contiguous_excursion_minutes = 0.0
        min_recorded_temp: Optional[float] = None
        max_recorded_temp: Optional[float] = None

        if not requires_cold_chain:
            r9_passed = True
            r9_explanation = "Cold-chain temperature monitoring is not required under current contract SLA."
        else:
            if not readings_raw:
                r9_passed = False
                r9_epistemic_type = EpistemologicalType.UNCERTAINTY
                r9_explanation = "Cold-chain monitoring required by contract SLA, but no temperature logger telemetry was provided."
            else:
                parsed_readings: List[Tuple[datetime, float]] = []
                malformed_data = False
                telemetry_confidence_failed = False

                for r in readings_raw:
                    if not isinstance(r, dict):
                        malformed_data = True
                        break

                    conf = float(r.get("confidence", 1.0))
                    if conf < min_confidence or r.get("epistemic_type") == "UNCERTAINTY":
                        telemetry_confidence_failed = True

                    ts = _parse_timestamp(r.get("timestamp"))
                    temp = r.get("temperature_celsius") if "temperature_celsius" in r else r.get("temperature_c")
                    if ts is None or not isinstance(temp, (int, float)):
                        malformed_data = True
                        break
                    parsed_readings.append((ts, float(temp)))

                if malformed_data or len(parsed_readings) < 2:
                    r9_passed = False
                    r9_epistemic_type = EpistemologicalType.UNCERTAINTY
                    r9_explanation = (
                        "Temperature telemetry data is malformed, corrupted, or contains fewer than 2 valid timestamped readings."
                    )
                elif telemetry_confidence_failed:
                    r9_passed = False
                    r9_epistemic_type = EpistemologicalType.UNCERTAINTY
                    r9_explanation = (
                        f"Temperature telemetry does not meet required confidence threshold ({min_confidence:.2f}) or has UNCERTAINTY status."
                    )
                else:
                    # Sort readings chronologically
                    parsed_readings.sort(key=lambda x: x[0])
                    temps = [p[1] for p in parsed_readings]
                    min_recorded_temp = min(temps)
                    max_recorded_temp = max(temps)

                    cold_chain_inputs["min_recorded_temp_celsius"] = min_recorded_temp
                    cold_chain_inputs["max_recorded_temp_celsius"] = max_recorded_temp

                    current_contiguous_minutes = 0.0

                    calculation_method = str(contract_config.get("excursion_calculation_method", "step")).lower()

                    for i in range(len(parsed_readings) - 1):
                        t_curr, temp_curr = parsed_readings[i]
                        t_next, temp_next = parsed_readings[i + 1]

                        delta_seconds = (t_next - t_curr).total_seconds()
                        if delta_seconds < 0:
                            malformed_data = True
                            break
                        delta_minutes = delta_seconds / 60.0

                        is_curr_excursion = temp_curr < min_temp_celsius or temp_curr > max_temp_celsius
                        is_next_excursion = temp_next < min_temp_celsius or temp_next > max_temp_celsius

                        if calculation_method == "linear":
                            if is_curr_excursion and is_next_excursion:
                                excursion_interval = delta_minutes
                            elif is_curr_excursion != is_next_excursion:
                                thresh = max_temp_celsius if max(temp_curr, temp_next) > max_temp_celsius else min_temp_celsius
                                diff = abs(temp_next - temp_curr)
                                if diff > 1e-6:
                                    frac = abs((temp_curr if is_curr_excursion else temp_next) - thresh) / diff
                                    excursion_interval = delta_minutes * min(1.0, max(0.0, frac))
                                else:
                                    excursion_interval = delta_minutes / 2.0
                            else:
                                excursion_interval = 0.0
                        else:
                            # Step-wise sample-and-hold: if the sensor recorded an excursion at t_curr,
                            # the temperature was out of spec for that interval until the next reading
                            excursion_interval = delta_minutes if is_curr_excursion else 0.0

                        if excursion_interval > 0:
                            total_excursion_minutes += excursion_interval
                            current_contiguous_minutes += excursion_interval
                            if current_contiguous_minutes > max_contiguous_excursion_minutes:
                                max_contiguous_excursion_minutes = current_contiguous_minutes
                        else:
                            current_contiguous_minutes = 0.0

                    if malformed_data:
                        r9_passed = False
                        r9_epistemic_type = EpistemologicalType.UNCERTAINTY
                        r9_explanation = "Non-chronological telemetry timestamps encountered during interval analysis."
                    else:
                        eval_minutes = (
                            max_contiguous_excursion_minutes
                            if excursion_mode == "contiguous"
                            else total_excursion_minutes
                        )
                        cold_chain_inputs["calculated_excursion_minutes"] = round(eval_minutes, 2)
                        cold_chain_inputs["total_cumulative_excursion_minutes"] = round(total_excursion_minutes, 2)
                        cold_chain_inputs["max_contiguous_excursion_minutes"] = round(max_contiguous_excursion_minutes, 2)

                        if eval_minutes <= max_excursion_duration_minutes:
                            r9_passed = True
                            r9_explanation = (
                                f"Temperature monitoring compliant: {eval_minutes:.1f} excursion min(s) "
                                f"within allowed SLA threshold ({max_excursion_duration_minutes:.1f} mins) "
                                f"[Range: {min_recorded_temp:.1f}°C to {max_recorded_temp:.1f}°C]."
                            )
                        else:
                            r9_passed = False
                            r9_epistemic_type = EpistemologicalType.RULE
                            r9_explanation = (
                                f"Cold-chain SLA violation: {eval_minutes:.1f} excursion min(s) exceeds "
                                f"allowed threshold of {max_excursion_duration_minutes:.1f} mins "
                                f"[Allowed: {min_temp_celsius:.1f}°C-{max_temp_celsius:.1f}°C, "
                                f"Observed: {min_recorded_temp:.1f}°C-{max_recorded_temp:.1f}°C]."
                            )

        traces.append(
            RuleEvaluationTrace(
                rule_id="RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION",
                rule_name="Cold-Chain Temperature SLA & Excursion Verification",
                passed=r9_passed,
                epistemic_type=r9_epistemic_type,
                inputs_used=cold_chain_inputs,
                evidence_ids=all_evidence_ids,
                explanation=r9_explanation,
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
            "requires_cold_chain": requires_cold_chain,
            "total_excursion_minutes": round(total_excursion_minutes, 2),
            "max_contiguous_excursion_minutes": round(max_contiguous_excursion_minutes, 2),
            "min_recorded_temperature_celsius": min_recorded_temp,
            "max_recorded_temperature_celsius": max_recorded_temp,
        }
        return traces, computed_metrics
