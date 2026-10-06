# EvidenceOS (`VeriDock`) — Independent Code, Metric & Research Audit

**Audit Status**: `COMPLETED`  
**Frozen Benchmark Reference**: `v1.0.0-benchmark-frozen` (Git commit `07c8065`, `seed=42`, $N=150$ Held-Out Cases)  
**Freeze Manifest**: [`evaluation/datasets/benchmark_freeze_manifest.json`](../evaluation/datasets/benchmark_freeze_manifest.json)  
**Post-Freeze Experimental Artifact**: [`evaluation/post_freeze_audit_experiments.json`](../evaluation/post_freeze_audit_experiments.json)

---

## Executive Summary

Before presenting a benchmark to technical reviewers, security researchers, or engineering leadership, we conducted an adversarial internal code and research audit of the entire EvidenceOS codebase (`core/`, `evaluation/`, `apps/`) to answer a single question:

> *"Where could the evaluation harness, synthetic dataset generator, offline vision/audio parsers, or metric definitions make EvidenceOS look stronger than it would be in open-world production?"*

This document records the cryptographic freeze of the `heldout_150` benchmark (`94.0%` decision accuracy, `0.0%` confident error rate), followed by four explicit code-audit findings, a dedicated **42-case Multi-SKU Entity Linking Stress Benchmark** targeting the system's hardest failure mode, and a **150-case Confidence Calibration & Selective Prediction (Risk-Coverage) Analysis**.

---

## 1. Cryptographic Benchmark Freeze (`v1.0.0-benchmark-frozen`)

To prevent post-hoc benchmark tuning ("test-set snooping"), the 150-case held-out benchmark was frozen at Git tag **`v1.0.0-benchmark-frozen`** (`commit 07c8065`). All post-freeze experiments (such as the `v2_context_aware` multi-SKU entity resolver) are gated behind an explicit `resolver_mode` flag (`default="v1_frozen"`) in [`core/entities/resolver.py`](../core/entities/resolver.py) so the baseline held-out evaluation remains 100% immutable and reproducible.

| Artifact | SHA-256 Digest | Locked Scope |
| :--- | :--- | :--- |
| [`evaluation/results.json`](../evaluation/results.json) | `3d235d9981af6558f9a53b1e32b87fd2e740752dee7fcbddf31fa879cf84eca8` | 4-system head-to-head metrics across `canonical_5`, `adversarial_60`, `heldout_150` |
| [`evaluation/failures.json`](../evaluation/failures.json) | `8888354de8ce471630a1e7e09e30e5d4016fa67d77bbce8aff26b742bc02b75f` | Full error taxonomy for all 9 `heldout_150` failures |
| [`evaluation/datasets/heldout_test_150_manifest.json`](../evaluation/datasets/heldout_test_150_manifest.json) | `2ec5157df9db722053144fd070795c05aaf201216c783b10406b6c1cf952113b` | Ground-truth labels, categories, and artifact manifests for `N=150` |

---

## 2. Code & Evaluation Audit Findings

We audited [`evaluation/runner.py`](../evaluation/runner.py), [`core/ai/provider.py`](../core/ai/provider.py), [`core/normalization/service.py`](../core/normalization/service.py), [`core/entities/resolver.py`](../core/entities/resolver.py), [`core/conflicts/detector.py`](../core/conflicts/detector.py), and [`core/decisions/engine.py`](../core/decisions/engine.py) for benchmark leakage, synthetic shortcuts, and metric calculation edge cases.

### Audit Check 0: Held-Out Filename, Role & Metadata Leakage (`PASS — ZERO LEAKAGE`)
- **What we checked**: Does the extraction or decision pipeline inspect case IDs, ground-truth labels, filenames, evidence roles, or hidden image metadata chunks during the 150-case held-out evaluation?
- **Verification**:
  - Every held-out case in [`evaluation/runner.py`](../evaluation/runner.py) (`build_heldout_150_specs`) writes files exclusively as opaque filenames (`artifact_01.pdf`, `artifact_02.pdf`, `artifact_03.png`, `artifact_04.wav`) and ingests every file with `role="unknown"`.
  - Every held-out PNG is generated with `blind_mode=True` (`generate_custom_pallet_png(..., blind_mode=True)`), and line 577 of [`evaluation/runner.py`](../evaluation/runner.py) executes `assert b"tEXt" not in png_bytes` before writing the file to disk.
  - Ground-truth fields (`expected_decision`, `expected_payout`, `expected_damaged_qty`, `expected_conflicts`) exist only inside `CaseSpec` in `evaluation/runner.py` and are never passed into `IngestionService` or `DecisionEngine`.

### `AUDIT_NOTE_01`: Synthetic Pixel Grid Geometry Coupling in Offline Vision (`core/ai/provider.py`)
- **Location**: [`core/ai/provider.py`](../core/ai/provider.py) (`analyze_pallet_pixels_blind`, lines 49–113).
- **Finding**: While `heldout_150` strips all PNG metadata chunks (`blind_mode=True`), the offline deterministic computer-vision analyzer (`analyze_pallet_pixels_blind`) inspects pixel luminance (`avg_lum`), Laplacian edge variance (`edge_score`), and red-vs-green color dominance (`cr > cg + 45`) across the `2x5` parcel bounding-box grid (`320x240` geometry) produced by the procedural pallet renderer (`generate_custom_pallet_png`).
- **Why this matters**: On the procedural benchmark, pixel inspection legitimately separates clean brown boxes, crushed red-marked boxes, occluded black regions, underexposed dark images (`avg_lum < 34`), blur (`edge_score < 6.5`), and off-topic gradient images (`non_dock_ratio > 0.45`). However, **this pixel grid heuristic will not generalize to unconstrained real-world smartphone photos** of warehouse pallets.
- **Mitigation & Disclosure**: Real-world photos require running EvidenceOS with `GEMINI_API_KEY` enabled (`GeminiAIProvider` multimodal vision in [`core/ai/provider.py`](../core/ai/provider.py)) or a fine-tuned YOLO/DETR parcel-damage detector. This distinction is explicitly disclosed in the README and Research Report.

### `AUDIT_FINDING_02`: Entity Count vs. Strict Claim-to-Entity Attribution (`evaluation/runner.py`)
- **Location**: [`evaluation/runner.py`](../evaluation/runner.py) (lines 380–384) and [`core/entities/resolver.py`](../core/entities/resolver.py) (lines 90–103).
- **Finding**: In `evaluation/runner.py`, `entity_matching_accuracy` (`100.0%` on `heldout_150`) evaluated whether the **count** of resolved SKU entities matched the ground-truth SKU count (`run_out["entities_count"] == expected_entities`).
- **Why this was overly optimistic**: In `multi_sku_dispute` cases (`heldout_case_142..144`), the Purchase Order and Delivery Challan both listed two SKUs (`SKU-IND-201` and `SKU-IND-202`), so `EntityResolutionService` created `2` entities (`entities_count == 2`, scoring a match). However, the blind pallet photo (`artifact_03.png`) produced a visual damage claim with `entity_ref="ITEM:UNKNOWN"` (because raw pixel detection has no barcode text), and `v1_frozen` linked `ITEM:UNKNOWN` to `primary_item_entity` (`SKU-IND-201`, the first PO line item) even when the voice transcript reported damage on `SKU-IND-202`.
- **Corrected Strict Metric**: We added **`strict_entity_claim_linking_accuracy`** to [`evaluation/multi_sku_and_calibration.py`](../evaluation/multi_sku_and_calibration.py), which requires both exact SKU entity count **and** zero misattributed SKU claims. Under strict claim-to-entity attribution:
  - Overall `heldout_150` strict entity attribution accuracy is **`98.0%` (`147 / 150`)** rather than `100.0%`.
  - On `multi_sku_dispute`, `v1_frozen` strict entity attribution accuracy is **`50.0%` (`3 / 6`)**, matching its `50.0%` decision accuracy.

### `AUDIT_FINDING_03`: Count-Based Conflict Precision & Recall (`evaluation/runner.py`)
- **Location**: [`evaluation/runner.py`](../evaluation/runner.py) (lines 386–391).
- **Finding**: Conflict Precision (`90.6%`), Recall (`100.0%`), and F1 (`95.1%`) are computed per case via `tp_c = min(exp_c, act_c)`, `fp_c = max(0, act_c - exp_c)`, and `fn_c = max(0, exp_c - act_c)`.
- **Nuance**: When an upstream extraction or SKU-linking miss occurs (as in the 9 `heldout_150` errors where a valid `partially_approved` claim failed to link or parse), `ConflictDetector` fires an `UNCORROBORATED_CLAIM` or `QUANTITY_MISMATCH` conflict because one modality appears uncorroborated (`act_c > 0` when `exp_c = 0`). Thus, the `10` false-positive conflicts on `heldout_150` are direct downstream safeguards triggered by the `9` upstream extraction/linking misses—which is why the rule engine safely routed all `9` cases to `manual_review_required` rather than issuing an unverified payout.

### `AUDIT_FINDING_04`: Binary Auto-Approval FP/FN vs. Conservative Over-Abstention (`evaluation/runner.py`)
- **Location**: [`evaluation/runner.py`](../evaluation/runner.py) (lines 393–400).
- **Finding**: In `evaluation/runner.py`, `false_positive_rate` (`0.0%`) measures the rate at which a case that *should* be escalated (`manual_review_required`) is erroneously auto-settled (`approved` or `partially_approved`). Conversely, `false_negative_rate` measures when an auto-settleable case is sent to `manual_review_required`.
- **Breakdown by Class**:
  - Clean deliveries (`approved`, $N=15$): **`15 / 15` (`100.0%`)** auto-approved (`0%` false abstention).
  - Valid partial-damage claims (`partially_approved`, $N=27$): **`18 / 27` (`66.7%`)** auto-settled with exact payout; **`9 / 27` (`33.3%`)** conservatively abstained to `manual_review_required` (`6.0%` of the 150 total cases).
  - True manual-review cases (`manual_review_required`, $N=108$): **`108 / 108` (`100.0%`)** escalated (`0.0%` false-positive auto-approval).

---

## 3. Gemini Live Multimodal (`GeminiAIProvider`) vs. Offline Deterministic (`DeterministicAIProvider`) Parity

We audited [`core/ai/provider.py`](../core/ai/provider.py) and [`core/normalization/service.py`](../core/normalization/service.py) to compare how the two providers operate and ensure identical downstream guarantees:

| Architectural Layer | `GeminiAIProvider` (`GEMINI_API_KEY` set) | `DeterministicAIProvider` (Default Offline CI/CD) | Parity & Safety Contract |
| :--- | :--- | :--- | :--- |
| **Image Inspection** | Calls `gemini-2.5-flash` with raw image bytes and structured JSON schema (`damaged_boxes_visible`, `tamper_seal_intact`, `condition_summary`, `confidence`). | Runs `analyze_pallet_pixels_blind` (luminance, Laplacian edge variance, 2x5 parcel grid color/occlusion inspection) + PNG chunk inspection on legacy fixtures. | Both emit the exact same `Claim` schema (`damaged_quantity`, `visual_integrity`, `confidence`) into `EvidenceGraphBuilder`. |
| **Audio Inspection** | Calls `gemini-2.5-flash` with `.wav` bytes to transcribe and extract `damaged_quantity`, `sku`, and speaker certainty. | Decodes spoken ASCII payload frames from `.wav` PCM bytes, strips prompt injections, parses colloquial & compound numbers, and penalizes hedged speech (`confidence=0.58`). | Both pass through `_sanitize_untrusted_text` and produce identical normalized `Claim` records. |
| **Prompt Injection Defense** | System instructions isolate untrusted evidence text + downstream `RuleEngine` ignores AI prose recommendations. | Regex sanitizer strips adversarial instructions (`IGNORE ALL PREVIOUS INSTRUCTIONS`, fake `tEXt`/`iTXt` chunks) + downstream `RuleEngine` is 100% deterministic Python. | **Identical**: Neither provider can directly set `DecisionOutcome` or `approved_payout`. |
| **Entity Resolution, Conflict Detection & Rule Engine** | `EntityResolutionService` $\rightarrow$ `ConflictDetector` $\rightarrow$ `RuleEngine` | `EntityResolutionService` $\rightarrow$ `ConflictDetector` $\rightarrow$ `RuleEngine` | **100% Shared Code Path**: Zero branching between live Gemini and offline mode after claim extraction. |

---

## 4. Post-Freeze Study 1: Attacking the Weakest Point — Multi-SKU Entity Linking Stress Benchmark ($N = 42$)

In the frozen 150-case held-out evaluation, **`multi_sku_dispute` was the hardest category (`50.0%` accuracy, `3/6`)**, accounting for 33% of all system errors.

### Why `v1_frozen` Failed on Multi-SKU Disputes
In [`core/entities/resolver.py`](../core/entities/resolver.py), when an image claim has `entity_ref="ITEM:UNKNOWN"` (because a warehouse dock photo shows crushed cartons without readable barcode text) or when an OCR scan introduces a 1-character typo (`SKU-IND-2O2` instead of `SKU-IND-202`), the frozen `v1_frozen` resolver fell back to linking `ITEM:UNKNOWN` to `primary_item_entity` (the **first** line item on the Purchase Order). Whenever the damaged item was actually the **second** or **third** SKU on the Purchase Order—or line items were reordered between the PO and Delivery Challan—`v1_frozen` linked the photo damage claim to the wrong SKU, triggering a cross-modal SKU conflict and forcing an abstention to `manual_review_required`.

### Designing the 42-Case Multi-SKU Stress Benchmark
We built [`evaluation/multi_sku_and_calibration.py`](../evaluation/multi_sku_and_calibration.py) with **42 blind multi-SKU cases across 7 failure modes** ($7 \times 6 = 42$ cases, all using blind PNGs with `assert b"tEXt" not in png_bytes` and opaque filenames):
1. `explicit_multi_sku` ($N=6$): Primary SKU (`SKU-IND-201`) damaged, explicitly named in challan and voice report.
2. `similar_sku_names_and_codes` ($N=6$): Near-identical SKU codes (`SKU-IND-201A` vs. `SKU-IND-201B` at different unit prices `\$180` vs. `\$310`), damage on `SKU-IND-201B`.
3. `reordered_line_items` ($N=6$): PO lists `SKU-ELC-401, SKU-ELC-402, SKU-ELC-403`, while the Delivery Challan lists them in reverse order and damage occurs on `SKU-ELC-403`.
4. `missing_visual_barcodes_blind_cv` ($N=6$): Blind pallet image shows 2–4 damaged boxes (`ITEM:UNKNOWN`), while challan and voice report attribute the exact same damage count to the secondary SKU (`SKU-IND-202`).
5. `partial_pallet_visibility` ($N=6$): Multi-SKU shipment where the pallet photo is 50% occluded by black shrink-wrap (`visual_integrity="occluded"`). Must escalate to `manual_review_required`.
6. `conflicting_sku_references` ($N=6$): Delivery challan attributes 3 damaged units to `SKU-IND-201` (`\$180/unit`), while the driver voice note attributes 3 damaged units to `SKU-IND-202` (`\$320/unit`). Must escalate to `manual_review_required`.
7. `ocr_noisy_sku_identifiers` ($N=6$): Voice transcript or OCR contains character-level noise (`SKU-IND-2O2` with letter `O` instead of `0`, or missing hyphen `SKUIND-202`).

### `v2_context_aware` Entity Resolver Architecture
We implemented `resolver_mode="v2_context_aware"` in [`core/entities/resolver.py`](../core/entities/resolver.py) with two principled mechanisms:
1. **OCR-Tolerant Canonical SKU Matching (`_normalize_ocr_sku` + `_levenshtein_le_1`)**: Normalizes visually ambiguous OCR confusions (`O` $\rightarrow$ `0`, `I`/`L` $\rightarrow$ `1`) in the numeric suffix and matches single-character edits within known PO/Challan SKUs without merging distinct suffix codes like `201A` vs. `201B`.
2. **Cross-Modal Damage Corroboration Linking**: When an image claim has `entity_ref="ITEM:UNKNOWN"` in a multi-SKU shipment, `v2_context_aware` inspects explicit SKU-tagged damage claims from corroborating modalities (challan, audio).
   - If **exactly one** known SKU has explicit damage claims across text/audio modalities (and their quantities corroborate the visual count), the blind visual claim is linked to that corroborated SKU entity.
   - If **multiple different SKUs** have competing damage claims across text/audio (e.g., challan says `SKU-IND-201` is damaged while audio says `SKU-IND-202` is damaged), `v2_context_aware` refuses to guess and preserves the ambiguity so `ConflictDetector` and `RuleEngine` escalate to `manual_review_required`.

### Head-to-Head Results ($N = 42$ Multi-SKU Stress Benchmark)

| Multi-SKU Stress Category ($N=6$ each) | `v1_frozen` Decision Acc | `v1_frozen` Strict SKU Attribution | `v2_context_aware` Decision Acc | `v2_context_aware` Strict SKU Attribution | Expected Safe Behavior |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. `explicit_multi_sku`** | `100.0%` (`6/6`) | `100.0%` (`6/6`) | **`100.0%` (`6/6`)** | **`100.0%` (`6/6`)** | Auto-settle primary SKU (`SKU-IND-201`) |
| **2. `similar_sku_names_and_codes`** (`201A` vs `201B`) | `0.0%` (`0/6`) | `0.0%` (`0/6`) | **`100.0%` (`6/6`)** | **`100.0%` (`6/6`)** | Auto-settle `SKU-IND-201B` at `\$310/unit` |
| **3. `reordered_line_items`** (3 SKUs, reverse order) | `0.0%` (`0/6`) | `0.0%` (`0/6`) | **`100.0%` (`6/6`)** | **`100.0%` (`6/6`)** | Auto-settle `SKU-ELC-403` at `\$410/unit` |
| **4. `missing_visual_barcodes_blind_cv`** (`ITEM:UNKNOWN`) | `0.0%` (`0/6`) | `0.0%` (`0/6`) | **`100.0%` (`6/6`)** | **`100.0%` (`6/6`)** | Link blind photo to corroborated `SKU-IND-202` |
| **5. `partial_pallet_visibility`** (50% occluded pallet) | `100.0%` (`6/6`) | `100.0%` (`6/6`) | **`100.0%` (`6/6`)** | **`100.0%` (`6/6`)** | Abstain (`manual_review_required`) |
| **6. `conflicting_sku_references`** (Challan `201` vs Audio `202`) | `100.0%` (`6/6`) | `100.0%` (`6/6`) | **`100.0%` (`6/6`)** | **`100.0%` (`6/6`)** | Abstain (`manual_review_required`) |
| **7. `ocr_noisy_sku_identifiers`** (`SKU-IND-2O2` / `SKUIND-202`) | `100.0%` (`6/6`) | `0.0%` (`0/6`)* | **`100.0%` (`6/6`)** | **`100.0%` (`6/6`)** | Canonicalize OCR typo to `SKU-IND-202` |
| **OVERALL ($N = 42$)** | **`57.1%` (`24/42`)** | **`42.9%` (`18/42`)** | **`100.0%` (`42/42`)** | **`100.0%` (`42/42`)** | **Confident Error Rate: `0.0%` in both** |

*\*Note on Category 7 (`ocr_noisy_sku_identifiers`): Under `v1_frozen`, the OCR typo `SKU-IND-2O2` spawned a spurious 3rd entity (`entities_count=3`), which caused `RuleEngine` to abstain on the secondary SKU (`0%` strict entity attribution).*

---

## 5. Post-Freeze Study 2: Confidence Calibration & Selective Prediction ($N = 150$ Held-Out Set)

In high-stakes financial dispute resolution, overall accuracy is less important than **Selective Prediction (Risk-Coverage)**:
- When EvidenceOS is **confident and acts** (`approved` or `partially_approved`), how often is it right?
- When EvidenceOS has **low or degraded confidence** (blurry images, hedged voice notes, conflicting quantities), how reliably does it **abstain** (`manual_review_required`)?

We evaluated calibration across all $N=150$ frozen held-out cases in [`evaluation/multi_sku_and_calibration.py`](../evaluation/multi_sku_and_calibration.py).

### 5.1 Auto-Settlement vs. Abstention Breakdown (`System D` vs. `System C`)

| Selective Prediction Metric ($N=150$ Held-Out Set) | `System D: Full EvidenceOS` (AI + Graph + Rules) | `System C: Semantic AI Only` (No Rule Engine) | Safety Implication |
| :--- | :---: | :---: | :--- |
| **Auto-Settled Cases (`approved` / `partially_approved`)** | **`33 / 150` (`22.0%` total; `78.6%` of valid claims)** | `108 / 150` (`72.0%` total) | `System D` only auto-settles when multi-modal corroboration & SLA rules pass. |
| **Auto-Settlement Precision (Accuracy when Acting)** | **`100.0%` (`33 / 33`)** *(95% CI: `[89.6%, 100.0%]`)* | `33.3%` (`36 / 108`) *(95% CI: `[25.1%, 42.7%]`)* | **Zero wrong payouts (`0 / 33`)** when `System D` acts autonomously. |
| **Abstained to Human Review (`manual_review_required`)** | **`117 / 150` (`78.0%`)** | `42 / 150` (`28.0%`) | `108` true escalations + `9` conservative abstentions on unparsed/multi-SKU claims. |
| **True Escalation Capture Rate (Abstention Recall)** | **`100.0%` (`108 / 108`)** | `33.3%` (`36 / 108`) | `System D` catches 100% of fraud, SLA violations, conflicts, and degraded evidence. |
| **Confident Error Rate (`conf >= 0.80` & Wrong Action)** | **`0.0%` (`0 / 150`)** | `48.0%` (`72 / 150`) | Removing the deterministic rule engine causes a `48.0%` confident error rate. |
| **Auto-Settlement Expected Calibration Error (ECE)** | **`0.0207` (`2.1%`)** | `0.5694` (`56.9%`) | `System D` confidence closely tracks empirical auto-settlement reliability. |

### 5.2 Reliability by Confidence Bin (`System D`, $N=150$)

| Case Minimum Modality Confidence Bin | Case Count ($N$) | Mean Confidence | Auto-Settled Count | Auto-Settlement Precision | Abstained Count (`manual_review`) | Overall Decision Accuracy | Root Cause of Bin Population |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`[0.00, 0.50]` (Severely Degraded)** | `24` | `0.3875` | `0` (`0.0%`) | `N/A` (100% abstained) | `24 / 24` (`100.0%`) | **`100.0%` (`24/24`)** | Blurry (`0.38`), dark (`0.42`), occluded (`0.45`), or irrelevant (`0.30`) images |
| **`[0.50, 0.70]` (Uncertain / Hedged)** | `6` | `0.5800` | `0` (`0.0%`) | `N/A` (100% abstained) | `6 / 6` (`100.0%`) | **`100.0%` (`6/6`)** | Hedged voice transcripts (*"maybe around 4 boxes..."*, `conf=0.58`) |
| **`[0.70, 0.85]` (Moderate)** | `0` | `—` | `0` | `—` | `0` | `—` | No held-out cases fall in `[0.70, 0.85)` |
| **`[0.85, 0.92]` (Standard Corroborated)** | `114` | `0.9058` | `33` (`28.9%`) | **`100.0%` (`33/33`)** | `81 / 114` (`71.1%`) | **`92.1%` (`105/114`)** | Clean & partial claims (`33` auto-settled at `100%` precision) + SLA/conflict escalations + `9` conservative abstentions |
| **`[0.92, 1.00]` (High Certainty)** | `6` | `0.9200` | `0` (`0.0%`) | `N/A` | `6 / 6` (`100.0%`) | **`100.0%` (`6/6`)** | High-confidence documents that fail SLA/policy rules and properly escalate |

### 5.3 Selective Prediction Threshold Sweep ($\tau \in [0.50, 0.95]$)

When sweeping the minimum confidence threshold $\tau$ required to permit auto-settlement (`approved` or `partially_approved`):

| Confidence Gate $\tau$ | Auto-Settlement Coverage (`%` of $N=150$) | Auto-Settled Cases | Auto-Settlement Precision | Selective Risk (Wrong Payout Rate) | Abstained to Human Review |
| :---: | :---: | :---: | :---: | :---: | :---: |
| $\tau = 0.50$ | `22.0%` | `33 / 150` | **`100.0%` (`33/33`)** | **`0.0%` (`0/33`)** | `117 / 150` (`78.0%`) |
| $\tau = 0.65$ | `22.0%` | `33 / 150` | **`100.0%` (`33/33`)** | **`0.0%` (`0/33`)** | `117 / 150` (`78.0%`) |
| $\tau = 0.75$ *(Production Default)* | `22.0%` | `33 / 150` | **`100.0%` (`33/33`)** | **`0.0%` (`0/33`)** | `117 / 150` (`78.0%`) |
| $\tau = 0.85$ | `22.0%` | `33 / 150` | **`100.0%` (`33/33`)** | **`0.0%` (`0/33`)** | `117 / 150` (`78.0%`) |
| $\tau = 0.90$ | `22.0%` | `33 / 150` | **`100.0%` (`33/33`)** | **`0.0%` (`0/33`)** | `117 / 150` (`78.0%`) |
| $\tau = 0.95$ | `0.0%` | `0 / 150` | `100.0%` (`0/0`) | `0.0%` | `150 / 150` (`100.0%`) |

---

## 6. Reproducing the Audit & Post-Freeze Experiments

```bash
# Verify cryptographic hashes against v1.0.0-benchmark-frozen and run N=42 Multi-SKU + N=150 Calibration suite
python -m evaluation.multi_sku_and_calibration

# Run full pytest suite (including audit & v2_context_aware verification)
python -m pytest -v
```
