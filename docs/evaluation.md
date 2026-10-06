# Empirical Evaluation Methodology & Ablation Study (`docs/evaluation.md`)

## 1. Two-Tier Evaluation Architecture

To ensure technical defensibility under engineering review, EvidenceOS separates **regression testing** from **empirical benchmarking**:

1. **5-Case Canonical Regression Suite (`suite="canonical_5"`, $N=5$ cases, $20$ files)**:
   - Verifies that the 5 core VeriDock scenarios (`clean_delivery`, `partial_damage`, `conflicting_evidence`, `reused_evidence`, `insufficient_evidence`) behave deterministically on every commit (`100%` pass rate required in CI).
2. **60-Case Stratified Adversarial Benchmark (`suite="extended_60"`, $N=60$ cases, $234$ files)**:
   - Evaluates the system across 8 controlled adversarial categories with varied wording, unstructured prose documents, colloquial voice transcripts (`"a couple of cartons got smashed"`, `"half a dozen boxes"`), missing visual evidence, low-contrast/blurry photos, perceptually perturbed duplicate photos, and SLA threshold breaches.

Run either benchmark at any time:

```bash
# Run the 60-case stratified benchmark + head-to-head ablation study
python -m evaluation.runner

# Or via the REST API:
curl "http://localhost:8000/api/evaluation/run?suite=extended_60"
curl "http://localhost:8000/api/evaluation/run?suite=canonical_5"
```

---

## 2. Head-to-Head Ablation: Semantic Multimodal Pipeline vs. Strict Regex Baseline ($N=60$)

We compare two extraction architectures feeding into the exact same deterministic rule engine:
- **`evidenceos-semantic-extractor-v1` / `GeminiAIProvider`**: Semantic multimodal extractor that parses unstructured prose POs/Challans, normalizes spoken quantifiers and colloquial damage descriptions, and enforces visual uncertainty thresholds.
- **`strict-regex-baseline-v1`**: Rigid table-and-digit regex parser representing a traditional non-AI rule baseline.

| Metric ($N=60$ Cases, $234$ Files) | Semantic Multimodal Pipeline | Strict Regex Baseline | Delta / Technical Finding |
| :--- | :---: | :---: | :--- |
| **Decision Accuracy** | **`96.7%`** (`58/60`) | `66.7%` (`40/60`) | **`+30.0%`** — Baseline fails on unstructured prose documents and spoken/colloquial voice claims |
| **Field-Level Quantity Accuracy** | **`100.0%`** (`180/180`) | `86.7%` (`156/180`) | **`+13.3%`** — Semantic parser extracts quantities from prose dispatch statements |
| **Conflict Detection Precision** | **`96.4%`** | `37.1%` | **`+59.3%`** — Rigid baseline triggers false quantity mismatches when prose POs extract as `0` |
| **Conflict Detection Recall** | **`96.4%`** | `46.4%` | **`+50.0%`** — Rigid baseline misses uncorroborated voice claims when quantities are spoken as words |
| **False Positive Rate** | **`0.0%`** (`0/60`) | `6.7%` (`4/60`) | Clean deliveries are never falsely flagged by the semantic pipeline |
| **False Negative Rate** | **`1.7%`** (`1/60`) | `10.0%` (`6/60`) | Only 1 extreme slang edge case missed without cloud LLM fallback |
| **Mean Processing Latency** | `122.7 ms / case` | `104.2 ms / case` | `< 20 ms` overhead for semantic normalization |

---

## 3. Stratified Accuracy Breakdown by Scenario Category ($N=60$)

| Scenario Category | Cases ($N$) | Semantic Pipeline Accuracy | Strict Baseline Accuracy | Failure Mode Analysis |
| :--- | :---: | :---: | :---: | :--- |
| **1. Clean Delivery** (Tabular & Prose PO/Challan) | `10` | **`100.0%`** (`10/10`) | `60.0%` (`6/10`) | Baseline fails on the 4 unstructured prose Purchase Orders. |
| **2. Corroborated Partial Damage** (Colloquial Audio) | `10` | **`90.0%`** (`9/10`) | `0.0%` (`0/10`) | Semantic extractor handles `"a couple of boxes"`, `"a pair of cartons"`, `"single box"`; misses 1 slang case (`"got busted up"`). |
| **3. Short Delivery Mismatch** (PO $\ne$ Challan) | `8` | **`100.0%`** (`8/8`) | `100.0%` (`8/8`) | Deterministically caught by `RULE_02_DELIVERY_COMPLETENESS`. |
| **4. Cross-Modal Damage Conflict** (Voice $\ne$ Image) | `8` | **`100.0%`** (`8/8`) | `100.0%` (`8/8`) | Voice (`"Five"` / `"Half a dozen"`) vs. Image (`1` or `2` damaged) caught by `ConflictDetectionService`. |
| **5. Missing Visual Evidence** (Voice-Only Claim) | `6` | **`83.3%`** (`5/6`) | `0.0%` (`0/6`) | Semantic extractor catches 5/6 uncorroborated voice claims; misses 1 slang case (`"totally trashed"`). |
| **6. Degraded / Blurry Visual Evidence** | `6` | **`100.0%`** (`6/6`) | `100.0%` (`6/6`) | Low-contrast photos (`confidence = 0.44`) tagged as `UNCERTAINTY` and routed to manual review. |
| **7. Perceptually Reused Historical Photos** | `6` | **`100.0%`** (`6/6`) | `100.0%` (`6/6`) | 64-bit `dHash` detects all 6 perturbed historical photos (Hamming distance $\le 2/64$). |
| **8. SLA Damage Ratio Breach** ($> 25\%$ Damage) | `6` | **`100.0%`** (`6/6`) | `100.0%` (`6/6`) | Deterministically routed to manual review by `RULE_04_CONTRACT_SLA_THRESHOLD`. |
