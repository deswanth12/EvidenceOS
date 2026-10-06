# Failure Analysis & Error Taxonomy Report

**Evaluation Suite**: Blind Held-Out Test Set (`N = 150` cases, `564` files across `25` categories)  
**Machine-Readable Failure Artifact**: [`evaluation/failures.json`](../evaluation/failures.json)

---

## 1. Executive Summary

A trustworthy evaluation must report and dissect its failures with the same rigor as its successes. Every failed case in the EvidenceOS evaluation suite is automatically categorized into one of **10 standardized failure taxonomy codes**:

1. `DOCUMENT_EXTRACTION_ERROR`
2. `IMAGE_INTERPRETATION_ERROR`
3. `VOICE_INTERPRETATION_ERROR`
4. `OCR_OR_TEXT_NOISE_ERROR`
5. `ENTITY_LINKING_ERROR`
6. `CONFLICT_MISDETECTION`
7. `DUPLICATE_HASH_MISS`
8. `RULE_THRESHOLD_MISMATCH`
9. `OVERCONFIDENT_DECISION`
10. `FALSE_ABSTENTION`

### Failure Count Across Evaluated Systems (`N = 150` Held-Out Cases)

| System | Total Failures | Error Rate | Confident Errors (Unsafe Auto-Decisions) | Conservative Abstentions (`FALSE_ABSTENTION` / Safe Fallback) |
| :--- | :---: | :---: | :---: | :---: |
| **System D: Full EvidenceOS (Semantic AI + Rules)** | **9** | **6.0%** | **0 (`0.0%`)** | **9 (`6.0%`)** |
| **Baseline B: Structured Deterministic Normalizer** | `33` | `22.0%` | `0 (`0.0%`)` | `33 (`22.0%`)` |
| **Baseline A: Strict Regex / Keyword Baseline** | `42` | `28.0%` | `6 (`4.0%`)` | `36 (`24.0%`)` |
| **System C: Semantic Multimodal AI Only (No Rules)** | `84` | `56.0%` | **72 (`48.0%`)** | `12 (`8.0%`)` |

---

## 2. Complete Breakdown of All 9 Failures in `System D` (`Full EvidenceOS`)

Across all `150` blind held-out cases, `System D` makes **0 unsafe auto-settlement errors** (`Confident Error Rate = 0.0%`). All **9 errors** occur on `REAL_WORLD_INSPIRED` cases where ground truth expects `approved_partial_settlement`, but a modality-level extraction or linking failure creates a cross-modal contradiction that safely routes the case to `manual_review_required`.

### 2.1 `ENTITY_LINKING_ERROR` (3 Cases: `heldout_case_142`, `heldout_case_143`, `heldout_case_144`)
- **Adversarial Category**: `multi_sku_dispute` (`REAL_WORLD_INSPIRED`)
- **Expected Decision**: `approved_partial_settlement`
- **Predicted Decision**: `manual_review_required`
- **Root Cause**:
  - The Purchase Order and Delivery Challan list two distinct line items: `SKU-IND-201` (100 units, 0 damaged) and `SKU-IND-202` (`12`, `14`, and `16` damaged units respectively).
  - The voice transcript correctly attributes the damaged units to `SKU-IND-202`.
  - However, in **Blind Mode**, the dock inspection photograph is a pure pixel rendering of the pallet grid with no embedded metadata or readable per-box barcode text. Consequently, `analyze_pallet_pixels_blind` detects the damaged red parcels visually (`2` damaged cells) but links the image claim to the default primary shipment item (`SKU-IND-201`).
  - During entity resolution and conflict detection, the pipeline sees a damage claim on `SKU-IND-201` (from the image) contradicting `0` damaged on `SKU-IND-201` (from the Challan), triggering Rule `R3_CONFLICTING_EVIDENCE_MANUAL_REVIEW`.
- **Remediation Path**: Add optical barcode/QR recognition (`pyzbar` / OCR bounding boxes) on pallet labels so visual damage claims bind to specific secondary SKUs in multi-item shipments.

### 2.2 `VOICE_INTERPRETATION_ERROR` (2 Cases: `heldout_case_077`, `heldout_case_078`)
- **Adversarial Category**: `colloquial_wording` (`REAL_WORLD_INSPIRED`)
- **Expected Decision**: `approved_partial_settlement`
- **Predicted Decision**: `manual_review_required`
- **Root Cause**:
  - `heldout_case_077` uses Australian/Commonwealth dock slang: *"Mate, 14 of the units are completely munted from transit."*
  - `heldout_case_078` uses informal idiom without standard damage verbs: *"Counted 100 off the truck, 16 of them are total toast."*
  - Because neither *"munted"* nor *"total toast"* appears in the semantic damage verb lexicon, the voice extractor records `damaged_quantity = 0` (`clean_delivery_statement`), while the Delivery Challan and blind pixel CV both detect damaged units.
  - The conflict detector flags `QUANTITY_MISMATCH` between the voice report (`0` damaged) and the Challan/Image (`14` and `16` damaged), escalating to `manual_review_required`.
- **Why We Did Not Patch the Lexicon After Seeing Held-Out Results**: Per our strict evaluation integrity protocol, we never add held-out vocabulary back into the extractor to inflate benchmark scores.

### 2.3 `OCR_OR_TEXT_NOISE_ERROR` (2 Cases: `heldout_case_083`, `heldout_case_084`)
- **Adversarial Category**: `typos_and_ocr_noise` (`REAL_WORLD_INSPIRED`)
- **Expected Decision**: `approved_partial_settlement`
- **Predicted Decision**: `manual_review_required`
- **Root Cause**:
  - `heldout_case_083` substitutes letters for digits inside the quantity token itself (`Ordered: 100 | Delivered: 100 | Damaged: lO` where `lO` represents `10`).
  - `heldout_case_084` corrupts the header keywords with heavy leetspeak/OCR noise (`0RD3R3D: 100 | D3L1V3R3D: 100 | D4M4G3D: 12`).
  - The document extractor fails to parse `ordered_quantity` (`0`), triggering a `MISSING_CRITICAL_EVIDENCE` conflict and Rule `R4_INSUFFICIENT_EVIDENCE_ABSTENTION`.

### 2.4 `DOCUMENT_EXTRACTION_ERROR` (2 Cases: `heldout_case_089`, `heldout_case_090`)
- **Adversarial Category**: `multilingual_or_mixed_terms` (`REAL_WORLD_INSPIRED`)
- **Expected Decision**: `approved_partial_settlement`
- **Predicted Decision**: `manual_review_required`
- **Root Cause**:
  - While the semantic extractor supports English, Spanish (`Pedido`, `Entregado`, `Dañados`), and French (`Commandé`, `Livré`, `Endommagé`), cases `089` and `090` use German procurement headers (`Bestellmenge: 100 | Geliefert: 100 | Defekt: 10` and `12`).
  - The unparsed German document yields `ordered_quantity = 0`, causing the deterministic safety rule `R4_INSUFFICIENT_EVIDENCE_ABSTENTION` to abstain safely.

---

## 3. Comparative Failure Taxonomy Across Baselines

| Failure Taxonomy Code | `Baseline A` (Regex) | `Baseline B` (Normalizer) | `System C` (AI Only, No Rules) | `System D` (Full EvidenceOS) |
| :--- | :---: | :---: | :---: | :---: |
| **`VOICE_INTERPRETATION_ERROR`** | `18` | `15` | `2` | **2** |
| **`DOCUMENT_EXTRACTION_ERROR`** | `14` | `8` | `2` | **2** |
| **`OCR_OR_TEXT_NOISE_ERROR`** | `4` | `4` | `2` | **2** |
| **`ENTITY_LINKING_ERROR`** | `0` | `0` | `3` | **3** |
| **`OVERCONFIDENT_DECISION`** | `6` | `0` | **72** | **0** |
| **`RULE_THRESHOLD_MISMATCH`** | `0` | `6` | `3` | **0** |
| **Total Failures (out of 150)** | **42 (`28.0%`)** | **33 (`22.0%`)** | **84 (`56.0%`)** | **9 (`6.0%`)** |

### Why `System C` (Standalone Semantic AI Without Rules) Fails Catastrophically (`84` Errors)
When the deterministic rule engine (`R1–R8`) is disabled in `System C`:
1. **SLA Breach Blindness**: `System C` approves partial settlements on claims filed `72+` hours after delivery (`late_claim_submission`) because the multimodal evidence itself is internally consistent.
2. **High-Value & Severe-Ratio Auto-Payouts**: `System C` auto-settles disputes exceeding the `$5,000` manual review cap (`high_value_manual_review`) and `>30%` catastrophic damage ratios (`high_damage_ratio`).
3. **Uncorroborated Single-Source Claims**: When a voice report claims damage (`single_source_damage_claim`) without visual corroboration, `System C` issues a partial payout instead of abstaining.
4. **Degraded Evidence Overconfidence**: Even when an image is flagged as `UNCERTAINTY` (`low_light_image` or `blurry_image`), `System C` settles the claim based on the remaining text documents instead of enforcing Rule `R4_INSUFFICIENT_EVIDENCE_ABSTENTION`.
