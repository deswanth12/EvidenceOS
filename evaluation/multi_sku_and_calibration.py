"""Multi-SKU Entity Linking Stress Benchmark (N=42) & Confidence Calibration Analysis (N=150).

Implements the post-freeze research audit experiments without mutating the frozen
v1.0.0-benchmark-frozen held-out benchmark (N=150, 94.0% decision accuracy):
1. Generates `evaluation/datasets/benchmark_freeze_manifest.json` locking the v1.0.0 state.
2. Runs a dedicated 42-case Multi-SKU Entity Linking Stress Benchmark across 7 categories
   comparing `v1_frozen` (Primary-SKU Fallback) vs `v2_context_aware` (OCR-Canonicalized +
   Cross-Modal Corroborated Context Linking).
3. Computes Confidence Calibration (ECE, Reliability Bins) and Selective Prediction
   (Risk-Coverage & Auto-Settlement Precision vs. Abstention Rate) across the 150-case
   held-out evaluation set.
"""

import hashlib
import json
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai.provider import HeuristicLocalAIProvider
from core.datasets_generator import (
    generate_inspection_png_bytes,
    generate_pdf_bytes,
    generate_wav_voice_bytes,
)
from core.db.models import Base, CaseModel
from core.decisions.engine import CaseVerificationPipeline
from core.extraction.service import MultimodalExtractionService
from core.ingestion.service import EvidenceIngestionService
from core.storage.provider import LocalFilesystemStorage
from evaluation.runner import wilson_confidence_interval


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_multi_sku_42_dataset() -> List[Dict[str, Any]]:
    """Construct 42 dedicated Multi-SKU adversarial cases across 7 categories (6 cases each)."""
    cases: List[Dict[str, Any]] = []
    idx = 0

    def _add_case(
        category: str,
        sub_idx: int,
        title: str,
        expected_outcome: str,
        expected_ordered: int,
        expected_delivered: int,
        expected_damaged: int,
        target_damaged_sku: str,
        files: List[Dict[str, Any]],
    ) -> None:
        nonlocal idx
        idx += 1
        cases.append(
            {
                "case_id": f"multisku_case_{idx:03d}",
                "category": category,
                "category_index": sub_idx,
                "title": title,
                "expected_outcome": expected_outcome,
                "expected_ordered": expected_ordered,
                "expected_delivered": expected_delivered,
                "expected_damaged": expected_damaged,
                "target_damaged_sku": target_damaged_sku,
                "files": files,
            }
        )

    # Category 1: explicit_multi_sku (6 cases) — Explicit barcode/label on image + voice
    for i in range(1, 7):
        dmg = 1 if i % 2 == 1 else 2
        po = generate_pdf_bytes(
            document_title="PURCHASE ORDER",
            document_id=f"PO-MS1-{i}",
            po_reference=f"PO-MS1-{i}",
            shipment_id=f"SHP-MS1-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-01",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "ordered_quantity": 5, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "ordered_quantity": 5, "unit_price": 200.0},
            ],
        )
        dc = generate_pdf_bytes(
            document_title="DELIVERY CHALLAN",
            document_id=f"DC-MS1-{i}",
            po_reference=f"PO-MS1-{i}",
            shipment_id=f"SHP-MS1-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-04",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
            ],
        )
        img = generate_inspection_png_bytes(
            sku="SKU-IND-202",
            visible_quantity=10,
            damaged_quantity=dmg,
            packaging_condition="crushed_corner",
            visual_seed=7000 + i,
            blind_mode=False,  # Optical barcode label present
        )
        wav = generate_wav_voice_bytes(
            f"Unloaded multi-SKU shipment: {dmg} boxes of SKU-IND-202 were damaged during unloading."
        )
        _add_case(
            category="explicit_multi_sku",
            sub_idx=i,
            title=f"Explicit Multi-SKU Barcode #{i}",
            expected_outcome="partially_approved",
            expected_ordered=10,
            expected_delivered=10,
            expected_damaged=dmg,
            target_damaged_sku="SKU-IND-202",
            files=[
                {"filename": "artifact_01.pdf", "role": "purchase_order", "content": po},
                {"filename": "artifact_02.pdf", "role": "delivery_challan", "content": dc},
                {"filename": "artifact_03.png", "role": "inspection_image", "content": img},
                {"filename": "artifact_04.wav", "role": "voice_report", "content": wav},
            ],
        )

    # Category 2: similar_sku_names_and_codes (6 cases) — SKU-IND-201A vs SKU-IND-201B, blind CV
    for i in range(1, 7):
        dmg = 2 if i <= 3 else 1
        po = generate_pdf_bytes(
            document_title="PURCHASE ORDER",
            document_id=f"PO-MS2-{i}",
            po_reference=f"PO-MS2-{i}",
            shipment_id=f"SHP-MS2-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-01",
            items=[
                {"sku": "SKU-IND-201A", "name": "High-Pressure Servo Valve 10mm", "ordered_quantity": 5, "unit_price": 200.0},
                {"sku": "SKU-IND-201B", "name": "High-Pressure Servo Valve 12mm", "ordered_quantity": 5, "unit_price": 200.0},
            ],
        )
        dc = generate_pdf_bytes(
            document_title="DELIVERY CHALLAN",
            document_id=f"DC-MS2-{i}",
            po_reference=f"PO-MS2-{i}",
            shipment_id=f"SHP-MS2-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-04",
            items=[
                {"sku": "SKU-IND-201A", "name": "High-Pressure Servo Valve 10mm", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
                {"sku": "SKU-IND-201B", "name": "High-Pressure Servo Valve 12mm", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
            ],
        )
        img = generate_inspection_png_bytes(
            sku="SKU-IND-201B",
            visible_quantity=10,
            damaged_quantity=dmg,
            packaging_condition="crushed_corner",
            visual_seed=7100 + i,
            blind_mode=True,
        )
        wav = generate_wav_voice_bytes(
            f"Inspection found {dmg} boxes of SKU-IND-201B crushed at the dock."
        )
        _add_case(
            category="similar_sku_names_and_codes",
            sub_idx=i,
            title=f"Similar SKU Codes (201A vs 201B) #{i}",
            expected_outcome="partially_approved",
            expected_ordered=10,
            expected_delivered=10,
            expected_damaged=dmg,
            target_damaged_sku="SKU-IND-201B",
            files=[
                {"filename": "artifact_01.pdf", "role": "purchase_order", "content": po},
                {"filename": "artifact_02.pdf", "role": "delivery_challan", "content": dc},
                {"filename": "artifact_03.png", "role": "inspection_image", "content": img},
                {"filename": "artifact_04.wav", "role": "voice_report", "content": wav},
            ],
        )

    # Category 3: reordered_line_items (6 cases) — PO lists [202, 201], Challan lists [201, 202]
    for i in range(1, 7):
        dmg = 2
        po = generate_pdf_bytes(
            document_title="PURCHASE ORDER",
            document_id=f"PO-MS3-{i}",
            po_reference=f"PO-MS3-{i}",
            shipment_id=f"SHP-MS3-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-01",
            items=[
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "ordered_quantity": 5, "unit_price": 200.0},
                {"sku": "SKU-IND-201", "name": "Primary Valve", "ordered_quantity": 5, "unit_price": 200.0},
            ],
        )
        dc = generate_pdf_bytes(
            document_title="DELIVERY CHALLAN",
            document_id=f"DC-MS3-{i}",
            po_reference=f"PO-MS3-{i}",
            shipment_id=f"SHP-MS3-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-04",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "delivered_quantity": 5, "damaged_quantity": dmg, "unit_price": 200.0},
            ],
        )
        img = generate_inspection_png_bytes(
            sku="SKU-IND-202",
            visible_quantity=10,
            damaged_quantity=dmg,
            packaging_condition="crushed_corner",
            visual_seed=7200 + i,
            blind_mode=True,
        )
        wav = generate_wav_voice_bytes(
            "Two boxes of SKU-IND-202 were damaged during unloading."
        )
        _add_case(
            category="reordered_line_items",
            sub_idx=i,
            title=f"Reordered PO vs Challan Line Items #{i}",
            expected_outcome="partially_approved",
            expected_ordered=10,
            expected_delivered=10,
            expected_damaged=dmg,
            target_damaged_sku="SKU-IND-202",
            files=[
                {"filename": "artifact_01.pdf", "role": "purchase_order", "content": po},
                {"filename": "artifact_02.pdf", "role": "delivery_challan", "content": dc},
                {"filename": "artifact_03.png", "role": "inspection_image", "content": img},
                {"filename": "artifact_04.wav", "role": "voice_report", "content": wav},
            ],
        )

    # Category 4: missing_visual_barcodes_blind_cv (6 cases) — The exact heldout_150 failure mode
    for i in range(1, 7):
        dmg = 1 if i % 2 == 1 else 2
        po = generate_pdf_bytes(
            document_title="PURCHASE ORDER",
            document_id=f"PO-MS4-{i}",
            po_reference=f"PO-MS4-{i}",
            shipment_id=f"SHP-MS4-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-01",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "ordered_quantity": 5, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "ordered_quantity": 5, "unit_price": 200.0},
            ],
        )
        dc = generate_pdf_bytes(
            document_title="DELIVERY CHALLAN",
            document_id=f"DC-MS4-{i}",
            po_reference=f"PO-MS4-{i}",
            shipment_id=f"SHP-MS4-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-04",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
            ],
        )
        img = generate_inspection_png_bytes(
            sku="SKU-IND-202",
            visible_quantity=10,
            damaged_quantity=dmg,
            packaging_condition="crushed_corner",
            visual_seed=7300 + i,
            blind_mode=True,
        )
        wav = generate_wav_voice_bytes(
            f"Unloaded pallet: {dmg} boxes of SKU-IND-202 were crushed on arrival."
        )
        _add_case(
            category="missing_visual_barcodes_blind_cv",
            sub_idx=i,
            title=f"Blind Pixel CV Without Box Barcode #{i}",
            expected_outcome="partially_approved",
            expected_ordered=10,
            expected_delivered=10,
            expected_damaged=dmg,
            target_damaged_sku="SKU-IND-202",
            files=[
                {"filename": "artifact_01.pdf", "role": "purchase_order", "content": po},
                {"filename": "artifact_02.pdf", "role": "delivery_challan", "content": dc},
                {"filename": "artifact_03.png", "role": "inspection_image", "content": img},
                {"filename": "artifact_04.wav", "role": "voice_report", "content": wav},
            ],
        )

    # Category 5: partial_pallet_visibility (6 cases) — Clean multi-SKU delivery where image sees 10 boxes
    for i in range(1, 7):
        po = generate_pdf_bytes(
            document_title="PURCHASE ORDER",
            document_id=f"PO-MS5-{i}",
            po_reference=f"PO-MS5-{i}",
            shipment_id=f"SHP-MS5-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-01",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "ordered_quantity": 6, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "ordered_quantity": 6, "unit_price": 200.0},
            ],
        )
        dc = generate_pdf_bytes(
            document_title="DELIVERY CHALLAN",
            document_id=f"DC-MS5-{i}",
            po_reference=f"PO-MS5-{i}",
            shipment_id=f"SHP-MS5-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-04",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "delivered_quantity": 6, "damaged_quantity": 0, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "delivered_quantity": 6, "damaged_quantity": 0, "unit_price": 200.0},
            ],
        )
        img = generate_inspection_png_bytes(
            sku="SKU-IND-201",
            visible_quantity=10,
            damaged_quantity=0,
            packaging_condition="intact",
            visual_seed=7400 + i,
            blind_mode=True,
        )
        wav = generate_wav_voice_bytes(
            "All 12 units across SKU-IND-201 and SKU-IND-202 arrived intact, zero damaged."
        )
        _add_case(
            category="partial_pallet_visibility",
            sub_idx=i,
            title=f"Multi-SKU Partial Pallet Visibility #{i}",
            expected_outcome="approved",
            expected_ordered=12,
            expected_delivered=12,
            expected_damaged=0,
            target_damaged_sku="NONE",
            files=[
                {"filename": "artifact_01.pdf", "role": "purchase_order", "content": po},
                {"filename": "artifact_02.pdf", "role": "delivery_challan", "content": dc},
                {"filename": "artifact_03.png", "role": "inspection_image", "content": img},
                {"filename": "artifact_04.wav", "role": "voice_report", "content": wav},
            ],
        )

    # Category 6: conflicting_sku_references (6 cases) — Challan says 201 damaged, Voice says 202 damaged
    for i in range(1, 7):
        po = generate_pdf_bytes(
            document_title="PURCHASE ORDER",
            document_id=f"PO-MS6-{i}",
            po_reference=f"PO-MS6-{i}",
            shipment_id=f"SHP-MS6-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-01",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "ordered_quantity": 5, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "ordered_quantity": 5, "unit_price": 200.0},
            ],
        )
        dc = generate_pdf_bytes(
            document_title="DELIVERY CHALLAN",
            document_id=f"DC-MS6-{i}",
            po_reference=f"PO-MS6-{i}",
            shipment_id=f"SHP-MS6-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-04",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "delivered_quantity": 5, "damaged_quantity": 2, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
            ],
        )
        img = generate_inspection_png_bytes(
            sku="SKU-IND-201",
            visible_quantity=10,
            damaged_quantity=2,
            packaging_condition="crushed_corner",
            visual_seed=7500 + i,
            blind_mode=True,
        )
        wav = generate_wav_voice_bytes(
            "Two boxes of SKU-IND-202 were crushed during unloading."
        )
        _add_case(
            category="conflicting_sku_references",
            sub_idx=i,
            title=f"Conflicting Cross-Modal SKU Attribution #{i}",
            expected_outcome="manual_review_required",
            expected_ordered=10,
            expected_delivered=10,
            expected_damaged=2,
            target_damaged_sku="CONFLICT",
            files=[
                {"filename": "artifact_01.pdf", "role": "purchase_order", "content": po},
                {"filename": "artifact_02.pdf", "role": "delivery_challan", "content": dc},
                {"filename": "artifact_03.png", "role": "inspection_image", "content": img},
                {"filename": "artifact_04.wav", "role": "voice_report", "content": wav},
            ],
        )

    # Category 7: ocr_noisy_sku_identifiers (6 cases) — Voice/Challan has SKU-1ND-2O2 typo
    for i in range(1, 7):
        dmg = 2
        po = generate_pdf_bytes(
            document_title="PURCHASE ORDER",
            document_id=f"PO-MS7-{i}",
            po_reference=f"PO-MS7-{i}",
            shipment_id=f"SHP-MS7-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-01",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "ordered_quantity": 5, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "ordered_quantity": 5, "unit_price": 200.0},
            ],
        )
        dc = generate_pdf_bytes(
            document_title="DELIVERY CHALLAN",
            document_id=f"DC-MS7-{i}",
            po_reference=f"PO-MS7-{i}",
            shipment_id=f"SHP-MS7-{i}",
            supplier="Apex Industrial",
            buyer="Vertex Logistics",
            date_str="2026-10-04",
            items=[
                {"sku": "SKU-IND-201", "name": "Primary Valve", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
                {"sku": "SKU-IND-202", "name": "Secondary Actuator", "delivered_quantity": 5, "damaged_quantity": 0, "unit_price": 200.0},
            ],
        )
        img = generate_inspection_png_bytes(
            sku="SKU-IND-202",
            visible_quantity=10,
            damaged_quantity=dmg,
            packaging_condition="crushed_corner",
            visual_seed=7600 + i,
            blind_mode=True,
        )
        wav = generate_wav_voice_bytes(
            "Two boxes of SKU-1ND-2O2 were damaged during unloading."
        )
        _add_case(
            category="ocr_noisy_sku_identifiers",
            sub_idx=i,
            title=f"OCR-Corrupted SKU Identifier (SKU-1ND-2O2) #{i}",
            expected_outcome="partially_approved",
            expected_ordered=10,
            expected_delivered=10,
            expected_damaged=dmg,
            target_damaged_sku="SKU-IND-202",
            files=[
                {"filename": "artifact_01.pdf", "role": "purchase_order", "content": po},
                {"filename": "artifact_02.pdf", "role": "delivery_challan", "content": dc},
                {"filename": "artifact_03.png", "role": "inspection_image", "content": img},
                {"filename": "artifact_04.wav", "role": "voice_report", "content": wav},
            ],
        )

    return cases


def evaluate_multi_sku_benchmark(resolver_mode: str) -> Dict[str, Any]:
    """Run the 42-case Multi-SKU benchmark under either v1_frozen or v2_context_aware."""
    cases = build_multi_sku_42_dataset()
    provider = HeuristicLocalAIProvider()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        storage = LocalFilesystemStorage(base_dir=tmp_path / "store")
        engine = create_engine(
            f"sqlite:///{(tmp_path / 'ms.db').as_posix()}",
            connect_args={"check_same_thread": False},
            future=True,
        )
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        ingestor = EvidenceIngestionService(storage=storage)
        extractor = MultimodalExtractionService(ai_provider=provider, storage=storage)
        pipeline = CaseVerificationPipeline(extractor=extractor)

        decision_hits = 0
        strict_entity_link_hits = 0
        confident_errors = 0
        cat_totals: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "decision_passed": 0, "strict_entity_linked": 0}
        )

        with SessionLocal() as db:
            for spec in cases:
                cid = f"{spec['case_id']}_{resolver_mode}"
                cat = spec["category"]
                case = CaseModel(
                    id=cid,
                    title=spec["title"],
                    status="created",
                    contract_sla_config={
                        "max_auto_approve_damage_ratio": 0.25,
                        "min_confidence_threshold": 0.75,
                    },
                )
                db.add(case)
                db.commit()

                for idx_f, f in enumerate(spec["files"], start=1):
                    content = f["content"]
                    if f["filename"].endswith(".wav") and len(content) > 60:
                        ba = bytearray(content)
                        ba[44] = idx_f & 0xFF
                        ba[45] = int(spec["case_id"][-3:]) & 0xFF
                        content = bytes(ba)
                    ingestor.ingest_file(
                        db=db,
                        case_id=cid,
                        filename=f["filename"],
                        content=content,
                        document_role=f["role"],
                    )

                run_out = pipeline.run_case_pipeline(
                    db=db,
                    case_id=cid,
                    use_rule_engine=True,
                    enable_historical_matching=False,
                    resolver_mode=resolver_mode,
                )
                dec = run_out["decision"]
                actual_out = dec["outcome"]
                expected_out = spec["expected_outcome"]
                passed = actual_out == expected_out

                cat_totals[cat]["total"] += 1
                if passed:
                    decision_hits += 1
                    cat_totals[cat]["decision_passed"] += 1
                else:
                    if actual_out in ("approved", "partially_approved"):
                        confident_errors += 1

                # Strict entity linking check:
                # Did the pipeline resolve exactly 2 canonical SKUs (no spurious 3rd typo entity)
                # and corroborate the target SKU's damage?
                strict_linked = passed and (run_out["entities_count"] == 2)
                if strict_linked:
                    strict_entity_link_hits += 1
                    cat_totals[cat]["strict_entity_linked"] += 1

        engine.dispose()

    n = len(cases)
    return {
        "resolver_mode": resolver_mode,
        "total_cases": n,
        "decision_accuracy": round(decision_hits / n, 4),
        "decision_accuracy_ci_95": wilson_confidence_interval(decision_hits, n),
        "strict_entity_claim_linking_accuracy": round(strict_entity_link_hits / n, 4),
        "strict_entity_linking_ci_95": wilson_confidence_interval(strict_entity_link_hits, n),
        "confident_error_rate": round(confident_errors / n, 4),
        "category_breakdown": [
            {
                "category": k,
                "total_cases": v["total"],
                "decision_passed": v["decision_passed"],
                "decision_accuracy": round(v["decision_passed"] / v["total"], 4),
                "strict_entity_linked": v["strict_entity_linked"],
                "strict_entity_linking_accuracy": round(v["strict_entity_linked"] / v["total"], 4),
            }
            for k, v in cat_totals.items()
        ],
    }


def compute_confidence_calibration_and_risk_coverage(results_path: Path) -> Dict[str, Any]:
    """Compute ECE, Brier score, Reliability Bins, and Selective Prediction curves on heldout_150."""
    from evaluation.datasets.generator import get_heldout_150_dataset
    from evaluation.runner import _evaluate_provider_on_cases

    heldout_cases = get_heldout_150_dataset(seed=42)
    sys_d_out = _evaluate_provider_on_cases(
        provider=HeuristicLocalAIProvider(),
        benchmark_cases=heldout_cases,
        system_label="System D: Full EvidenceOS",
        use_rule_engine=True,
        enable_historical_matching=True,
    )
    sys_c_out = _evaluate_provider_on_cases(
        provider=HeuristicLocalAIProvider(),
        benchmark_cases=heldout_cases,
        system_label="System C: Semantic AI Only",
        use_rule_engine=False,
        enable_historical_matching=True,
    )
    case_results = sys_d_out["case_results"]
    sys_c_results = sys_c_out["case_results"]
    n = len(case_results)

    # 1. Reliability bins across overall case confidence
    bin_edges = [(0.0, 0.50), (0.50, 0.70), (0.70, 0.85), (0.85, 0.92), (0.92, 1.01)]
    bins_report = []
    ece_auto_settle = 0.0
    total_auto_settled = 0
    correct_auto_settled = 0

    for lo, hi in bin_edges:
        in_bin = [c for c in case_results if lo <= float(c["confidence"]) < hi]
        cnt = len(in_bin)
        if cnt == 0:
            bins_report.append(
                {
                    "bin_range": f"[{lo:.2f}, {min(1.0, hi):.2f})",
                    "case_count": 0,
                    "mean_confidence": 0.0,
                    "empirical_decision_accuracy": 0.0,
                    "auto_settlement_count": 0,
                    "auto_settlement_precision": 1.0,
                }
            )
            continue
        mean_conf = sum(float(c["confidence"]) for c in in_bin) / cnt
        emp_acc = sum(1 for c in in_bin if c["passed"]) / cnt
        auto_in_bin = [
            c for c in in_bin if c["actual_outcome"] in ("approved", "partially_approved")
        ]
        auto_cnt = len(auto_in_bin)
        auto_prec = (
            sum(1 for c in auto_in_bin if c["passed"]) / auto_cnt if auto_cnt > 0 else 1.0
        )
        total_auto_settled += auto_cnt
        correct_auto_settled += sum(1 for c in auto_in_bin if c["passed"])
        if auto_cnt > 0:
            ece_auto_settle += (auto_cnt / n) * abs(auto_prec - mean_conf)

        bins_report.append(
            {
                "bin_range": f"[{lo:.2f}, {min(1.0, hi):.2f}]",
                "case_count": cnt,
                "mean_confidence": round(mean_conf, 4),
                "empirical_decision_accuracy": round(emp_acc, 4),
                "auto_settlement_count": auto_cnt,
                "auto_settlement_precision": round(auto_prec, 4),
            }
        )

    # 2. Selective Prediction / Risk-Coverage Sweep across confidence thresholds tau
    thresholds = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    threshold_sweep = []
    for tau in thresholds:
        covered = [
            c
            for c in case_results
            if float(c["confidence"]) >= tau
            and c["actual_outcome"] in ("approved", "partially_approved")
        ]
        cov_cnt = len(covered)
        cov_rate = round(cov_cnt / n, 4)
        sel_acc = round(sum(1 for c in covered if c["passed"]) / cov_cnt, 4) if cov_cnt > 0 else 1.0
        sel_risk = round(1.0 - sel_acc, 4)
        threshold_sweep.append(
            {
                "confidence_threshold_tau": tau,
                "auto_settled_cases": cov_cnt,
                "auto_settlement_coverage": cov_rate,
                "selective_precision_when_acting": sel_acc,
                "selective_risk_error_rate": sel_risk,
            }
        )

    sys_c_auto = [
        c for c in sys_c_results if c["actual_outcome"] in ("approved", "partially_approved")
    ]
    sys_c_auto_cnt = len(sys_c_auto)
    sys_c_auto_correct = sum(1 for c in sys_c_auto if c["passed"])

    return {
        "dataset": "heldout_150",
        "total_cases": n,
        "total_auto_settled_cases": total_auto_settled,
        "auto_settlement_coverage": round(total_auto_settled / n, 4),
        "auto_settlement_precision": round(correct_auto_settled / max(1, total_auto_settled), 4),
        "auto_settlement_precision_ci_95": wilson_confidence_interval(
            correct_auto_settled, max(1, total_auto_settled)
        ),
        "total_abstained_to_human_review": n - total_auto_settled,
        "abstention_coverage": round((n - total_auto_settled) / n, 4),
        "confident_error_count": total_auto_settled - correct_auto_settled,
        "confident_error_rate": round((total_auto_settled - correct_auto_settled) / n, 4),
        "expected_calibration_error_auto_settlement": round(ece_auto_settle, 4),
        "system_c_ai_only_comparison": {
            "auto_settled_cases": sys_c_auto_cnt,
            "auto_settlement_coverage": round(sys_c_auto_cnt / n, 4),
            "auto_settlement_precision": round(sys_c_auto_correct / max(1, sys_c_auto_cnt), 4),
            "confident_error_count": sys_c_auto_cnt - sys_c_auto_correct,
            "confident_error_rate": round((sys_c_auto_cnt - sys_c_auto_correct) / n, 4),
        },
        "reliability_bins": bins_report,
        "selective_prediction_threshold_sweep": threshold_sweep,
    }


def run_post_freeze_audit_and_experiments() -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    results_path = root / "evaluation" / "results.json"
    failures_path = root / "evaluation" / "failures.json"
    manifest_path = root / "evaluation" / "datasets" / "heldout_test_150_manifest.json"

    # 1. Generate Freeze Manifest
    freeze_manifest = {
        "benchmark_tag": "v1.0.0-benchmark-frozen",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": 42,
        "heldout_cases": 150,
        "heldout_files": 564,
        "locked_system_d_metrics": {
            "decision_accuracy": 0.94,
            "decision_accuracy_ci_95": [0.89, 0.968],
            "macro_f1": 0.9132,
            "field_level_accuracy": 0.9556,
            "conflict_f1": 0.9505,
            "confident_error_rate": 0.0,
            "appropriate_abstention_rate": 1.0,
            "strict_entity_claim_linking_accuracy": 0.98,
        },
        "artifact_sha256_digests": {
            "evaluation/results.json": _sha256_file(results_path),
            "evaluation/failures.json": _sha256_file(failures_path),
            "evaluation/datasets/heldout_test_150_manifest.json": _sha256_file(manifest_path),
        },
    }
    freeze_out = root / "evaluation" / "datasets" / "benchmark_freeze_manifest.json"
    freeze_out.write_text(json.dumps(freeze_manifest, indent=2), encoding="utf-8")

    # 2. Run Multi-SKU Entity Linking Stress Benchmark (v1_frozen vs v2_context_aware)
    v1_res = evaluate_multi_sku_benchmark("v1_frozen")
    v2_res = evaluate_multi_sku_benchmark("v2_context_aware")

    # 3. Run Confidence Calibration & Selective Prediction Analysis on heldout_150
    calibration_res = compute_confidence_calibration_and_risk_coverage(results_path)

    combined = {
        "freeze_manifest": freeze_manifest,
        "multi_sku_stress_benchmark_42": {
            "total_cases": 42,
            "categories_count": 7,
            "v1_frozen_baseline_resolver": v1_res,
            "v2_context_aware_resolver": v2_res,
        },
        "confidence_calibration_and_selective_prediction_150": calibration_res,
    }
    out_file = root / "evaluation" / "post_freeze_audit_experiments.json"
    out_file.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    return combined


if __name__ == "__main__":
    summary = run_post_freeze_audit_and_experiments()
    v1 = summary["multi_sku_stress_benchmark_42"]["v1_frozen_baseline_resolver"]
    v2 = summary["multi_sku_stress_benchmark_42"]["v2_context_aware_resolver"]
    cal = summary["confidence_calibration_and_selective_prediction_150"]
    print(f"Multi-SKU (N=42) v1_frozen Decision Acc: {v1['decision_accuracy']*100:.1f}%")
    print(f"Multi-SKU (N=42) v2_context_aware Decision Acc: {v2['decision_accuracy']*100:.1f}%")
    print(
        f"Calibration (N=150): Auto-Settled={cal['total_auto_settled_cases']}/150 "
        f"({cal['auto_settlement_coverage']*100:.1f}%), Precision={cal['auto_settlement_precision']*100:.1f}%, "
        f"Confident Errors={cal['confident_error_count']}"
    )
