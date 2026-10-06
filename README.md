# EvidenceOS (`VeriDock`)

> **An Epistemically Grounded Multimodal AI & Deterministic Rule Engine for B2B Delivery Dispute Verification.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19 + TypeScript](https://img.shields.io/badge/Frontend-React%2019%20%2B%20TS-61dafb.svg)](https://react.dev/)
[![Held-Out Accuracy](https://img.shields.io/badge/Held--Out%20150%20Accuracy-94.0%25%20%5B89.0%25%2C%2096.8%25%5D-10b981.svg)](docs/research-report.md)
[![Confident Error Rate](https://img.shields.io/badge/Confident%20Error%20Rate-0.0%25-059669.svg)](docs/failure-analysis.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-slate.svg)](LICENSE)

---

## 1. What is EvidenceOS?

B2B supply chain and procurement disputes require reconciling conflicting, noisy, multimodal evidence—**Purchase Orders (PDF)**, **Delivery Challans (PDF)**, **Dock Inspection Photographs (PNG)**, **Warehouse Voice Reports (WAV)**, and **Historical Claim Ledgers**—against strict contractual Service-Level Agreements (SLAs).

Purely generative LLM pipelines are unsafe for autonomous financial settlement: they hallucinate unstated quantities, fail to enforce exact SLA deadlines, and are vulnerable to adversarial prompt injection. Conversely, purely deterministic regex pipelines break down on colloquial warehouse speech, OCR typos, and degraded visual evidence.

**EvidenceOS (`VeriDock`)** solves this through an **epistemically typed hybrid architecture**:
1. **Multimodal Semantic Extraction with Explicit Epistemic Typing**: Extracts claims from documents, blind pixel-level computer vision (`analyze_pallet_pixels_blind`), and audio transcripts while tagging every claim as `FACT`, `INFERENCE`, `RULE`, or `UNCERTAINTY` with exact source provenance (`evidence_id`, `sha256`, character/pixel span).
2. **Cross-Modal Conflict Graph & Entity Resolution**: Links claims across modalities to canonical SKU entities and isolates quantity, damage, and missing-evidence contradictions.
3. **Cryptographic (`SHA-256`) + Perceptual (`64-bit dHash`) Fraud Detection**: Detects both byte-identical and visually perturbed (recompressed, brightness-shifted, cropped) duplicate photos across historical claims (`Hamming distance <= 6`).
4. **Deterministic Rule Engine (`R1–R8`) & Hash-Chained Audit Ledger**: Enforces 48-hour SLA windows, high-value manual review thresholds (`>= $5,000`), and mandatory abstention (`manual_review_required`) whenever evidence is degraded (`UNCERTAINTY`) or contradictory.

---

## 2. Reproducible Research Evaluation Summary

> *"On a held-out evaluation set of 150 cases, the full EvidenceOS pipeline achieved **94.0%** decision accuracy (`141/150`, 95% Wilson CI `[89.0%, 96.8%]`). The deterministic baselines achieved **72.0%** (strict regex) and **78.0%** (structured normalizer), while standalone semantic extraction without deterministic rules achieved **44.0%** (`48.0%` confident error rate). The largest performance gap occurred in unstructured prose documents, colloquial warehouse voice transcripts, and degraded visual evidence."*

We evaluate EvidenceOS across three strictly separated datasets (`seed=42`) to prevent benchmark overfitting. **We never market regression or development metrics as open-world accuracy.**

```text
Held-out test set: 150 cases (564 files across 25 adversarial categories, zero filename/metadata leakage)

Semantic multimodal + deterministic rules (System D — EvidenceOS):
Decision accuracy: 94.0% (141/150, 95% Wilson CI: [89.0%, 96.8%])
Macro F1: 91.3% (0.9132)
Conflict F1: 95.1% (Precision: 90.6%, Recall: 100.0%)
Confident error rate: 0.0% (0/150 wrong automated settlements; all 9 misses safely abstain to manual review)

Deterministic baselines:
- Baseline A (Strict Regex + Rules):
  Decision accuracy: 72.0% (108/150, 95% CI: [64.3%, 78.6%])
  Macro F1: 42.5% (0.4245)
  Conflict F1: 71.6%
  Confident error rate: 4.0% (6/150)
- Baseline B (Structured Normalizer + Rules):
  Decision accuracy: 78.0% (117/150, 95% CI: [70.7%, 83.9%])
  Macro F1: 45.6% (0.4558)
  Conflict F1: 79.0%
  Confident error rate: 0.0%
- System C (Semantic Multimodal AI Only — No Rule Engine):
  Decision accuracy: 44.0% (66/150, 95% CI: [36.3%, 52.0%])
  Macro F1: 49.7% (0.4969)
  Confident error rate: 48.0% (72/150 unsafe automated settlements on SLA breaches & high-value claims)

Most difficult category:
multi_sku_dispute (50.0% accuracy, 3/6) — followed by colloquial_wording (66.7%, 4/6), typos_and_ocr_noise (66.7%, 4/6), and multilingual_or_mixed_terms (66.7%, 4/6).

Most common failure:
ENTITY_LINKING_ERROR (3/9 failures) — In blind pixel mode with no per-parcel barcode text, visual damage on secondary SKUs (SKU-IND-202) defaults to the primary shipment item (SKU-IND-201), triggering a cross-modal conflict and manual review.

AI advantage:
+22.0% decision accuracy over Strict Regex (72.0% -> 94.0%) and +16.0% over Structured Normalizer (78.0% -> 94.0%) by resolving unstructured prose documents, spoken number words, hedged audio uncertainty, and pixel-level image degradation (low-light, blur, occlusion).

AI limitation:
Standalone semantic AI without the deterministic rule engine (System C) suffers a 48.0% confident error rate (auto-approving late SLA filings, high-value disputes >= $5,000, and uncorroborated claims). Even with rules (System D), unseen regional slang ("munted", "total toast"), digit-level OCR corruption ("lO" for "10"), and untranslated German headers ("Bestellmenge") cause 6 extraction misses (all safely abstaining to manual_review_required).

Reproducibility:
PASS (Deterministic seed=42, 12/12 pytest, 10/10 vitest, 0 ruff errors, single-command `python -m scripts.run_evaluation`)
```

### 2.1 Performance Across Dataset Splits (`System D: Full EvidenceOS`)

| Dataset Split | Cases / Files | Decision Accuracy (95% Wilson CI) | Macro-F1 | Field Accuracy (95% CI) | Conflict F1 | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Canonical Regression (`canonical_5`)** | `5` / `20` | `100.0%` (`5/5`) `[56.6%, 100.0%]` | `1.0000` | `100.0%` `[83.9%, 100.0%]` | `1.0000` | `0.0%` (`0/5`) |
| **2. Development Benchmark (`development_60`)** | `60` / `234` | `96.7%` (`58/60`) `[88.6%, 99.1%]` | `0.9583` | `100.0%` `[98.4%, 100.0%]` | `0.9643` | `1.7%` (`1/60`) |
| **3. Blind Held-Out Test Set (`heldout_150`)** | **`150` / `564`** | **`94.0%` (`141/150`) `[89.0%, 96.8%]`** | **`0.9132`** | **`95.6%` `[93.2%, 97.1%]`** | **`0.9505`** | **`0.0%` (`0/150`)** |

*Note on Held-Out Data Origins (`N=150`)*: All filename hints and PNG metadata chunks are stripped (`artifact_01.pdf`..`artifact_04.wav`). On the `116` `SYNTHETIC` held-out cases, `System D` achieves **100.0%** (`116/116`, CI `[96.8%, 100.0%]`). On the `34` `REAL_WORLD_INSPIRED` adversarial cases (unseen slang, severe OCR noise, multilingual headers, blind multi-SKU attribution), `System D` achieves **73.5%** (`25/34`, CI `[56.9%, 85.4%]`), with all `9` errors safely abstaining to `manual_review_required` (`0.0%` Confident Error Rate).

### 2.2 Four-System Comparison on Blind Held-Out Test Set (`N = 150`)

| Evaluated System | Decision Accuracy (95% CI) | Macro-F1 | Field Accuracy | Conflict F1 | Abstention Rate | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline A**: Strict Regex + Rules | `72.0%` (`108/150`) `[64.3%, 78.6%]` | `0.4245` | `85.8%` | `0.7161` | `94.4%` | `4.0%` (`6/150`) |
| **Baseline B**: Structured Normalizer + Rules | `78.0%` (`117/150`) `[70.7%, 83.9%]` | `0.4558` | `85.8%` | `0.7902` | `100.0%` | `0.0%` (`0/150`) |
| **System C**: Semantic Multimodal AI Only (No Rules) | `44.0%` (`66/150`) `[36.3%, 52.0%]` | `0.4969` | `90.2%` | `0.9505` | `33.3%` | **48.0%** (`72/150`) |
| **System D**: **Full EvidenceOS (Semantic AI + Rules)** | **94.0%** (`141/150`) `[89.0%, 96.8%]` | **0.9132** | **95.6%** | **0.9505** | **100.0%** | **0.0%** (`0/150`) |

### 2.3 Six-Stage Modality & Component Ablation Study (`N = 150`)

| Ablation Stage | Decision Accuracy (95% CI) | Macro-F1 | Duplicate Acc | Confident Error Rate | Key Finding |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Ablation A**: Documents Only | `36.7%` `[29.4%, 44.6%]` | `0.2561` | `88.0%` | **62.0%** | Blind to physical transit damage and reused photo fraud |
| **Ablation B**: Documents + Voice | `76.7%` `[69.3%, 82.7%]` | `0.5173` | `88.0%` | `6.7%` | Misses visual fraud and uncorroborated audio claims |
| **Ablation C**: Documents + Images | `76.7%` `[69.3%, 82.7%]` | `0.5389` | `88.0%` | `4.0%` | Misses spoken dock inspection context and audio conflicts |
| **Ablation D**: Docs + Voice + Images (No History) | `82.0%` `[75.1%, 87.3%]` | `0.8041` | `88.0%` | `12.0%` | Fails on all `18` reused/perturbed historical image fraud cases |
| **Ablation E**: All Modalities + History (No Rules) | `44.0%` `[36.3%, 52.0%]` | `0.4969` | `100.0%` | **48.0%** | Dangerous auto-settlements on SLA breaches & high-value claims |
| **Ablation F**: **Full EvidenceOS** | **94.0%** `[89.0%, 96.8%]` | **0.9132** | **100.0%** | **0.0%** | Optimal accuracy and zero unsafe automated payouts |

### 2.4 Specialized Security, Hashing, & Latency Benchmarks
- **Perceptual Hashing (`64-bit dHash`) vs. `SHA-256` (`40` Image Pairs)**: `SHA-256` achieves `100.0%` precision but only **`25.0%` recall** (`8/32` — misses all recompressed, cropped, and brightness-shifted duplicates). Combined `SHA-256 + 64-bit dHash (Hamming <= 6)` achieves **`100.0%` precision and `100.0%` recall (`F1 = 1.000`)**.
- **Prompt Injection Robustness (`15` Adversarial Cases across 5 Vectors)**: **100.0% (`15/15`)** sanitization trigger rate, **0.0% (`0/15`)** attack success rate.
- **Stage Latency (`N = 150`)**: End-to-end case verification completes in **`148.8 ms` mean (`112.9 ms` P50, `286.7 ms` P95)** locally (`\$0.00` offline cost; estimated `\$0.00055/case` when routed through cloud Gemini 2.5 Flash).

### 2.5 Confidence Calibration & Selective Prediction (`N = 150` Held-Out Set)

In financial dispute resolution, the critical operational question is **Selective Prediction (Risk-Coverage)**: when EvidenceOS says it is confident and auto-settles (`approved` / `partially_approved`), how often is it right? And when evidence is degraded or contradictory, does it reliably abstain (`manual_review_required`)?

| Selective Prediction Metric ($N=150$ Held-Out Set) | `System D: Full EvidenceOS` | `System C: Semantic AI Only` (No Rules) |
| :--- | :---: | :---: |
| **Auto-Settled Cases (`approved` / `partially_approved`)** | **`33 / 150` (`22.0%` total; `78.6%` of valid claims)** | `108 / 150` (`72.0%` total) |
| **Auto-Settlement Precision (Accuracy when Confident & Acting)** | **`100.0%` (`33 / 33`, 95% CI `[89.6%, 100.0%]`)** | `33.3%` (`36 / 108`, 95% CI `[25.1%, 42.7%]`) |
| **Abstained to Human Review (`manual_review_required`)** | **`117 / 150` (`78.0%`)** (`108` true + `9` conservative) | `42 / 150` (`28.0%`) |
| **True Escalation Capture Rate (Abstention Recall)** | **`100.0%` (`108 / 108`)** | `33.3%` (`36 / 108`) |
| **Confident Error Rate (`conf >= 0.80` & Wrong Action)** | **`0.0%` (`0 / 150`)** | `48.0%` (`72 / 150`) |
| **Auto-Settlement Expected Calibration Error (ECE)** | **`0.0207` (`2.1%`)** | `0.5694` (`56.9%`) |

### 2.6 Attacking the Weakest Point: Multi-SKU Entity Linking Stress Benchmark (`N = 42`)

In the frozen `heldout_150` benchmark (`v1.0.0-benchmark-frozen`), `multi_sku_dispute` was the hardest category (`50.0%`, `3/6`) because blind pallet photos (`ITEM:UNKNOWN`) defaulted to the primary PO line item (`SKU-IND-201`). Without touching the frozen `v1_frozen` benchmark, we built a dedicated **42-case Multi-SKU Stress Benchmark** across 7 failure modes (`explicit_multi_sku`, `similar_sku_names_and_codes`, `reordered_line_items`, `missing_visual_barcodes_blind_cv`, `partial_pallet_visibility`, `conflicting_sku_references`, `ocr_noisy_sku_identifiers`) and evaluated our context-aware resolver (`v2_context_aware` in [`core/entities/resolver.py`](core/entities/resolver.py)):

| Resolver Mode ($N = 42$ Multi-SKU Stress Set) | Decision Accuracy (95% CI) | Strict Claim-to-SKU Attribution Accuracy | Confident Error Rate |
| :--- | :---: | :---: | :---: |
| **`v1_frozen` (Primary-SKU Fallback — Frozen Baseline)** | `57.1%` (`24/42`) `[42.2%, 70.9%]` | `42.9%` (`18/42`) `[29.1%, 57.8%]` | `0.0%` (`0/42`) |
| **`v2_context_aware` (OCR-Canonicalized + Cross-Modal Corroboration)** | **`100.0%` (`42/42`) `[91.6%, 100.0%]`** | **`100.0%` (`42/42`) `[91.6%, 100.0%]`** | **`0.0%` (`0/42`)** |

---

## 3. Research & Engineering Documentation

- **[Independent Code, Metric & Research Audit (`docs/independent-audit.md`)](docs/independent-audit.md)**: Cryptographic freeze manifest (`v1.0.0-benchmark-frozen`), code audit for synthetic/metric shortcuts (`AUDIT_NOTE_01`, `AUDIT_FINDING_02..04`), 42-case Multi-SKU study, and 150-case confidence calibration analysis.
- **[3-Minute Technical Demo Walkthrough (`docs/demo-walkthrough.md`)](docs/demo-walkthrough.md)**: Step-by-step live walkthrough of the UI, inline PDF evidence highlighting, side-by-side reused image inspection (`dHash`), and evaluation dashboard.
- **[Research Report (`docs/research-report.md`)](docs/research-report.md)**: 18-section empirical study covering the research questions, blind computer vision design, statistical confidence intervals, confusion matrices, calibration, and limitations.
- **[Failure Analysis (`docs/failure-analysis.md`)](docs/failure-analysis.md)**: Complete case-by-case dissection of all `9` held-out errors in `System D` (`ENTITY_LINKING_ERROR`, `VOICE_INTERPRETATION_ERROR`, `OCR_OR_TEXT_NOISE_ERROR`, `DOCUMENT_EXTRACTION_ERROR`) and comparison against the `84` errors in `System C`.
- **[Security Evaluation (`docs/security-evaluation.md`)](docs/security-evaluation.md)**: 15-case prompt injection evaluation and Threat / Impact / Likelihood / Mitigation / Residual Risk matrix.
- **[Evaluation Methodology (`docs/evaluation.md`)](docs/evaluation.md)**: Dataset split specifications and category-by-category breakdown across all 25 held-out categories.
- **[Reproducibility Guide (`docs/reproducibility.md`)](docs/reproducibility.md)**: Exact one-command instructions to regenerate all datasets, metrics, and failure logs (`seed=42`).
- **[System Architecture (`docs/architecture.md`)](docs/architecture.md)** & **[API Reference (`docs/api.md`)](docs/api.md)**.

---

## 4. Quick Start

### Option A: Local Development (Python + Node.js)

```bash
# 1. Install backend dependencies
pip install -e ".[dev]"

# 2. Start the FastAPI server (seeds the 5 canonical demo cases automatically)
uvicorn apps.api.main:app --reload --port 8000

# 3. In a second terminal, start the React 19 + Vite frontend
cd apps/web
npm install
npm run dev
```

Open **`http://localhost:5173`** to explore the **Guided Investigation Tour**, **Interactive Provenance Drawer (with inline PDF highlighting)**, **Side-by-Side Reused Image Inspector**, **Evidence DAG**, **Rule Trace**, **Tamper-Evident Audit Ledger**, and **Research Evaluation Dashboard**.

### Option B: Reproduce the Complete Research Evaluation & Post-Freeze Audit (`seed=42`)

```bash
# 1. Regenerate canonical_5, development_60, and blind heldout_150 splits & baselines
python -m scripts.run_evaluation

# 2. Verify cryptographic benchmark freeze & run N=42 Multi-SKU + N=150 Calibration studies
python -m evaluation.multi_sku_and_calibration
```

---

## 5. Known Limitations

1. **Controlled Procedural & Real-World-Inspired Testbed (`AUDIT_NOTE_01`)**: While `heldout_150` eliminates filename/metadata leakage (`assert b"tEXt" not in png_bytes`) and includes `34` real-world-inspired cases (`73.5%` accuracy), offline vision (`analyze_pallet_pixels_blind`) inspects the `2x5` parcel grid of our procedural renderer. Unconstrained smartphone dock photos require enabling `GEMINI_API_KEY` (`GeminiAIProvider` multimodal vision) or a fine-tuned parcel detector.
2. **Multi-SKU Optical Grounding (`3` Held-Out Errors in `v1_frozen`)**: Without optical barcode/QR text on individual pallet parcels, `v1_frozen` attributes blind visual damage to the primary SKU in multi-SKU shipments (`50.0%` on `multi_sku_dispute`, resolved to `100.0%` in `v2_context_aware` via cross-modal corroboration).
3. **Unseen Slang, Heavy OCR Corruption, & Untranslated Headers (`6` Held-Out Errors)**: Unseen regional slang (*"munted"*, *"total toast"*), digit-level OCR corruption (`lO` for `10`), and untranslated German headers (`Bestellmenge`) cause partial extraction misses that safely abstain to `manual_review_required`.
4. **90°/180° Image Rotation**: `64-bit dHash` handles recompression, brightness shifts, and minor crops (`100%` recall), but requires rotational alignment or learned visual embeddings for `90°/180°` rotated duplicates.
