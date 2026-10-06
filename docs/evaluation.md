# Evaluation Methodology & Benchmark Architecture

**Primary Evaluation Artifacts**:
- [`evaluation/results.json`](../evaluation/results.json) — Complete metrics, 95% Wilson CIs, confusion matrices, ablations, latencies, and cost estimates.
- [`evaluation/failures.json`](../evaluation/failures.json) — Exhaustive failure logs and error taxonomy codes across all 4 evaluated systems.
- [`docs/research-report.md`](research-report.md) — 15-section empirical study answering the primary and 9 secondary research questions.
- [`docs/failure-analysis.md`](failure-analysis.md) — Root-cause dissection of all `9` held-out errors in `System D`.

---

## 1. Strict Three-Split Benchmark Architecture

To prevent benchmark overfitting and eliminate data leakage, EvidenceOS enforces a strict separation across three dataset splits (`seed=42`):

1. **`CANONICAL REGRESSION SUITE` (`canonical_5`, `N = 5` cases, `20` files)**:
   - Covers the 5 core B2B dispute archetypes: Clean Delivery (`APPROVED_FULL`), Corroborated Partial Damage (`APPROVED_PARTIAL_SETTLEMENT`), Cross-Modal Contradiction (`MANUAL_REVIEW_REQUIRED`), Historical Reused Photo (`REJECTED_DUPLICATE_EVIDENCE`), and Degraded Blurry Photo (`MANUAL_REVIEW_REQUIRED`).
   - **Purpose**: Fast CI regression smoke test (`100.0%` accuracy, `5/5`). Never marketed as proof of open-world generalization.
2. **`DEVELOPMENT BENCHMARK` (`development_60`, `N = 60` cases, `234` files across `10` categories)**:
   - Used during development to tune normalizer rules, conflict thresholds, and prompt sanitization.
   - **Result**: `96.7%` decision accuracy (`58/60`, 95% Wilson CI `[88.6%, 99.1%]`) vs. `66.7%` (`40/60`) for the Strict Regex Baseline.
3. **`BLIND HELD-OUT TEST SET` (`heldout_150`, `N = 150` cases, `564` files across `25` categories)**:
   - **Zero Leakage**: Uses generic filenames (`artifact_01.pdf`, `artifact_02.pdf`, `artifact_03.png`, `artifact_04.wav`), neutral case IDs (`heldout_case_001`..`150`), and pure pixel rendering (`blind_mode=True`) with zero PNG text metadata chunks.
   - **Explicit Data Origin**: `116` `SYNTHETIC` cases (`100.0%` accuracy) and `34` `REAL_WORLD_INSPIRED` cases (`73.5%` accuracy).
   - **Human Audit Sample**: `30` stratified cases (`20%` of the held-out set) independently verified with **96.7% (`29/30`) inter-reviewer agreement** ([`evaluation/datasets/human_validation_sample_30.json`](../evaluation/datasets/human_validation_sample_30.json)).

---

## 2. The 25 Adversarial Categories in `heldout_150` (`6` Cases per Category)

| # | Category ID | Data Origin | Ground-Truth Expected Decision | Per-Case Accuracy (`System D`) |
| :---: | :--- | :---: | :--- | :---: |
| 1 | `clean_delivery` | `SYNTHETIC` | `approved_full` | `6/6 (100.0%)` |
| 2 | `corroborated_partial_damage` | `SYNTHETIC` | `approved_partial_settlement` | `6/6 (100.0%)` |
| 3 | `severe_damage_ratio_review` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 4 | `high_value_manual_review` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 5 | `single_source_damage_claim` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 6 | `contradictory_quantities` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 7 | `contradictory_damage_counts` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 8 | `late_claim_submission` | `SYNTHETIC` | `rejected_late_filing` | `6/6 (100.0%)` |
| 9 | `borderline_sla_window` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 10 | `exact_duplicate_image` | `SYNTHETIC` | `rejected_duplicate_evidence` | `6/6 (100.0%)` |
| 11 | `recompressed_image` | `SYNTHETIC` | `rejected_duplicate_evidence` | `6/6 (100.0%)` |
| 12 | `cropped_or_brightness_shifted_image` | `SYNTHETIC` | `rejected_duplicate_evidence` | `6/6 (100.0%)` |
| 13 | `colloquial_wording` | `REAL_WORLD_INSPIRED` | `approved_partial_settlement` | **`4/6 (66.7%)`** |
| 14 | `typos_and_ocr_noise` | `REAL_WORLD_INSPIRED` | `approved_partial_settlement` | **`4/6 (66.7%)`** |
| 15 | `multilingual_or_mixed_terms` | `REAL_WORLD_INSPIRED` | `approved_partial_settlement` | **`4/6 (66.7%)`** |
| 16 | `hedged_uncertain_voice` | `REAL_WORLD_INSPIRED` | `manual_review_required` | `6/6 (100.0%)` |
| 17 | `blurry_image` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 18 | `low_light_image` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 19 | `occluded_image` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 20 | `missing_purchase_order` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 21 | `missing_delivery_challan` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 22 | `missing_visual_evidence` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 23 | `conflicting_sku_identifiers` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |
| 24 | `multi_sku_dispute` | `REAL_WORLD_INSPIRED` | `approved_partial_settlement` (`3`) / `manual_review_required` (`3`) | **`3/6 (50.0%)`** |
| 25 | `irrelevant_uploaded_evidence` | `SYNTHETIC` | `manual_review_required` | `6/6 (100.0%)` |

---

## 3. Summary of Held-Out Results (`N = 150`)

| System | Decision Accuracy | 95% Wilson CI | Macro-F1 | Field Accuracy | Conflict F1 | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline A (Strict Regex)** | `72.0%` (`108/150`) | `[64.3%, 78.6%]` | `0.4245` | `85.8%` | `0.7161` | `4.0%` (`6/150`) |
| **Baseline B (Structured Normalizer)** | `78.0%` (`117/150`) | `[70.7%, 83.9%]` | `0.4558` | `85.8%` | `0.7902` | `0.0%` (`0/150`) |
| **System C (Semantic AI Only — No Rules)** | `44.0%` (`66/150`) | `[36.3%, 52.0%]` | `0.4969` | `90.2%` | `0.9505` | **48.0%** (`72/150`) |
| **System D (Full EvidenceOS)** | **94.0%** (`141/150`) | **`[89.0%, 96.8%]`** | **`0.9132`** | **`95.6%`** | **`0.9505`** | **0.0%** (`0/150`) |

To reproduce all numbers from scratch:
```bash
python -m scripts.run_evaluation
```
