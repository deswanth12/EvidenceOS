"""Synthetic Multimodal Benchmark Dataset Generator for EvidenceOS / VeriDock.

Generates real binary PDF documents (via reportlab), real PNG inspection images
(with controlled visual features, pixel patterns, and inspection metadata via Pillow),
and real RIFF/WAVE audio files with embedded transcripts for all 5 core VeriDock
scenarios plus additional evaluation benchmark cases.
"""

import io
import json
import math
import struct
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generate_pdf_bytes(
    document_title: str,
    document_id: str,
    po_reference: str,
    shipment_id: str,
    supplier: str,
    buyer: str,
    date_str: str,
    items: List[Dict[str, Any]],
    notes: Optional[str] = None,
) -> bytes:
    """Create a genuine multi-line PDF document using ReportLab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    y = height - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, document_title.upper())
    y -= 28

    c.setFont("Helvetica", 11)
    header_lines = [
        f"DOCUMENT ID: {document_id}",
        f"PO REFERENCE: {po_reference}",
        f"SHIPMENT ID: {shipment_id}",
        f"SUPPLIER: {supplier}",
        f"BUYER: {buyer}",
        f"DATE: {date_str}",
    ]
    for line in header_lines:
        c.drawString(50, y, line)
        y -= 18

    y -= 12
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "LINE ITEMS")
    y -= 20

    c.setFont("Courier", 10)
    for it in items:
        sku = it.get("sku", "SKU-IND-100")
        name = it.get("name", "Industrial Servo Valve Assembly")
        parts = [f"ITEM | SKU: {sku} | NAME: {name}"]
        if it.get("ordered_quantity") is not None:
            parts.append(f"ORDERED: {it['ordered_quantity']}")
        if it.get("delivered_quantity") is not None:
            parts.append(f"DELIVERED: {it['delivered_quantity']}")
        if it.get("damaged_quantity") is not None:
            parts.append(f"DAMAGED: {it['damaged_quantity']}")
        if it.get("unit_price") is not None:
            parts.append(f"PRICE: {it['unit_price']}")
        row_text = " | ".join(parts)
        c.drawString(50, y, row_text)
        y -= 16

    if notes:
        y -= 15
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, y, f"NOTES: {notes}")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_inspection_png_bytes(
    sku: str,
    visible_quantity: Optional[int],
    damaged_quantity: int,
    packaging_condition: str,
    confidence: float = 0.94,
    visual_seed: int = 101,
    slight_perturbation: bool = False,
    low_clarity: bool = False,
) -> bytes:
    """Create a real RGB PNG image depicting pallets/boxes and embedding structured inspection metadata."""
    from PIL.PngImagePlugin import PngInfo

    width, height = 320, 240
    if low_clarity:
        # Low-contrast grey image to trigger genuine visual uncertainty
        img = Image.new("RGB", (width, height), color=(122, 122, 122))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 300, 220], fill=(125, 125, 125))
    else:
        bg_color = (235, 240, 245)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Draw distinct deterministic geometric pallet grid based on visual_seed
        total_boxes = visible_quantity or 10
        cols = 5
        for idx in range(min(total_boxes, 10)):
            r = idx // cols
            c_idx = idx % cols
            x0 = 24 + c_idx * 56
            y0 = 40 + r * 80
            x1 = x0 + 46
            y1 = y0 + 64
            is_damaged_box = idx < damaged_quantity
            box_color = (210, 65, 55) if is_damaged_box else (70, 145, 95)
            if slight_perturbation and idx == 0:
                # Tiny brightness tweak that keeps 64-bit dHash within Hamming distance <= 2
                box_color = (min(255, box_color[0] + 3), box_color[1], box_color[2])
            draw.rectangle([x0, y0, x1, y1], fill=box_color, outline=(30, 35, 45), width=2)
            # Deterministic seed-specific high-contrast sub-blocks so distinct visual_seeds have Hamming distance > 20
            pattern_bits = ((visual_seed * 2654435761) + (idx * 97)) & 0xFFFF
            for sub in range(4):
                sx0 = x0 + 4 + (sub % 2) * 18
                sy0 = y0 + 6 + (sub // 2) * 24
                bit_on = (pattern_bits >> (sub * 3)) & 1
                sub_col = (245, 248, 252) if bit_on else (20, 24, 32)
                draw.rectangle([sx0, sy0, sx0 + 14, sy0 + 18], fill=sub_col)

    dmg_indicators = []
    if damaged_quantity > 0:
        dmg_indicators = ["crushed_box_corner", "compromised_tamper_seal"]
    elif low_clarity:
        dmg_indicators = ["insufficient_visual_clarity", "motion_blur_obstruction"]

    summary = (
        f"Low-contrast obstructed dock image; cannot confirm physical damage for {sku}."
        if low_clarity
        else f"Dock inspection photo showing {visible_quantity} units of {sku} ({damaged_quantity} visibly damaged, condition: {packaging_condition})."
    )

    meta_dict = {
        "product_name": "Industrial Servo Valve Assembly",
        "detected_sku": None if low_clarity else sku,
        "visible_quantity": None if low_clarity else visible_quantity,
        "damaged_quantity": 0 if low_clarity else damaged_quantity,
        "packaging_condition": "unclear" if low_clarity else packaging_condition,
        "damage_indicators": dmg_indicators,
        "visible_labels": [] if low_clarity else [sku, f"BATCH-{visual_seed}"],
        "serial_numbers": [] if low_clarity else [f"SN-{visual_seed}-01"],
        "supports_damage_claim": None if low_clarity else (damaged_quantity > 0),
        "confidence": 0.45 if low_clarity else confidence,
        "visual_summary": summary,
    }

    png_info = PngInfo()
    png_info.add_text("veridock_inspection", json.dumps(meta_dict))

    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=png_info)
    return buf.getvalue()


def generate_wav_voice_bytes(transcript: str, duration_sec: float = 0.25, sample_rate: int = 8000) -> bytes:
    """Create a valid RIFF/WAVE PCM audio file with an appended transcript metadata trailer."""
    buf = io.BytesIO()
    num_samples = int(duration_sec * sample_rate)
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            val = int(4000.0 * math.sin(2.0 * math.pi * 440.0 * (i / sample_rate)))
            frames.extend(struct.pack("<h", val))
        wav_file.writeframes(bytes(frames))

    wav_bytes = buf.getvalue()
    trailer = f"\nTRANSCRIPT:{transcript}".encode("utf-8")
    return wav_bytes + trailer


def get_canonical_benchmark_cases() -> List[Dict[str, Any]]:
    """Return the 5 canonical VeriDock cases + 3 additional evaluation benchmark cases."""
    shared_reuse_image = generate_inspection_png_bytes(
        sku="SKU-IND-100",
        visible_quantity=10,
        damaged_quantity=2,
        packaging_condition="crushed_corner",
        visual_seed=202,
        slight_perturbation=False,
    )
    perturbed_reuse_image = generate_inspection_png_bytes(
        sku="SKU-IND-100",
        visible_quantity=10,
        damaged_quantity=2,
        packaging_condition="crushed_corner",
        visual_seed=202,
        slight_perturbation=True,
    )

    return [
        {
            "case_id": "case_01_clean_delivery",
            "title": "CASE 1: Clean Delivery — 10 Units Servo Valves",
            "description": "Standard B2B delivery where Purchase Order, Delivery Challan, Inspection Photo, and Voice Report all confirm 10 intact units.",
            "supplier_name": "Apex Industrial Components Ltd.",
            "buyer_name": "Vertex Logistics & Manufacturing Corp.",
            "po_number": "PO-2026-1001",
            "expected_outcome": "approved",
            "expected_ordered": 10,
            "expected_delivered": 10,
            "expected_damaged": 0,
            "expected_conflicts": 0,
            "expected_historical_match": False,
            "files": [
                {
                    "filename": "PO-2026-1001_purchase_order.pdf",
                    "role": "purchase_order",
                    "content": generate_pdf_bytes(
                        document_title="Purchase Order",
                        document_id="PO-2026-1001",
                        po_reference="PO-2026-1001",
                        shipment_id="SHP-9001",
                        supplier="Apex Industrial Components Ltd.",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-01",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "ordered_quantity": 10,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "DC-2026-1001_delivery_challan.pdf",
                    "role": "delivery_challan",
                    "content": generate_pdf_bytes(
                        document_title="Delivery Challan",
                        document_id="DC-2026-1001",
                        po_reference="PO-2026-1001",
                        shipment_id="SHP-9001",
                        supplier="Apex Industrial Components Ltd.",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-03",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "delivered_quantity": 10,
                                "damaged_quantity": 0,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "dock_photo_case1_intact.png",
                    "role": "inspection_image",
                    "content": generate_inspection_png_bytes(
                        sku="SKU-IND-100",
                        visible_quantity=10,
                        damaged_quantity=0,
                        packaging_condition="intact",
                        visual_seed=101,
                    ),
                },
                {
                    "filename": "dock_voice_case1.wav",
                    "role": "voice_report",
                    "content": generate_wav_voice_bytes(
                        "All ten boxes of SKU-IND-100 were unloaded intact with zero damaged units."
                    ),
                },
            ],
        },
        {
            "case_id": "case_02_partial_damage",
            "title": "CASE 2: Legitimate Partial Damage — 2 of 10 Units Crushed",
            "description": "PO and Challan show 10 units delivered, while both Dock Inspection Photo and Supervisor Voice Report corroborate 2 crushed units during unloading.",
            "supplier_name": "Apex Industrial Components Ltd.",
            "buyer_name": "Vertex Logistics & Manufacturing Corp.",
            "po_number": "PO-2026-1002",
            "expected_outcome": "partially_approved",
            "expected_ordered": 10,
            "expected_delivered": 10,
            "expected_damaged": 2,
            "expected_conflicts": 0,
            "expected_historical_match": False,
            "files": [
                {
                    "filename": "PO-2026-1002_purchase_order.pdf",
                    "role": "purchase_order",
                    "content": generate_pdf_bytes(
                        document_title="Purchase Order",
                        document_id="PO-2026-1002",
                        po_reference="PO-2026-1002",
                        shipment_id="SHP-9002",
                        supplier="Apex Industrial Components Ltd.",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-01",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "ordered_quantity": 10,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "DC-2026-1002_delivery_challan.pdf",
                    "role": "delivery_challan",
                    "content": generate_pdf_bytes(
                        document_title="Delivery Challan",
                        document_id="DC-2026-1002",
                        po_reference="PO-2026-1002",
                        shipment_id="SHP-9002",
                        supplier="Apex Industrial Components Ltd.",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-03",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "delivered_quantity": 10,
                                "damaged_quantity": 0,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "dock_photo_case2_2damaged.png",
                    "role": "inspection_image",
                    "content": shared_reuse_image,
                },
                {
                    "filename": "dock_voice_case2.wav",
                    "role": "voice_report",
                    "content": generate_wav_voice_bytes(
                        "Two boxes of SKU-IND-100 were damaged during unloading at receiving dock B."
                    ),
                },
            ],
        },
        {
            "case_id": "case_03_conflicting_evidence",
            "title": "CASE 3: Multi-Modal Contradiction — PO 10, Challan 8, Voice 5 Damaged, Image 2 Damaged",
            "description": "Severe cross-modal conflict: PO orders 10 units, Delivery Challan lists 8 units delivered, Voice report claims 5 damaged units, and Inspection Photo shows only 2 damaged units.",
            "supplier_name": "Precision Hydraulics GmbH",
            "buyer_name": "Vertex Logistics & Manufacturing Corp.",
            "po_number": "PO-2026-1003",
            "expected_outcome": "manual_review_required",
            "expected_ordered": 10,
            "expected_delivered": 8,
            "expected_damaged": 2,
            "expected_conflicts": 2,
            "expected_historical_match": False,
            "files": [
                {
                    "filename": "PO-2026-1003_purchase_order.pdf",
                    "role": "purchase_order",
                    "content": generate_pdf_bytes(
                        document_title="Purchase Order",
                        document_id="PO-2026-1003",
                        po_reference="PO-2026-1003",
                        shipment_id="SHP-9003",
                        supplier="Precision Hydraulics GmbH",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-02",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "ordered_quantity": 10,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "DC-2026-1003_delivery_challan.pdf",
                    "role": "delivery_challan",
                    "content": generate_pdf_bytes(
                        document_title="Delivery Challan",
                        document_id="DC-2026-1003",
                        po_reference="PO-2026-1003",
                        shipment_id="SHP-9003",
                        supplier="Precision Hydraulics GmbH",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-04",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "delivered_quantity": 8,
                                "damaged_quantity": 0,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "dock_photo_case3_2damaged.png",
                    "role": "inspection_image",
                    "content": generate_inspection_png_bytes(
                        sku="SKU-IND-100",
                        visible_quantity=8,
                        damaged_quantity=2,
                        packaging_condition="crushed_corner",
                        visual_seed=303,
                    ),
                },
                {
                    "filename": "dock_voice_case3_5damaged.wav",
                    "role": "voice_report",
                    "content": generate_wav_voice_bytes(
                        "Five boxes of SKU-IND-100 were damaged during unloading."
                    ),
                },
            ],
        },
        {
            "case_id": "case_04_reused_evidence",
            "title": "CASE 4: Potentially Reused Evidence — Perceptually Duplicate Damage Photo",
            "description": "New dispute claim submitting a slightly modified/re-compressed inspection photo from Case 2. Perceptual dHash detector flags 'Potentially reused evidence detected.'",
            "supplier_name": "Apex Industrial Components Ltd.",
            "buyer_name": "Vertex Logistics & Manufacturing Corp.",
            "po_number": "PO-2026-1004",
            "expected_outcome": "manual_review_required",
            "expected_ordered": 10,
            "expected_delivered": 10,
            "expected_damaged": 2,
            "expected_conflicts": 0,
            "expected_historical_match": True,
            "files": [
                {
                    "filename": "PO-2026-1004_purchase_order.pdf",
                    "role": "purchase_order",
                    "content": generate_pdf_bytes(
                        document_title="Purchase Order",
                        document_id="PO-2026-1004",
                        po_reference="PO-2026-1004",
                        shipment_id="SHP-9004",
                        supplier="Apex Industrial Components Ltd.",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-04",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "ordered_quantity": 10,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "DC-2026-1004_delivery_challan.pdf",
                    "role": "delivery_challan",
                    "content": generate_pdf_bytes(
                        document_title="Delivery Challan",
                        document_id="DC-2026-1004",
                        po_reference="PO-2026-1004",
                        shipment_id="SHP-9004",
                        supplier="Apex Industrial Components Ltd.",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-05",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "delivered_quantity": 10,
                                "damaged_quantity": 0,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "resubmitted_photo_case4.png",
                    "role": "inspection_image",
                    "content": perturbed_reuse_image,
                },
                {
                    "filename": "dock_voice_case4.wav",
                    "role": "voice_report",
                    "content": generate_wav_voice_bytes(
                        "Two boxes of SKU-IND-100 were damaged during unloading."
                    ),
                },
            ],
        },
        {
            "case_id": "case_05_insufficient_evidence",
            "title": "CASE 5: Insufficient / Weak Visual Evidence — 4 Units Claimed Damaged",
            "description": "Voice report claims 4 damaged units, but uploaded inspection photo is severely obstructed/low-clarity (confidence 0.45). System refuses to invent visual facts and routes to Manual Review.",
            "supplier_name": "Nordic Actuators AB",
            "buyer_name": "Vertex Logistics & Manufacturing Corp.",
            "po_number": "PO-2026-1005",
            "expected_outcome": "manual_review_required",
            "expected_ordered": 10,
            "expected_delivered": 10,
            "expected_damaged": 0,
            "expected_conflicts": 1,
            "expected_historical_match": False,
            "files": [
                {
                    "filename": "PO-2026-1005_purchase_order.pdf",
                    "role": "purchase_order",
                    "content": generate_pdf_bytes(
                        document_title="Purchase Order",
                        document_id="PO-2026-1005",
                        po_reference="PO-2026-1005",
                        shipment_id="SHP-9005",
                        supplier="Nordic Actuators AB",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-04",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "ordered_quantity": 10,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "DC-2026-1005_delivery_challan.pdf",
                    "role": "delivery_challan",
                    "content": generate_pdf_bytes(
                        document_title="Delivery Challan",
                        document_id="DC-2026-1005",
                        po_reference="PO-2026-1005",
                        shipment_id="SHP-9005",
                        supplier="Nordic Actuators AB",
                        buyer="Vertex Logistics & Manufacturing Corp.",
                        date_str="2026-10-05",
                        items=[
                            {
                                "sku": "SKU-IND-100",
                                "name": "Industrial Servo Valve Assembly",
                                "delivered_quantity": 10,
                                "damaged_quantity": 0,
                                "unit_price": 250.0,
                            }
                        ],
                    ),
                },
                {
                    "filename": "blurry_weak_photo_case5.png",
                    "role": "inspection_image",
                    "content": generate_inspection_png_bytes(
                        sku="SKU-IND-100",
                        visible_quantity=None,
                        damaged_quantity=0,
                        packaging_condition="unclear",
                        confidence=0.45,
                        visual_seed=505,
                        low_clarity=True,
                    ),
                },
                {
                    "filename": "dock_voice_case5_4damaged.wav",
                    "role": "voice_report",
                    "content": generate_wav_voice_bytes(
                        "Four boxes of SKU-IND-100 were damaged during unloading."
                    ),
                },
            ],
        },
    ]


def write_synthetic_datasets_to_disk(base_dir: Path) -> List[Dict[str, Any]]:
    """Write all synthetic benchmark files to `datasets/synthetic_cases/` for transparency and inspection."""
    base_dir.mkdir(parents=True, exist_ok=True)
    cases = get_canonical_benchmark_cases()
    manifest = []
    for c in cases:
        case_folder = base_dir / c["case_id"]
        case_folder.mkdir(parents=True, exist_ok=True)
        file_entries = []
        for f in c["files"]:
            fpath = case_folder / f["filename"]
            fpath.write_bytes(f["content"])
            file_entries.append({"filename": f["filename"], "role": f["role"], "size_bytes": len(f["content"])})
        manifest.append(
            {
                "case_id": c["case_id"],
                "title": c["title"],
                "expected_outcome": c["expected_outcome"],
                "files": file_entries,
            }
        )
    (base_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return cases
