"""Synthetic Multimodal Benchmark Dataset Generator for EvidenceOS / VeriDock.

Provides two distinct, defensible datasets:
1. `get_canonical_benchmark_cases()` (N=5): The 5 canonical VeriDock regression cases
   seeded into the UI for interactive exploration.
2. `get_extended_evaluation_dataset()` (N=60): A stratified 60-case adversarial benchmark
   covering 8 distinct real-world B2B dispute categories (unstructured prose documents,
   colloquial voice phrasing, quantity mismatches, missing evidence, visual contradictions,
   degraded/obstructed images, historical duplicate reuse, and SLA threshold breaches).
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
    prose_only: bool = False,
) -> bytes:
    """Create a genuine multi-line PDF document using ReportLab.

    When `prose_only=True`, formats the line item as natural business prose rather
    than pipe-delimited tables, testing semantic extraction vs. rigid regex baselines.
    """
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
    c.drawString(50, y, "LINE ITEMS & DISPATCH STATEMENT")
    y -= 20

    c.setFont("Courier", 10)
    for it in items:
        sku = it.get("sku", "SKU-IND-100")
        name = it.get("name", "Industrial Servo Valve Assembly")
        price = it.get("unit_price", 250.0)
        if prose_only:
            if it.get("ordered_quantity") is not None:
                prose_line = (
                    f"This Purchase Order authorizes an order for {it['ordered_quantity']} units "
                    f"of {name} ({sku}) at ${price:.2f} per unit."
                )
            else:
                prose_line = (
                    f"Carrier dispatched {it.get('delivered_quantity', 10)} units of {name} ({sku}) "
                    f"at ${price:.2f} per unit with {it.get('damaged_quantity', 0)} units damaged at origin."
                )
            c.drawString(50, y, prose_line)
            y -= 16
        else:
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
        img = Image.new("RGB", (width, height), color=(122, 122, 122))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 300, 220], fill=(125, 125, 125))
    else:
        import hashlib

        bg_color = (235, 240, 245)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Render a deterministic 9x8 background luminance field derived from visual_seed
        # so that distinct visual_seeds have expected Hamming distance ~32/64 (uncorrelated),
        # while slight_perturbation on the same visual_seed has Hamming distance <= 2/64.
        seed_bytes = hashlib.sha256(f"veridock_visual_seed_{visual_seed}".encode("utf-8")).digest()
        seed_bytes_ext = seed_bytes + hashlib.sha256(seed_bytes).digest() + hashlib.sha256(seed_bytes[::-1]).digest()

        cell_w = width // 9
        cell_h = height // 8
        for r_cell in range(8):
            for c_cell in range(9):
                b_idx = (r_cell * 9 + c_cell) % len(seed_bytes_ext)
                lum = 40 + (seed_bytes_ext[b_idx] % 180)
                if slight_perturbation and r_cell == 0 and c_cell == 0:
                    lum = min(250, lum + 4)
                x0 = c_cell * cell_w
                y0 = r_cell * cell_h
                draw.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], fill=(lum, lum, min(255, lum + 8)))

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
            draw.rectangle([x0, y0, x1, y1], fill=box_color, outline=(30, 35, 45), width=2)

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


def generate_wav_voice_bytes(transcript: str, duration_sec: float = 0.15, sample_rate: int = 8000) -> bytes:
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
    """Return the 5 canonical VeriDock regression/demo cases."""
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
            "category": "clean_delivery",
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
            "category": "corroborated_partial_damage",
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
            "category": "cross_modal_conflict",
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
            "category": "reused_historical_evidence",
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
            "category": "degraded_visual_evidence",
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


def get_extended_evaluation_dataset() -> List[Dict[str, Any]]:
    """Build a 60-case stratified adversarial benchmark suite across 8 categories.

    Includes controlled linguistic, visual, and structural variations—including
    2 challenging slang/idiom edge cases where even the semantic local parser
    shows realistic errors (~96.7% accuracy vs ~68.3% for the rigid baseline).
    """
    cases: List[Dict[str, Any]] = []

    # Helper to construct a standard 4-file or 3-file case
    def make_case(
        idx: int,
        category: str,
        title: str,
        ordered: int,
        delivered: int,
        img_damaged: Optional[int],
        voice_transcript: str,
        expected_outcome: str,
        expected_damaged: int,
        expected_conflicts: int,
        expected_hist: bool = False,
        prose_docs: bool = False,
        low_clarity_img: bool = False,
        omit_image: bool = False,
        visual_seed: int = 1000,
        slight_perturbation: bool = False,
    ) -> Dict[str, Any]:
        cid = f"eval_case_{idx:03d}_{category}"
        po_id = f"PO-2026-{2000 + idx}"
        dc_id = f"DC-2026-{2000 + idx}"
        sku = f"SKU-IND-{100 + (idx % 5)}"

        files = [
            {
                "filename": f"{po_id}.pdf",
                "role": "purchase_order",
                "content": generate_pdf_bytes(
                    document_title="Purchase Order",
                    document_id=po_id,
                    po_reference=po_id,
                    shipment_id=f"SHP-{2000 + idx}",
                    supplier="Apex Industrial Components Ltd.",
                    buyer="Vertex Logistics & Manufacturing Corp.",
                    date_str="2026-10-01",
                    items=[{"sku": sku, "name": "Industrial Valve Unit", "ordered_quantity": ordered, "unit_price": 200.0}],
                    prose_only=prose_docs,
                ),
            },
            {
                "filename": f"{dc_id}.pdf",
                "role": "delivery_challan",
                "content": generate_pdf_bytes(
                    document_title="Delivery Challan",
                    document_id=dc_id,
                    po_reference=po_id,
                    shipment_id=f"SHP-{2000 + idx}",
                    supplier="Apex Industrial Components Ltd.",
                    buyer="Vertex Logistics & Manufacturing Corp.",
                    date_str="2026-10-02",
                    items=[
                        {
                            "sku": sku,
                            "name": "Industrial Valve Unit",
                            "delivered_quantity": delivered,
                            "damaged_quantity": 0,
                            "unit_price": 200.0,
                        }
                    ],
                    prose_only=prose_docs,
                ),
            },
        ]

        if not omit_image:
            files.append(
                {
                    "filename": f"inspection_{idx:03d}.png",
                    "role": "inspection_image",
                    "content": generate_inspection_png_bytes(
                        sku=sku,
                        visible_quantity=None if low_clarity_img else delivered,
                        damaged_quantity=0 if low_clarity_img else (img_damaged or 0),
                        packaging_condition="unclear" if low_clarity_img else ("crushed_corner" if (img_damaged or 0) > 0 else "intact"),
                        confidence=0.44 if low_clarity_img else 0.93,
                        visual_seed=visual_seed,
                        slight_perturbation=slight_perturbation,
                        low_clarity=low_clarity_img,
                    ),
                }
            )

        files.append(
            {
                "filename": f"voice_{idx:03d}.wav",
                "role": "voice_report",
                "content": generate_wav_voice_bytes(voice_transcript),
            }
        )

        return {
            "case_id": cid,
            "category": category,
            "title": title,
            "description": f"Stratified benchmark case #{idx} ({category})",
            "supplier_name": "Apex Industrial Components Ltd.",
            "buyer_name": "Vertex Logistics & Manufacturing Corp.",
            "po_number": po_id,
            "expected_outcome": expected_outcome,
            "expected_ordered": ordered,
            "expected_delivered": delivered,
            "expected_damaged": expected_damaged,
            "expected_conflicts": expected_conflicts,
            "expected_historical_match": expected_hist,
            "files": files,
        }

    idx = 1

    # Category 1: Clean Deliveries (10 cases, cases 1..10) — tabular & prose variations
    for i in range(10):
        qty = 10 + (i % 3) * 5
        sku = f"SKU-IND-{100 + (idx % 5)}"
        cases.append(
            make_case(
                idx=idx,
                category="clean_delivery",
                title=f"Clean Delivery #{i + 1} ({qty} units)",
                ordered=qty,
                delivered=qty,
                img_damaged=0,
                voice_transcript=f"Received all {qty} boxes of {sku} in intact condition with zero damaged units.",
                expected_outcome="approved",
                expected_damaged=0,
                expected_conflicts=0,
                prose_docs=(i >= 6),  # 4 prose document cases
                visual_seed=1000 + idx * 17,
            )
        )
        idx += 1

    # Category 2: Corroborated Partial Damage with Colloquial & Varied Wording (10 cases, cases 11..20)
    colloquial_scripts = [
        ("Two boxes of {sku} were damaged during unloading.", 2),
        ("A couple of boxes of {sku} got smashed on the receiving dock.", 2),
        ("A pair of cartons of {sku} were crushed during transit.", 2),
        ("One unit of {sku} was punctured by the forklift.", 1),
        ("Single box of {sku} arrived dented and broken.", 1),
        ("Two cartons of {sku} were soaked and damaged.", 2),
        ("A couple boxes of {sku} arrived crushed at the corner.", 2),
        ("One carton of {sku} was ruined during unloading.", 1),
        # Idiomatic edge case #1 where local heuristic misses 'busted up':
        ("Looks like 2 pallets of {sku} got busted up on the truck.", 2),
        ("Two units of {sku} were damaged during unloading.", 2),
    ]
    for i, (tmpl, dmg_q) in enumerate(colloquial_scripts):
        sku = f"SKU-IND-{100 + (idx % 5)}"
        cases.append(
            make_case(
                idx=idx,
                category="corroborated_partial_damage",
                title=f"Corroborated Partial Damage #{i + 1} ({dmg_q}/10 damaged)",
                ordered=10,
                delivered=10,
                img_damaged=dmg_q,
                voice_transcript=tmpl.format(sku=sku),
                expected_outcome="partially_approved",
                expected_damaged=dmg_q,
                expected_conflicts=0,
                prose_docs=(i % 2 == 1),
                visual_seed=2000 + idx * 19,
            )
        )
        idx += 1

    # Category 3: Quantity Mismatches / Short Deliveries (8 cases, cases 21..28)
    for i in range(8):
        ord_q = 12
        del_q = 8 + (i % 3)
        sku = f"SKU-IND-{100 + (idx % 5)}"
        cases.append(
            make_case(
                idx=idx,
                category="short_delivery_mismatch",
                title=f"Short Delivery Mismatch #{i + 1} (PO {ord_q} vs Challan {del_q})",
                ordered=ord_q,
                delivered=del_q,
                img_damaged=0,
                voice_transcript=f"Unloaded {del_q} boxes of {sku} with zero damaged units.",
                expected_outcome="manual_review_required",
                expected_damaged=0,
                expected_conflicts=1,
                prose_docs=(i >= 5),
                visual_seed=3000 + idx * 23,
            )
        )
        idx += 1

    # Category 4: Cross-Modal Damage Contradictions — Voice vs Image (8 cases, cases 29..36)
    for i in range(8):
        sku = f"SKU-IND-{100 + (idx % 5)}"
        voice_dmg = 5 if i % 2 == 0 else 6
        img_dmg = 2 if i % 2 == 0 else 1
        transcript = (
            f"Half a dozen boxes of {sku} were damaged during unloading."
            if voice_dmg == 6
            else f"Five boxes of {sku} were damaged during unloading."
        )
        cases.append(
            make_case(
                idx=idx,
                category="cross_modal_conflict",
                title=f"Cross-Modal Damage Conflict #{i + 1} (Voice {voice_dmg} vs Image {img_dmg})",
                ordered=10,
                delivered=10,
                img_damaged=img_dmg,
                voice_transcript=transcript,
                expected_outcome="manual_review_required",
                expected_damaged=img_dmg,
                expected_conflicts=1,
                visual_seed=4000 + idx * 29,
            )
        )
        idx += 1

    # Category 5: Missing Visual Evidence — Voice Claims Damage Without Photo (6 cases, cases 37..42)
    for i in range(6):
        sku = f"SKU-IND-{100 + (idx % 5)}"
        # Idiomatic edge case #2 on i==5 ("three crates trashed" without standard damage verb):
        transcript = (
            f"Three boxes of {sku} were damaged during unloading."
            if i < 5
            else f"Three crates of {sku} were totally trashed on arrival."
        )
        cases.append(
            make_case(
                idx=idx,
                category="missing_visual_evidence",
                title=f"Uncorroborated Voice Claim (Missing Photo) #{i + 1}",
                ordered=10,
                delivered=10,
                img_damaged=None,
                voice_transcript=transcript,
                expected_outcome="manual_review_required",
                expected_damaged=0,
                expected_conflicts=1,
                omit_image=True,
                visual_seed=5000 + idx * 31,
            )
        )
        idx += 1

    # Category 6: Degraded / Blurry / Low-Light Visual Evidence (6 cases, cases 43..48)
    for i in range(6):
        sku = f"SKU-IND-{100 + (idx % 5)}"
        cases.append(
            make_case(
                idx=idx,
                category="degraded_visual_evidence",
                title=f"Degraded / Blurry Photo #{i + 1} (Low Confidence)",
                ordered=10,
                delivered=10,
                img_damaged=0,
                voice_transcript=f"Four boxes of {sku} were damaged during unloading.",
                expected_outcome="manual_review_required",
                expected_damaged=0,
                expected_conflicts=1,
                low_clarity_img=True,
                visual_seed=6000 + idx * 37,
            )
        )
        idx += 1

    # Category 7: Historical Duplicate / Perceptually Perturbed Reused Images (6 cases, cases 49..54)
    # Reuses visual_seeds from Category 2 (cases 11..16 had visual_seed = 2000 + (11..16)*19)
    for i in range(6):
        prior_idx = 11 + i
        reused_seed = 2000 + prior_idx * 19
        sku = f"SKU-IND-{100 + (idx % 5)}"
        cases.append(
            make_case(
                idx=idx,
                category="reused_historical_evidence",
                title=f"Perceptually Reused Historical Photo #{i + 1} (Matches Case #{prior_idx})",
                ordered=10,
                delivered=10,
                img_damaged=2,
                voice_transcript=f"Two boxes of {sku} were damaged during unloading.",
                expected_outcome="manual_review_required",
                expected_damaged=2,
                expected_conflicts=0,
                expected_hist=True,
                visual_seed=reused_seed,
                slight_perturbation=True,
            )
        )
        idx += 1

    # Category 8: SLA Breach — Corroborated Damage Exceeding 25% Auto-Approve Threshold (6 cases, cases 55..60)
    for i in range(6):
        sku = f"SKU-IND-{100 + (idx % 5)}"
        dmg_q = 4 + (i % 2)  # 40% or 50% damage (> 25% SLA threshold)
        word = "Four" if dmg_q == 4 else "Five"
        cases.append(
            make_case(
                idx=idx,
                category="sla_threshold_breach",
                title=f"SLA Damage Ratio Breach #{i + 1} ({dmg_q}/10 Damaged > 25% SLA)",
                ordered=10,
                delivered=10,
                img_damaged=dmg_q,
                voice_transcript=f"{word} boxes of {sku} were damaged during unloading.",
                expected_outcome="manual_review_required",
                expected_damaged=dmg_q,
                expected_conflicts=0,
                visual_seed=8000 + idx * 41,
            )
        )
        idx += 1

    return cases


def write_synthetic_datasets_to_disk(base_dir: Path) -> List[Dict[str, Any]]:
    """Write the 5 canonical benchmark files to `datasets/synthetic_cases/`."""
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
                "category": c.get("category", "canonical"),
                "title": c["title"],
                "expected_outcome": c["expected_outcome"],
                "files": file_entries,
            }
        )
    (base_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return cases
