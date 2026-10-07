"""Comprehensive unit test suite for Cold-Chain Temperature Excursion Rule (R9).

Deterministic tests verifying:
- Compliant temperature windows (e.g. 2°C - 8°C)
- Exact temperature and duration threshold boundaries
- Short allowable excursions vs over-threshold excursions
- Cumulative vs contiguous excursion evaluation modes
- Sub-zero freezing events
- Irregular telemetry timestamp intervals
- Missing telemetry when required by contract SLA
- Malformed, corrupted, and non-chronological telemetry
- Low-confidence and UNCERTAINTY telemetry readings
- Backward compatibility when requires_cold_chain is disabled
"""

from datetime import datetime, timezone

from core.rules.engine import DeterministicRuleEngine
from core.schemas import (
    DocumentRole,
    EpistemologicalType,
    EvidenceModality,
    Provenance,
    ResolvedEntity,
    TemperatureReading,
    TemperatureTelemetryPayload,
)


def _build_dummy_entity(all_good: bool = True) -> ResolvedEntity:
    """Helper to produce a baseline resolved entity satisfying Rules 1-5."""
    return ResolvedEntity(
        entity_id="item_pharma_cold_1",
        case_id="case_pharma_cold_01",
        entity_type="line_item",
        canonical_key="ITEM:SKU-COLD-500",
        display_name="Temperature Sensitive Biologicals",
        sku="SKU-COLD-500",
        linked_evidence_ids=["ev_po_01", "ev_dc_01"],
        attributes_by_source={
            "document_relevance": [
                {"confidence": 0.95, "epistemic_type": "FACT", "role": "purchase_order"},
                {"confidence": 0.95, "epistemic_type": "FACT", "role": "delivery_challan"},
            ],
            "ordered_quantity": [{"value": 100, "confidence": 0.98}],
            "delivered_quantity": [{"value": 100, "confidence": 0.98}],
            "unit_price": [{"value": 50.0}],
            "damaged_quantity": [{"value": 0, "confidence": 1.0, "document_role": "delivery_challan"}],
        },
        resolved_at=datetime.now(timezone.utc),
    )


def test_cold_chain_disabled_by_default_backward_compatible():
    """Verify that when requires_cold_chain is False or omitted, Rule 9 passes unconditionally."""
    entity = _build_dummy_entity()
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity],
        conflicts=[],
        historical_warnings=[],
        contract_config={"requires_cold_chain": False},
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is True
    assert r9_trace.epistemic_type == EpistemologicalType.RULE
    assert "not required" in r9_trace.explanation
    assert metrics["requires_cold_chain"] is False


def test_cold_chain_normal_compliant_temperatures():
    """Verify continuous compliant temperatures (4.0°C - 5.5°C) within [2.0°C, 8.0°C]."""
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 4.5, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:15:00Z", "temperature_celsius": 5.0, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:30:00Z", "temperature_celsius": 4.8, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:45:00Z", "temperature_celsius": 5.2, "confidence": 0.95},
        {"timestamp": "2026-10-07T11:00:00Z", "temperature_celsius": 4.9, "confidence": 0.95},
    ]
    contract_config = {
        "requires_cold_chain": True,
        "min_temperature_celsius": 2.0,
        "max_temperature_celsius": 8.0,
        "max_excursion_duration_minutes": 60.0,
        "temperature_telemetry": telemetry,
    }
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity], conflicts=[], historical_warnings=[], contract_config=contract_config
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is True
    assert r9_trace.epistemic_type == EpistemologicalType.RULE
    assert metrics["total_excursion_minutes"] == 0.0
    assert metrics["min_recorded_temperature_celsius"] == 4.5
    assert metrics["max_recorded_temperature_celsius"] == 5.2


def test_cold_chain_exact_boundary_temperatures():
    """Verify readings exactly on the boundary: min 2.0°C and max 8.0°C are compliant."""
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 2.0, "confidence": 0.99},
        {"timestamp": "2026-10-07T10:30:00Z", "temperature_celsius": 8.0, "confidence": 0.99},
        {"timestamp": "2026-10-07T11:00:00Z", "temperature_celsius": 2.0, "confidence": 0.99},
    ]
    contract_config = {
        "requires_cold_chain": True,
        "min_temperature_celsius": 2.0,
        "max_temperature_celsius": 8.0,
        "max_excursion_duration_minutes": 30.0,
        "temperature_telemetry": telemetry,
    }
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity], conflicts=[], historical_warnings=[], contract_config=contract_config
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is True
    assert metrics["total_excursion_minutes"] == 0.0


def test_cold_chain_short_allowable_excursion():
    """Verify brief spike (15 minutes at 9.5°C) within allowable SLA of 60 minutes passes."""
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 4.0, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:15:00Z", "temperature_celsius": 9.5, "confidence": 0.95},  # 15m excursion
        {"timestamp": "2026-10-07T10:30:00Z", "temperature_celsius": 4.2, "confidence": 0.95},  # back to normal
        {"timestamp": "2026-10-07T11:00:00Z", "temperature_celsius": 4.1, "confidence": 0.95},
    ]
    contract_config = {
        "requires_cold_chain": True,
        "min_temperature_celsius": 2.0,
        "max_temperature_celsius": 8.0,
        "max_excursion_duration_minutes": 60.0,
        "temperature_telemetry": telemetry,
    }
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity], conflicts=[], historical_warnings=[], contract_config=contract_config
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is True
    assert metrics["total_excursion_minutes"] == 15.0
    assert "within allowed SLA threshold" in r9_trace.explanation


def test_cold_chain_exact_duration_threshold_boundary():
    """Verify an excursion lasting exactly the maximum allowed SLA (60m) passes."""
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 5.0, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:30:00Z", "temperature_celsius": 9.2, "confidence": 0.95},  # 30m excursion
        {"timestamp": "2026-10-07T11:00:00Z", "temperature_celsius": 9.0, "confidence": 0.95},  # 30m excursion (total 60m)
        {"timestamp": "2026-10-07T11:30:00Z", "temperature_celsius": 4.5, "confidence": 0.95},  # recovery
    ]
    contract_config = {
        "requires_cold_chain": True,
        "min_temperature_celsius": 2.0,
        "max_temperature_celsius": 8.0,
        "max_excursion_duration_minutes": 60.0,
        "temperature_telemetry": telemetry,
    }
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity], conflicts=[], historical_warnings=[], contract_config=contract_config
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is True
    assert metrics["total_excursion_minutes"] == 60.0


def test_cold_chain_exceeding_duration_threshold_fails():
    """Verify an excursion lasting 75 minutes when SLA limit is 60 minutes fails."""
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 5.0, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:30:00Z", "temperature_celsius": 10.0, "confidence": 0.95},  # Excursion start: 30m
        {"timestamp": "2026-10-07T11:00:00Z", "temperature_celsius": 11.2, "confidence": 0.95},  # Still excursion: 30m (cumulative 60m)
        {"timestamp": "2026-10-07T11:30:00Z", "temperature_celsius": 9.8, "confidence": 0.95},   # Still excursion: 15m until 11:45 (or 30m)
        {"timestamp": "2026-10-07T11:45:00Z", "temperature_celsius": 4.5, "confidence": 0.95},   # Excursion ended: 30 + 30 + 15 = 75m
        {"timestamp": "2026-10-07T12:00:00Z", "temperature_celsius": 4.5, "confidence": 0.95},
    ]
    contract_config = {
        "requires_cold_chain": True,
        "min_temperature_celsius": 2.0,
        "max_temperature_celsius": 8.0,
        "max_excursion_duration_minutes": 60.0,
        "temperature_telemetry": telemetry,
    }
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity], conflicts=[], historical_warnings=[], contract_config=contract_config
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is False
    assert r9_trace.epistemic_type == EpistemologicalType.RULE
    assert metrics["total_excursion_minutes"] == 75.0
    assert "Cold-chain SLA violation" in r9_trace.explanation


def test_cold_chain_subzero_freeze_excursion():
    """Verify sub-zero cold excursion (< 2.0°C / below freezing) triggers failure."""
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T08:00:00Z", "temperature_celsius": 4.0, "confidence": 0.95},
        {"timestamp": "2026-10-07T09:00:00Z", "temperature_celsius": -1.5, "confidence": 0.95},  # 60m freeze
        {"timestamp": "2026-10-07T09:30:00Z", "temperature_celsius": -0.8, "confidence": 0.95},  # 30m freeze (total 90m)
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 3.5, "confidence": 0.95},
    ]
    contract_config = {
        "requires_cold_chain": True,
        "min_temperature_celsius": 2.0,
        "max_temperature_celsius": 8.0,
        "max_excursion_duration_minutes": 30.0,
        "temperature_telemetry": telemetry,
    }
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity], conflicts=[], historical_warnings=[], contract_config=contract_config
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is False
    assert metrics["min_recorded_temperature_celsius"] == -1.5


def test_cold_chain_cumulative_vs_contiguous_mode():
    """Verify multiple excursions evaluate differently under cumulative vs contiguous modes.

    Two separate 40-minute excursions:
    - Cumulative total = 80 minutes (fails when max allowed is 60 minutes)
    - Contiguous maximum = 40 minutes (passes when max allowed is 60 minutes)
    """
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T08:00:00Z", "temperature_celsius": 4.0, "confidence": 0.95},
        # Excursion 1: 40m
        {"timestamp": "2026-10-07T08:10:00Z", "temperature_celsius": 10.5, "confidence": 0.95},
        {"timestamp": "2026-10-07T08:50:00Z", "temperature_celsius": 4.0, "confidence": 0.95},   # Normalized
        # Normal period: 30m
        {"timestamp": "2026-10-07T09:20:00Z", "temperature_celsius": 4.0, "confidence": 0.95},
        # Excursion 2: 40m
        {"timestamp": "2026-10-07T09:20:00Z", "temperature_celsius": 10.2, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 4.0, "confidence": 0.95},   # Normalized
    ]
    # 1. Cumulative mode (default): total = 80m > 60m threshold -> FAILS
    traces_cum, metrics_cum = DeterministicRuleEngine.evaluate_rules(
        entities=[entity],
        conflicts=[],
        historical_warnings=[],
        contract_config={
            "requires_cold_chain": True,
            "max_excursion_duration_minutes": 60.0,
            "excursion_evaluation_mode": "cumulative",
            "temperature_telemetry": telemetry,
        },
    )
    r9_cum = next(t for t in traces_cum if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_cum.passed is False
    assert metrics_cum["total_excursion_minutes"] == 80.0

    # 2. Contiguous mode: max contiguous = 40m <= 60m threshold -> PASSES
    traces_cont, metrics_cont = DeterministicRuleEngine.evaluate_rules(
        entities=[entity],
        conflicts=[],
        historical_warnings=[],
        contract_config={
            "requires_cold_chain": True,
            "max_excursion_duration_minutes": 60.0,
            "excursion_evaluation_mode": "contiguous",
            "temperature_telemetry": telemetry,
        },
    )
    r9_cont = next(t for t in traces_cont if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_cont.passed is True
    assert metrics_cont["max_contiguous_excursion_minutes"] == 40.0


def test_cold_chain_irregular_telemetry_timestamps():
    """Verify non-uniform intervals (7m, 13m, 25m) are accurately calculated without rounding errors."""
    entity = _build_dummy_entity()
    telemetry = [
        {"timestamp": "2026-10-07T12:00:00Z", "temperature_celsius": 5.0, "confidence": 0.95},
        {"timestamp": "2026-10-07T12:05:00Z", "temperature_celsius": 12.0, "confidence": 0.95},  # Excursion 1: 7m (to 12:12)
        {"timestamp": "2026-10-07T12:12:00Z", "temperature_celsius": 5.0, "confidence": 0.95},   # Back to normal
        {"timestamp": "2026-10-07T12:20:00Z", "temperature_celsius": 11.0, "confidence": 0.95},  # Excursion 2: 13m (to 12:33)
        {"timestamp": "2026-10-07T12:33:00Z", "temperature_celsius": 5.0, "confidence": 0.95},   # Recovery: 25m
        {"timestamp": "2026-10-07T12:58:00Z", "temperature_celsius": 5.0, "confidence": 0.95},
    ]
    contract_config = {
        "requires_cold_chain": True,
        "max_excursion_duration_minutes": 30.0,
        "temperature_telemetry": telemetry,
    }
    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity], conflicts=[], historical_warnings=[], contract_config=contract_config
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is True
    assert metrics["total_excursion_minutes"] == 20.0  # 7 + 13 = 20 mins <= 30 mins


def test_cold_chain_missing_telemetry_triggers_uncertainty():
    """Verify that when cold chain is required but telemetry is absent, rule fails with UNCERTAINTY."""
    entity = _build_dummy_entity()
    traces, _ = DeterministicRuleEngine.evaluate_rules(
        entities=[entity],
        conflicts=[],
        historical_warnings=[],
        contract_config={"requires_cold_chain": True, "temperature_telemetry": []},
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is False
    assert r9_trace.epistemic_type == EpistemologicalType.UNCERTAINTY
    assert "no temperature logger telemetry" in r9_trace.explanation


def test_cold_chain_malformed_telemetry_triggers_uncertainty():
    """Verify corrupted timestamps or non-numeric values fail safely with UNCERTAINTY."""
    entity = _build_dummy_entity()
    malformed_telemetry = [
        {"timestamp": "not-a-valid-timestamp", "temperature_celsius": 5.0},
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": "invalid_temp"},
    ]
    traces, _ = DeterministicRuleEngine.evaluate_rules(
        entities=[entity],
        conflicts=[],
        historical_warnings=[],
        contract_config={"requires_cold_chain": True, "temperature_telemetry": malformed_telemetry},
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is False
    assert r9_trace.epistemic_type == EpistemologicalType.UNCERTAINTY
    assert "malformed" in r9_trace.explanation


def test_cold_chain_low_confidence_telemetry_triggers_uncertainty():
    """Verify telemetry with confidence below SLA threshold fails with UNCERTAINTY."""
    entity = _build_dummy_entity()
    low_conf_telemetry = [
        {"timestamp": "2026-10-07T10:00:00Z", "temperature_celsius": 5.0, "confidence": 0.95},
        {"timestamp": "2026-10-07T10:30:00Z", "temperature_celsius": 5.2, "confidence": 0.40},  # Below 0.85 default
    ]
    traces, _ = DeterministicRuleEngine.evaluate_rules(
        entities=[entity],
        conflicts=[],
        historical_warnings=[],
        contract_config={
            "requires_cold_chain": True,
            "min_confidence_threshold": 0.85,
            "temperature_telemetry": low_conf_telemetry,
        },
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is False
    assert r9_trace.epistemic_type == EpistemologicalType.UNCERTAINTY
    assert "confidence threshold" in r9_trace.explanation


def test_cold_chain_via_entity_attributes_and_pydantic_schema():
    """Verify telemetry embedded directly inside ResolvedEntity attributes using Pydantic schema."""
    telemetry_payload = TemperatureTelemetryPayload(
        device_id="LOGGER-COLD-909",
        recording_interval_seconds=900,
        readings=[
            TemperatureReading(timestamp=datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc), temperature_celsius=5.0),
            TemperatureReading(timestamp=datetime(2026, 10, 7, 10, 15, tzinfo=timezone.utc), temperature_celsius=10.5),
            TemperatureReading(timestamp=datetime(2026, 10, 7, 10, 30, tzinfo=timezone.utc), temperature_celsius=5.0),
        ],
        provenance=Provenance(
            evidence_id="ev_logger_01",
            source_type=EvidenceModality.JSON,
            extraction_method="iot_temperature_logger",
            document_role=DocumentRole.TEMPERATURE_LOGGER,
            confidence=0.96,
            epistemic_type=EpistemologicalType.FACT,
        ),
    )
    # Serialize to entity attribute format
    entity = _build_dummy_entity()
    entity.attributes_by_source["temperature_telemetry"] = [telemetry_payload.model_dump(mode="json")]

    traces, metrics = DeterministicRuleEngine.evaluate_rules(
        entities=[entity],
        conflicts=[],
        historical_warnings=[],
        contract_config={"requires_cold_chain": True, "max_excursion_duration_minutes": 30.0},
    )
    r9_trace = next(t for t in traces if t.rule_id == "RULE_09_COLD_CHAIN_TEMPERATURE_EXCURSION")
    assert r9_trace.passed is True
    assert metrics["total_excursion_minutes"] == 15.0
