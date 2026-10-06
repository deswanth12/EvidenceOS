# Empirical Evaluation Methodology & Results (`docs/evaluation.md`)

## 1. Reproducible Benchmark Methodology

The EvidenceOS evaluation harness (`evaluation/runner.py`) creates an isolated temporary database and filesystem store, generates the 5 canonical multimodal B2B dispute cases (`20` binary PDF, PNG, and WAV files), runs the full 12-stage verification pipeline end-to-end, and measures actual outputs against ground-truth expectations.

Run the benchmark at any time via CLI or API:

```bash
python -m evaluation.runner
# or via REST API:
curl http://localhost:8000/api/evaluation/run
```

---

## 2. Measured Benchmark Results (`veridock-eval-v1.0`)

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Total Cases Evaluated** | `5` | Canonical VeriDock benchmark suite (`case_01` – `case_05`) |
| **Total Evidence Artifacts** | `20` | 5 PDF POs, 5 PDF Challans, 5 PNG Inspection Photos, 5 WAV Voice Reports |
| **Extraction Accuracy** | `100.0%` (`20/20`) | All 20 multimodal artifacts parsed into validated Pydantic models |
| **Field-Level Accuracy** | `100.0%` (`15/15`) | Exact match on `ordered_quantity`, `delivered_quantity`, `verified_damaged_quantity` |
| **Entity Matching Accuracy** | `100.0%` (`5/5`) | Cross-modal claims resolved to canonical `ITEM:SKU-IND-100` |
| **Conflict Detection Precision** | `100.0%` (`3/3`) | Zero false conflict alarms on clean or corroborated cases |
| **Conflict Detection Recall** | `100.0%` (`3/3`) | Detected `SHORT_DELIVERY_MISMATCH`, `DAMAGE_QUANTITY_CONTRADICTION`, and `INSUFFICIENT_VISUAL_CORROBORATION` |
| **Duplicate Detection Accuracy** | `100.0%` (`5/5`) | 64-bit dHash detected perceptually perturbed image in Case 4 (Hamming distance $\le 4/64$) with 0 false matches on Cases 1–3 & 5 |
| **Decision Accuracy** | `100.0%` (`5/5`) | Exact match across `approved`, `partially_approved`, and `manual_review_required` |
| **False Positive Rate** | `0.0%` | Clean deliveries were never erroneously rejected |
| **False Negative Rate** | `0.0%` | Conflicting, reused, or weak-evidence claims were never auto-approved |
| **Mean Processing Latency** | `~158 ms / case` | Measured end-to-end including PDF parsing, dHash, and SQLite commits |
| **P95 Processing Latency** | `~184 ms / case` | Full 4-artifact multimodal case processing |

---

## 3. Case-by-Case Breakdown

| Case ID | Scenario | PO / Challan / Voice / Image | Conflicts | Historical Reuse | Expected vs. Actual Decision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `case_01_clean_delivery` | Clean delivery | `10` / `10` / `0 dmg` / `0 dmg` | `0` | `0` | `approved` == `approved` ✓ |
| `case_02_partial_damage` | Legitimate partial damage | `10` / `10` / `2 dmg` / `2 dmg` | `0` | `0` | `partially_approved` == `partially_approved` ✓ |
| `case_03_conflicting_evidence` | Conflicting quantities | `10` / `8` / `5 dmg` / `2 dmg` | `2` | `0` | `manual_review_required` == `manual_review_required` ✓ |
| `case_04_reused_evidence` | Perceptually reused photo | `10` / `10` / `2 dmg` / `2 dmg (reused)` | `0` | `1` (`dHash`) | `manual_review_required` == `manual_review_required` ✓ |
| `case_05_insufficient_evidence` | Blurry / weak photo | `10` / `10` / `4 dmg` / `UNCLEAR (conf 0.45)` | `1` | `0` | `manual_review_required` == `manual_review_required` ✓ |
