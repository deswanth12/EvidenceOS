# EvidenceOS Research Report: Empirical Evaluation of Hybrid Semantic Multimodal Extraction and Deterministic Rule Reasoning for B2B Dispute Verification

**Document Status**: Reproducible Evaluation Report (`v2.0`)  
**Fixed Random Seed**: `42`  
**Evaluation Artifact**: [`evaluation/results.json`](../evaluation/results.json) | [`evaluation/failures.json`](../evaluation/failures.json)

---

## 1. Abstract

High-stakes B2B delivery and procurement dispute resolution requires reconciling heterogeneous multimodal evidence—Purchase Orders (PDF), Delivery Challans (PDF), Dock Inspection Photographs (PNG), Warehouse Voice Reports (WAV), and Historical Claim Ledgers—against strict Service-Level Agreements (SLAs). While Large Language Models (LLMs) and multimodal extractors handle linguistic variation well, purely generative decision pipelines suffer from uncalibrated confidence, susceptibility to prompt injection, and inability to enforce deterministic contract boundaries. Conversely, purely deterministic regex pipelines fail when confronted with OCR noise, colloquial speech, multilingual terminology, or visual degradation.

In this study, we evaluate **EvidenceOS (`VeriDock`)**, a hybrid verification architecture that pairs **semantic multimodal extraction** (explicitly typed into `FACT`, `INFERENCE`, `RULE`, and `UNCERTAINTY`) with a **64-bit perceptual image hashing index (`dHash`)** and a **deterministic rule engine**. Across an untouched, blind **150-case Held-Out Test Set (`564` files across `25` adversarial categories)** with all filename and metadata leakage removed, **EvidenceOS (`System D`)** achieves **94.0% decision accuracy** (`141/150`, 95% Wilson CI `[89.0%, 96.8%]`, Macro-F1 `0.9132`) and a **0.0% Confident Error Rate** (`0/150` wrong automated financial settlements). It substantially outperforms a **Strict Regex Baseline (`Baseline A`)** at **72.0%** (`108/150`, CI `[64.3%, 78.6%]`), a **Structured Deterministic Normalizer (`Baseline B`)** at **78.0%** (`117/150`, CI `[70.7%, 83.9%]`), and a **Standalone Semantic Multimodal AI without the Deterministic Rule Engine (`System C`)** at **44.0%** (`66/150`, CI `[36.3%, 52.0%]`, Confident Error Rate **48.0%**).

---

## 2. Problem Statement

B2B supply chain disputes routinely stall working capital and audit workflows because physical evidence arrives in incompatible modalities with conflicting claims:
1. **Cross-Modal Contradictions**: A signed Delivery Challan states 0 damaged units (`clean_receipt`), while a dock supervisor's voice recording and pallet photo claim 15 crushed units.
2. **Evidence Quality & Physical Degradation**: Dock photos may be under-exposed (`mean luminance < 28.0`), motion-blurred (`luminance σ < 12.0`), or physically occluded (`center-band σ < 6.0`), and voice notes frequently use hedged language (*"maybe around 10 or 12 damaged, hard to tell"*).
3. **Cross-Case Evidence Fraud**: Claimants may resubmit photographs of damaged goods from a settled historical dispute—either byte-identical or perturbed via recompression, cropping, or brightness adjustments.
4. **Strict Contractual Boundaries**: SLA reporting windows (e.g., 48-hour filing deadline) and high-value manual review thresholds (`>= $5,000` or `> 30%` damage ratio) require exact mathematical enforcement rather than probabilistic text generation.

---

## 3. Research Questions

### Primary Research Question
> **Does semantic multimodal evidence extraction combined with deterministic rule reasoning improve evidence verification accuracy and safety compared with strict deterministic extraction baselines and standalone semantic AI?**

### Secondary Research Questions
1. **RQ1 (Semantic Benefit)**: Where does semantic AI provide the largest accuracy improvement over deterministic extractors?
2. **RQ2 (Deterministic Advantage)**: Where does deterministic rule logic outperform standalone semantic AI?
3. **RQ3 (Modality Failures)**: Which evidence modalities contribute most to residual pipeline failures?
4. **RQ4 (Degraded Evidence)**: How does degraded visual or acoustic evidence affect pipeline reliability and abstention behavior?
5. **RQ5 (Contradictory Evidence)**: How accurately does the conflict graph isolate cross-modal contradictions?
6. **RQ6 (Abstention Calibration)**: How often does the system abstain (`manual_review_required`) when evidence is insufficient, degraded, or conflicted?
7. **RQ7 (Linguistic Sensitivity)**: How sensitive are each of the four evaluated systems to colloquial phrasing, OCR typos, and multilingual terminology?
8. **RQ8 (Historical Duplicate Robustness)**: How robust is 64-bit perceptual `dHash` compared with cryptographic `SHA-256` under image perturbations?
9. **RQ9 (Latency & Cost Tradeoffs)**: What latency and computational overhead does semantic multimodal processing introduce per stage?

---

## 4. System Architecture

EvidenceOS enforces a 12-stage epistemic verification pipeline where every extracted claim carries source provenance (`evidence_id`, `sha256`, character/pixel span, confidence, and `EpistemologicalType`):

```text
Raw Artifacts (PDF, PNG, WAV, JSON, CSV)
  │
  ├─► [1. Ingestion & Guardrails] ──► SHA-256 + 64-bit dHash + Prompt Injection Sanitizer
  ├─► [2. Multimodal Extraction]  ──► PDF Parser + Blind Pixel CV + Acoustic/Transcript Analyzer
  ├─► [3. Epistemic Typing]       ──► Classifies claims into FACT | INFERENCE | UNCERTAINTY
  ├─► [4. Normalization]          ──► Canonical quantities, timestamps, & SKU normalization
  ├─► [5. Entity Resolution]      ──► Links PO, Challan, Image, & Voice nodes to SKU entities
  ├─► [6. Evidence DAG]           ──► Constructs directed provenance graph
  ├─► [7. Conflict Detection]     ──► Cross-examines quantity, damage, SKU, & missing-doc conflicts
  ├─► [8. Historical Matching]    ──► Queries prior cases via SHA-256 & Hamming(dHash) <= 6
  ├─► [9. Deterministic Rules]    ──► Evaluates 8 prioritized SLA & epistemic safety rules (R1–R8)
  └─► [10. Decision & Audit Log]  ──► Emits Decision + Confidence + Hash-Chained Audit Entry
```

### Blind Pixel-Level Computer Vision (Zero Leakage)
To ensure scientific validity, all filename and PNG metadata hints were stripped from the vision extractor (`analyze_pallet_pixels_blind` in `core/ai/provider.py`). The vision module computes:
- **Global Mean Luminance ($\mu_Y$)**: Flags `low_light` (`UNCERTAINTY`) when $\mu_Y < 28.0$.
- **Luminance Standard Deviation ($\sigma_Y$)**: Flags `blurry` (`UNCERTAINTY`) when $\sigma_Y < 12.0$.
- **Center-Band Occlusion ($\sigma_{\text{center}}$)**: Flags `occluded` (`UNCERTAINTY`) when a solid obstruction band depresses center variance ($\sigma_{\text{center}} < 6.0$).
- **2×5 Parcel Grid Chromaticity**: Evaluates red-vs-green channel dominance across the 10 pallet parcel cells to count visibly damaged boxes directly from pixel intensities.

---

## 5. Dataset Construction & Leakage Elimination

To prevent benchmark overfitting, EvidenceOS maintains three strictly separated datasets generated deterministically (`seed=42`):

| Dataset Split | Cases | Total Files | Purpose | Leakage Controls |
| :--- | :---: | :---: | :--- | :--- |
| **1. Canonical Regression (`canonical_5`)** | `5` | `20` | Fast CI smoke test covering the 5 foundational dispute archetypes | Standard demo filenames |
| **2. Development Benchmark (`development_60`)** | `60` | `234` | Prompt, normalizer, and rule tuning across 10 categories | Controlled synthetic variations |
| **3. Blind Held-Out Test Set (`heldout_150`)** | `150` | `564` | Primary research evaluation across **25 adversarial categories** (`6` cases/category) | **Strict Blind Mode**: Generic filenames (`artifact_01.pdf`..`artifact_04.wav`), neutral case IDs (`heldout_case_001`..`150`), zero PNG text chunks, pure pixel rendering |

### Data Origin Labeling & Human Audit Verification
Every case in the Held-Out Test Set is explicitly tagged with its `data_origin`:
- **`SYNTHETIC` (`N = 116`)**: Procedurally generated documents, pixel-rendered inspection scenes, and synthesized WAV telemetry.
- **`REAL_WORLD_INSPIRED` (`N = 34`)**: Cases modeled on real logistics failure modes—colloquial dock slang (`colloquial_wording`), OCR character substitutions (`typos_and_ocr_noise`), mixed English/German/Spanish/French invoices (`multilingual_or_mixed_terms`), hedged supervisor voice reports (`hedged_uncertain_voice`), and multi-SKU partial damage (`multi_sku_dispute`).

A stratified 20% subset (`30/150` cases across all 25 categories, saved in [`evaluation/datasets/human_validation_sample_30.json`](../evaluation/datasets/human_validation_sample_30.json)) underwent independent dual-reviewer verification, achieving **96.7% (`29/30`) inter-reviewer agreement** on expected decision, ground-truth conflict presence, and abstention requirement (`1` borderline calibration note on `heldout_case_043` regarding exact 48.0h SLA boundary handling).

---

## 6. Baseline Systems

We evaluate four distinct system configurations on identical inputs:

1. **Baseline A — Strict Regex / Keyword Pipeline (`OfflineDeterministicBaselineProvider` + Rule Engine)**:
   - Uses rigid `Ordered:` / `Delivered:` / `Damaged:` regular expressions and literal keyword matching. Does not perform synonym expansion, semantic speech parsing, or blind pixel grid inspection.
2. **Baseline B — Structured Deterministic Normalizer (`StructuredNormalizedBaselineProvider` + Rule Engine)**:
   - A stronger non-LLM engineering baseline that normalizes tabular headers (`Qty Dispatched`, `Broken Units`, ` Defekt`), parses number words (`one`..`twenty`), and applies deterministic rule checks, but lacks contextual semantic disambiguation for complex spoken narratives.
3. **System C — Semantic Multimodal AI Only (`GeminiMultimodalProvider`, `use_rule_engine=False`)**:
   - Uses the full semantic multimodal extractor and conflict detector, but bypasses the deterministic rule engine (`R1–R8`), relying on direct evidence-weighted confidence heuristics to settle claims.
4. **System D — Full EvidenceOS (`GeminiMultimodalProvider` + Perceptual `dHash` + Deterministic Rule Engine)**:
   - Combines semantic multimodal extraction, explicit `UNCERTAINTY` propagation, 64-bit `dHash` historical duplicate detection, and the 8-rule deterministic decision engine.

---

## 7. Evaluation Metrics

All proportions are reported with **95% Wilson Score Confidence Intervals**:
- **Decision Accuracy & Macro-F1**: Exact match and unweighted class-averaged F1 across `approved_full`, `approved_partial_settlement`, `rejected_duplicate_evidence`, `rejected_late_filing`, and `manual_review_required`.
- **Confident Error Rate (Safety Metric)**: Percentage of all cases where the system issues an **incorrect automated settlement or rejection** (`approved_*` or `rejected_*`) when the ground truth requires `manual_review_required` or a different outcome. Conservative abstentions (`manual_review_required`) are tracked separately from dangerous confident errors.
- **Exact Case Field Match & Individual Field Accuracy**: Accuracy across `ordered_qty`, `delivered_qty`, `doc_damaged_qty`, and `voice_damaged_qty` (`600` total fields in `heldout_150`).
- **Conflict Precision, Recall, & F1**: Set-level evaluation of detected cross-modal contradictions.
- **Appropriate Abstention Rate**: Recall on the `108` held-out cases whose ground-truth label is `manual_review_required`.

---

## 8. Quantitative Results Across Splits & Baselines

### 8.1 Performance Across Dataset Splits (`System D: Full EvidenceOS`)

| Metric | Canonical Regression (`N=5`) | Development Benchmark (`N=60`) | Blind Held-Out Test Set (`N=150`) |
| :--- | :---: | :---: | :---: |
| **Decision Accuracy (95% CI)** | **100.0%** (`[56.6%, 100.0%]`) | **96.7%** (`[88.6%, 99.1%]`) | **94.0%** (`[89.0%, 96.8%]`) |
| **Macro-F1** | `1.0000` | `0.9583` | `0.9132` |
| **Exact Case Field Match (95% CI)** | `100.0%` (`[56.6%, 100.0%]`) | `100.0%` (`[94.0%, 100.0%]`) | `89.3%` (`[83.4%, 93.3%]`) |
| **Individual Field Accuracy (95% CI)** | `100.0%` (`[83.9%, 100.0%]`) | `100.0%` (`[98.4%, 100.0%]`) | `95.6%` (`[93.2%, 97.1%]`) |
| **Entity Resolution Accuracy** | `100.0%` | `100.0%` | `100.0%` |
| **Conflict Precision / Recall / F1** | `100.0%` / `100.0%` / `1.000` | `96.4%` / `96.4%` / `0.964` | `90.6%` / `100.0%` / `0.951` |
| **Duplicate Detection F1** | `1.0000` | `1.0000` | `1.0000` (`100.0%` acc) |
| **Appropriate Abstention Rate** | `100.0%` (`2/2`) | `93.3%` (`14/15`) | `100.0%` (`108/108`) |
| **Confident Error Rate (Dangerous Errors)** | **0.0%** (`0/5`) | **1.7%** (`1/60`) | **0.0%** (`0/150`) |

**Split Breakdown on Held-Out 150 by Data Origin**:
- **`SYNTHETIC` (`N = 116`)**: **100.0%** Decision Accuracy (`116/116`, 95% CI `[96.8%, 100.0%]`).
- **`REAL_WORLD_INSPIRED` (`N = 34`)**: **73.5%** Decision Accuracy (`25/34`, 95% CI `[56.9%, 85.4%]`), reflecting genuine errors on unseen slang, severe OCR corruptions, untranslated German headers, and blind multi-SKU attribution.

### 8.2 Four-System Comparison on Blind Held-Out Test Set (`N = 150`)

| System Architecture | Decision Accuracy (95% CI) | Macro-F1 | Field Accuracy (95% CI) | Conflict F1 | Abstention Rate | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline A**: Strict Regex + Rules | `72.0%` (`108/150`) `[64.3%, 78.6%]` | `0.4245` | `85.8%` `[82.1%, 88.8%]` | `0.7161` | `94.4%` | `4.0%` (`6/150`) |
| **Baseline B**: Structured Normalizer + Rules | `78.0%` (`117/150`) `[70.7%, 83.9%]` | `0.4558` | `85.8%` `[82.1%, 88.8%]` | `0.7902` | `100.0%` | `0.0%` (`0/150`) |
| **System C**: Semantic Multimodal AI Only (No Rules) | `44.0%` (`66/150`) `[36.3%, 52.0%]` | `0.4969` | `90.2%` `[87.0%, 92.7%]` | `0.9505` | `33.3%` | **48.0%** (`72/150`) |
| **System D**: **Full EvidenceOS (Semantic AI + Rules)** | **94.0%** (`141/150`) `[89.0%, 96.8%]` | **0.9132** | **95.6%** `[93.2%, 97.1%]` | **0.9505** | **100.0%** | **0.0%** (`0/150`) |

### 8.3 Confusion Matrix (`System D` on Blind Held-Out Test Set, `N = 150`)

Rows represent **Ground-Truth Expected Decisions**; columns represent **System D Predicted Decisions**:

| Expected \ Predicted | `approved_full` | `approved_partial_settlement` | `rejected_duplicate_evidence` | `rejected_late_filing` | `manual_review_required` | **Row Total** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`approved_full`** | **6** | `0` | `0` | `0` | `0` | `6` |
| **`approved_partial_settlement`** | `0` | **9** | `0` | `0` | **9** | `18` |
| **`rejected_duplicate_evidence`** | `0` | `0` | **12** | `0` | `0` | `12` |
| **`rejected_late_filing`** | `0` | `0` | `0` | **6** | `0` | `6` |
| **`manual_review_required`** | `0` | `0` | `0` | `0` | **108** | `108` |
| **Column Total** | `6` | `9` | `12` | `6` | `117` | **150** |

**Key Observation**: Every single error made by `System D` (`9/150` cases) falls in the `(Expected: approved_partial_settlement, Predicted: manual_review_required)` cell. When `System D` fails to extract a noisy or colloquial field, the cross-modal conflict detector spots the discrepancy between the partial extraction and the remaining modalities, safely routing the dispute to human review rather than issuing a wrong payout.

---

## 9. Modality & Component Ablation Study

To isolate the causal contribution of each modality and architectural layer, we executed a 6-stage ablation across all `150` held-out cases:

| Ablation Configuration | Decision Acc (95% CI) | Macro-F1 | Conflict F1 | Duplicate Acc | Abstention Rate | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Ablation A**: Documents Only (PO + Challan) | `36.7%` `[29.4%, 44.6%]` | `0.2561` | `0.5833` | `88.0%` | `29.6%` | **62.0%** |
| **Ablation B**: Documents + Voice (No Images) | `76.7%` `[69.3%, 82.7%]` | `0.5173` | `0.8584` | `88.0%` | `90.7%` | `6.7%` |
| **Ablation C**: Documents + Images (No Voice) | `76.7%` `[69.3%, 82.7%]` | `0.5389` | `0.7857` | `88.0%` | `94.4%` | `4.0%` |
| **Ablation D**: Docs + Voice + Images (No Historical Hash) | `82.0%` `[75.1%, 87.3%]` | `0.8041` | `0.9505` | `88.0%` | `88.9%` | `12.0%` |
| **Ablation E**: All Modalities + History (No Rule Engine) | `44.0%` `[36.3%, 52.0%]` | `0.4969` | `0.9505` | `100.0%` | `33.3%` | **48.0%** |
| **Ablation F**: **Full EvidenceOS (All Modalities + Rules)** | **94.0%** `[89.0%, 96.8%]` | **0.9132** | **0.9505** | **100.0%** | **100.0%** | **0.0%** |

### Key Ablation Takeaways
1. **Documents Alone Are Blind to Dock Reality (`Ablation A`: `36.7%` accuracy, `62.0%` confident error rate)**: Without inspection photos or voice reports, unrecorded transit damage and reused photo fraud cannot be detected.
2. **Voice and Vision Provide Complementary Redundancy (`Ablation B` & `C`: `76.7%` each → `Ablation D`: `82.0%`)**: Combining both physical modalities catches single-source fabrications (`single_source_damage_claim`) and cross-modal quantity contradictions.
3. **Historical Perceptual Hashing Eliminates Reused Evidence Fraud (`Ablation D` `82.0%` → `Ablation F` `94.0%`)**: Enabling the SHA-256 + 64-bit `dHash` index resolves all `18` duplicate/perturbed image cases (`exact_duplicate_image`, `recompressed_image`, `cropped_or_brightness_shifted_image`).
4. **The Deterministic Rule Engine Is Essential for Safety (`Ablation E` `44.0%` → `Ablation F` `94.0%`)**: Removing the deterministic rule engine causes the Confident Error Rate to spike from **0.0% to 48.0%**, as semantic heuristics alone fail to enforce 48-hour SLA windows, high-value thresholds, and mandatory corroboration rules.

---

## 10. Failure Analysis (`System D` vs. Baselines)

Detailed per-case traces are cataloged in [`docs/failure-analysis.md`](failure-analysis.md) and [`evaluation/failures.json`](../evaluation/failures.json). Across the `150` blind held-out cases, `System D` makes **9 errors (`6.0%` error rate)** across exactly 4 failure categories:

| Failure Taxonomy Code | Count (`System D`) | Affected Category | Root Cause |
| :--- | :---: | :--- | :--- |
| **`ENTITY_LINKING_ERROR`** | `3` | `multi_sku_dispute` (`heldout_case_142..144`) | Blind inspection PNG shows damaged parcels without readable per-box SKU barcode text, defaulting visual damage to the primary line item (`SKU-IND-201`) while voice attributes damage to `SKU-IND-202`. |
| **`VOICE_INTERPRETATION_ERROR`** | `2` | `colloquial_wording` (`heldout_case_077..078`) | Unseen regional dock slang (*"munted"*, *"total toast"*) not mapped in the semantic lexicon, yielding `damaged_quantity=0` on audio and triggering a cross-modal conflict against the photo. |
| **`OCR_OR_TEXT_NOISE_ERROR`** | `2` | `typos_and_ocr_noise` (`heldout_case_083..084`) | Severe alphanumeric OCR corruption (`lO` for `10`, `0RD3R3D`) causes quantity parser fallback (`0`), triggering a conservative `MISSING_CRITICAL_EVIDENCE` review. |
| **`DOCUMENT_EXTRACTION_ERROR`** | `2` | `multilingual_or_mixed_terms` (`heldout_case_089..090`) | Untranslated German procurement headers (`Bestellmenge`, `Geliefert`, `Defekt`) are not matched by English/Spanish/French normalizers. |

---

## 11. Security & Adversarial Robustness Evaluation

We evaluated EvidenceOS against a dedicated **15-case Adversarial Prompt Injection Suite** across 5 attack vectors (`pdf_override_instruction`, `challan_hidden_system_prompt`, `voice_transcript_jailbreak`, `json_field_injection`, `fake_authority_claim`):
- **Sanitization Trigger Rate**: **100.0% (`15/15`)** — All 15 adversarial payloads were intercepted and neutralized (`[REDACTED_ADVERSARIAL_INSTRUCTION]`) by `sanitize_untrusted_text`.
- **Attack Success Rate**: **0.0% (`0/15`)** — Zero adversarial payloads succeeded in forcing `approved_full` on disputed/zero-damage shipments.
- **Safe Rejection / Escalation Rate**: **100.0% (`15/15`)**.

Full threat modeling and residual risk analysis are documented in [`docs/security-evaluation.md`](security-evaluation.md).

---

## 12. Perceptual Hashing vs. Cryptographic Hashing Evaluation

We evaluated duplicate image detection across **40 controlled image pairs** (`32` true duplicates across 4 perturbation types + `8` distinct control pairs):

| Perturbation Category | Pairs | `SHA-256` Exact Match | `64-bit dHash` (`Hamming <= 6`) | Mean Hamming Distance |
| :--- | :---: | :---: | :---: | :---: |
| **1. Exact Byte Duplicate** | `8` | `100.0%` (`8/8`) | `100.0%` (`8/8`) | `0.00` |
| **2. Recompressed / Palette Perturbed** | `8` | `0.0%` (`0/8`) | `100.0%` (`8/8`) | `0.00` |
| **3. Brightness Shifted (`+14..+21` RGB)** | `8` | `0.0%` (`0/8`) | `100.0%` (`8/8`) | `0.00` |
| **4. Cropped / Border Shifted (`2..3 px`)** | `8` | `0.0%` (`0/8`) | `100.0%` (`8/8`) | `0.00` |
| **5. Distinct Control Scenes (Negative)** | `8` | `0.0%` FP (`0/8`) | `0.0%` FP (`0/8`) | `12.00` |
| **Overall Precision / Recall / F1** | **40** | **P: `100.0%` / R: `25.0%` / F1: `0.400`** | **P: `100.0%` / R: `100.0%` / F1: `1.000`** | — |

---

## 13. Latency, Throughput, & Cost Analysis

Measured across all `150` cases (`564` files) in the Held-Out Test Set:

| Pipeline Stage | Mean Latency (`ms`) | Median P50 (`ms`) | Tail P95 (`ms`) |
| :--- | :---: | :---: | :---: |
| **1. Ingestion & Hashing (`SHA-256` + `dHash`)** | `34.81 ms` | `26.57 ms` | `72.42 ms` |
| **2. Document Extraction (PDF)** | `22.84 ms` | `17.24 ms` | `48.66 ms` |
| **3. Image Analysis (Blind Pixel CV)** | `12.03 ms` | `8.55 ms` | `27.64 ms` |
| **4. Voice Analysis (WAV + Transcript)** | `9.54 ms` | `6.70 ms` | `24.51 ms` |
| **5. Normalization** | `11.12 ms` | `7.17 ms` | `19.65 ms` |
| **6. Entity Resolution** | `9.44 ms` | `7.02 ms` | `20.57 ms` |
| **7. Conflict Detection** | `6.07 ms` | `4.85 ms` | `14.53 ms` |
| **8. Historical Duplicate Matching** | `20.92 ms` | `12.63 ms` | `50.61 ms` |
| **9. Rule & Decision Engine** | `8.44 ms` | `6.14 ms` | `16.62 ms` |
| **Total End-to-End Case Pipeline** | **`148.83 ms`** | **`112.92 ms`** | **`286.67 ms`** |

**Token & Cloud API Cost Projection**:
- **Local Hybrid Execution**: `$0.00` external API cost (`~6.7 cases/sec` sequential throughput).
- **Cloud Gemini 2.5 Flash Multimodal Equivalent**: Estimated `1,532` tokens/case (`229,800` tokens across `150` cases), corresponding to **`$0.00055` per case** (`$0.0825` per `150`-case evaluation run).

---

## 14. Limitations & Threats to Validity

1. **Synthetic & Procedurally Inspired Artifacts**: Although the 150-case Held-Out Test Set eliminates filename and metadata leakage and includes `34` real-world-inspired adversarial cases, the PDFs, PNGs, and WAVs are generated within a controlled testbed rather than sampled from live enterprise ERP production logs.
2. **2D Grid Vision Assumptions**: The blind pixel CV analyzer inspects a canonical 2×5 pallet grid and global luminance statistics. Wild camera angles, perspective distortion, or arbitrary warehouse backgrounds require a fine-tuned object detection head (e.g., OWL-ViT / YOLOv8) or live cloud VLM call.
3. **Multilingual & OCR Coverage**: As shown by the `9` held-out errors, unseen languages (e.g., German procurement terms) and character-level OCR substitutions (`lO` for `10`) degrade deterministic and lexical extractors alike unless paired with an OCR correction pass.
4. **Perceptual Hash Rotation Vulnerability**: While 64-bit `dHash` (`Hamming <= 6`) achieves `100%` recall on recompression, brightness shifts, and minor crops, it is not invariant to `90°/180°` rotations or heavy perspective warps.

---

## 15. Future Work

1. **Live Vision-Language & ASR Benchmarking**: Run side-by-side evaluations comparing the local blind pixel/acoustic extractors against live `gemini-2.5-flash` and `gemini-2.5-pro` API calls on scanned physical paper documents.
2. **Rotation-Invariant Embeddings**: Augment 64-bit `dHash` with lightweight CLIP/SigLIP visual embeddings for rotation- and perspective-invariant duplicate detection.
3. **Multi-SKU Barcode & Bounding-Box Grounding**: Integrate barcode/QR decoding (`pyzbar`) so visual damage in multi-SKU shipments is automatically linked to the exact SKU entity.
