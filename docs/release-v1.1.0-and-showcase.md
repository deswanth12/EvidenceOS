# EvidenceOS (`VeriDock`) — GitHub Release Notes (`v1.1.0`) & Technical Showcase Kit
 
**Repository**: `https://github.com/deswanth12/EvidenceOS`  
**Git Lineage & Release Tags**:
- `v1.0.0-benchmark-frozen` (`commit 07c8065`) — Cryptographically locked 150-case blind held-out benchmark (`94.0%` decision accuracy, `0.0%` confident error rate)
- `v1.1.0-research-hardened` (`commit d5f1138`, lineage `66df00c`) — Research release tag: Multi-SKU entity linking stress study (`57.1%` $\rightarrow$ `100.0%`), 150-case confidence calibration (`ECE = 0.0207`), and 14-slide presentation deck
- `main` (`HEAD`) — Post-release adversarial audit remediations (`AUD-01` row payload re-hashing, `AUD-02` monotonic audit sequence, and final pre-release audit report)

---

## 1. Ready-to-Publish GitHub Release (`v1.1.0-research-hardened`)

> Copy and paste the block below directly into **`https://github.com/deswanth12/EvidenceOS/releases/new?tag=v1.1.0-research-hardened`**

### Release Title
`v1.1.0-research-hardened — Epistemic Multimodal Verification, Frozen Held-Out Benchmark (N=150), Calibration & Multi-SKU Audit`

### Release Body (Markdown)
```markdown
## EvidenceOS (`VeriDock`) — `v1.1.0-research-hardened`

> **Core Architectural Principle**: *"The AI interprets evidence; deterministic rules constrain the decision; uncertainty triggers human review."*

This release completes the **Freeze → Evaluate → Attack → Audit → Document → Release** cycle for **EvidenceOS (`VeriDock`)**, an epistemically grounded multimodal AI and deterministic rule engine for high-stakes B2B delivery dispute verification.

---

### 1. Frozen Primary Held-Out Benchmark (`v1.0.0-benchmark-frozen`, `N = 150` Cases / `564` Files)

To prevent test-set snooping, our primary 150-case blind held-out evaluation (`seed=42`, zero filename or PNG metadata leakage, `assert b"tEXt" not in png_bytes`) is cryptographically locked in [`evaluation/datasets/benchmark_freeze_manifest.json`](evaluation/datasets/benchmark_freeze_manifest.json):

| Evaluated System (`N = 150` Blind Held-Out Set) | Decision Accuracy (95% Wilson CI) | Macro-F1 | Conflict F1 | Auto-Settlement Precision | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline A**: Strict Regex + Rules | `72.0%` (`108/150`) `[64.3%, 78.6%]` | `0.4245` | `0.7161` | `84.6%` | `4.0%` (`6/150`) |
| **Baseline B**: Structured Normalizer + Rules | `78.0%` (`117/150`) `[70.7%, 83.9%]` | `0.4558` | `0.7902` | `100.0%` | `0.0%` (`0/150`) |
| **System C**: Semantic Multimodal AI Only (No Rules) | `44.0%` (`66/150`) `[36.3%, 52.0%]` | `0.4969` | `0.9505` | `33.3%` (`36/108`) | **48.0%** (`72/150`) |
| **System D**: **Full EvidenceOS (Semantic AI + Rules)** | **94.0%** (`141/150`) `[89.0%, 96.8%]` | **0.9132** | **0.9505** | **100.0%** (`33/33`) | **0.0%** (`0/150`) |

---

### 2. Confidence Calibration & Selective Prediction (`N = 150`)

Rather than optimizing for raw accuracy alone, EvidenceOS is architected for **Selective Prediction (Risk-Coverage)**:
- **100.0% Auto-Settlement Precision (`33 / 33`, 95% CI `[89.6%, 100.0%]`)**: Zero wrong automated payouts when EvidenceOS acts autonomously (`approved` / `partially_approved`).
- **100.0% True Escalation Capture Rate (`108 / 108`)**: Every case involving SLA breaches, cross-modal quantity contradictions, reused historical photos, or degraded vision/audio is escalated to `manual_review_required`.
- **Expected Calibration Error (`ECE`)**: **`0.0207` (`2.1%`)** for Full EvidenceOS (`System D`) vs. **`0.5694` (`56.9%`)** for standalone AI (`System C`).

---

### 3. Independent Code & Metric Audit (`docs/independent-audit.md`)

We audited our own evaluation harness for synthetic shortcuts and metric edge cases:
- **Corrected Entity Attribution Metric (`AUDIT_FINDING_02`)**: Identified that the original `entity_matching_accuracy` (`100.0%`) checked resolved SKU *counts* (`entities_count == 2`), which masked 3 multi-SKU cases where blind parcel damage (`ITEM:UNKNOWN`) linked to the primary SKU instead of the secondary SKU. Under **strict claim-to-SKU attribution accuracy**, the frozen `heldout_150` benchmark scores **`98.0%` (`147/150`)** overall and **`50.0%` (`3/6`)** on `multi_sku_dispute`.
- **Offline Pixel Grid Disclosure (`AUDIT_NOTE_01`)**: Documented that offline computer vision (`analyze_pallet_pixels_blind`) inspects the `2x5` parcel grid of our procedural renderer; unconstrained smartphone photos require enabling `GEMINI_API_KEY` (`GeminiAIProvider` multimodal vision) or a trained object detector.

---

### 4. Post-Freeze Multi-SKU Entity Linking Stress Benchmark (`N = 42`)

Without modifying the frozen `v1_frozen` benchmark, we built a dedicated **42-case Multi-SKU Stress Suite** across 7 failure modes (`similar_sku_names_and_codes`, `reordered_line_items`, `missing_visual_barcodes_blind_cv`, `ocr_noisy_sku_identifiers`, etc.) and evaluated our context-aware resolver (`v2_context_aware`):
- **`v1_frozen` (Primary-SKU Fallback)**: `57.1%` decision accuracy (`24/42`), `42.9%` strict SKU attribution (`18/42`), `0.0%` confident error rate.
- **`v2_context_aware` (OCR-Canonicalized + Cross-Modal Corroboration)**: **`100.0%` decision accuracy (`42/42`)**, **`100.0%` strict SKU attribution (`42/42`)**, `0.0%` confident error rate.

---

### 5. Verification & Reproducibility
- `13 / 13` backend unit & integration tests passing (`pytest`)
- `10 / 10` frontend component & UI tests passing (`vitest`)
- `0` linter errors (`ruff check .`)
- Single-command reproduction: `python -m scripts.run_evaluation && python -m evaluation.multi_sku_and_calibration`
```

---

## 2. LinkedIn / Project Showcase Posts

### Option A: Technical & Research-Focused Post (Recommended for AI Engineers, Researchers & Founders)

```text
Most AI demos stop the moment the happy path works on 5 examples.

With EvidenceOS (VeriDock) — an AI evidence verification engine for B2B delivery & procurement disputes — I wanted to follow a stricter engineering loop:

Freeze → Evaluate → Attack → Audit → Document → Release.

B2B delivery disputes are messy: a Purchase Order (PDF), a Delivery Challan (PDF), a warehouse dock photo (PNG), and a driver's voice note (WAV) rarely agree cleanly.

If you wire a raw LLM directly to settlement decisions, it hallucinates quantities, ignores 48-hour SLA windows, and falls for prompt injection. If you use strict regex rules alone, it breaks on colloquial dock speech ("half a dozen cartons smashed") and OCR noise.

So we built an epistemically typed hybrid architecture:
"The AI interprets evidence; deterministic rules constrain the decision; uncertainty triggers human review."

Here is what happened when we locked the system (`v1.0.0-benchmark-frozen`) and tested it on a 150-case blind held-out benchmark (564 files across 25 adversarial categories, all filename & PNG metadata hints stripped):

1. Overall Held-Out Decision Accuracy (N=150):
• Full EvidenceOS (Semantic AI + Graph + Deterministic Rules): 94.0% (141/150, 95% CI [89.0%, 96.8%])
• Structured Normalizer Baseline: 78.0%
• Strict Regex Baseline: 72.0%
• Standalone Semantic AI (No Rule Engine): 44.0%

2. The Real Story — Confidence Calibration & Selective Prediction:
In financial workflows, overall accuracy matters less than what happens when the system acts autonomously:
• Standalone AI auto-settled 72% of cases, but with only 33.3% precision and a 48.0% confident error rate (ECE = 0.5694).
• Full EvidenceOS achieved 100.0% precision whenever it automatically settled a claim (33/33), captured 100.0% of cases requiring human escalation (108/108), and had a 0.0% confident error rate (ECE = 0.0207). All 9 extraction/linking misses safely abstained to manual review.

3. Auditing & Attacking Our Weakest Point:
During our post-freeze code audit, we found our original entity-count metric overstated multi-SKU performance — strict claim-to-SKU attribution was 98.0% overall, and Multi-SKU disputes were our hardest category at 50.0% (3/6).
Instead of editing the frozen benchmark, we built a separate 42-case Multi-SKU stress suite across 7 failure modes (similar SKU codes, reordered line items, blind photos without barcodes, OCR typos). Adding OCR canonicalization + cross-modal damage corroboration (`v2_context_aware`) took Multi-SKU stress accuracy from 57.1% (24/42) to 100.0% (42/42).

What's inside the repo:
• FastAPI + SQLAlchemy backend & React 19 + TypeScript investigation workbench
• Inline PDF provenance highlighting & side-by-side 64-bit dHash reused-image fraud detection (100% recall across recompression, crops & brightness shifts vs. 25% for SHA-256 alone)
• Tamper-evident SHA-256 hash-chained audit ledger
• Full failure analysis, independent code audit, and 1-command reproducibility (`seed=42`)

GitHub Repo: https://github.com/deswanth12/EvidenceOS
```

---

### Option B: Concise Product & Systems Post (Shorter Hook)

```text
Why shouldn't an LLM directly approve a B2B financial claim?

Because in our 150-case held-out benchmark for EvidenceOS (VeriDock), running multimodal AI without a deterministic rule engine produced a 48.0% confident error rate — auto-approving late SLA filings, high-value disputes, and uncorroborated claims.

When we paired multimodal extraction (PDFs + Dock Photos + Voice Notes) with an epistemic provenance graph, 64-bit perceptual dHash fraud detection, and a deterministic contract rule engine:

• Held-out decision accuracy reached 94.0% (141/150) vs. 72.0% for strict regex
• Auto-settlement precision reached 100.0% (33/33) with a 0.0% confident error rate (ECE = 0.0207)
• Every single extraction miss (9/150) safely abstained to human review rather than issuing a wrong payout
• Reused image fraud detection jumped from 25.0% recall (SHA-256) to 100.0% recall (SHA-256 + 64-bit dHash)

We froze the v1.0.0 benchmark, audited our own evaluation code, attacked our weakest category (Multi-SKU entity linking, 57.1% -> 100.0% on a 42-case stress suite), and open-sourced the full platform + research report:

https://github.com/deswanth12/EvidenceOS
```

---

## 3. Defensible Technical FAQ ("Uncomfortable Questions & Exact Answers")

Use these exact responses when engineers, researchers, or interviewers probe the system:

1. **"Is the 94.0% accuracy on real-world enterprise production data?"**
   - **Answer**: *"No—and we explicitly disclose that in the README and `docs/independent-audit.md` (`AUDIT_NOTE_01`). The 150-case held-out set is a blind, procedurally generated + real-world-inspired adversarial benchmark where all filenames (`artifact_01..04`), roles (`unknown`), and PNG text chunks (`assert b'tEXt' not in png_bytes`) are stripped. On the 116 standard procedural cases it scores 100%, and on the 34 real-world-inspired adversarial cases (unseen slang, severe OCR noise, German headers, multi-SKU blind photos) it scores 73.5%, with all 9 misses safely abstaining to manual review."*
2. **"Why didn't you re-run the 150-case held-out benchmark with `v2_context_aware` to claim 96.0% instead of 94.0%?"**
   - **Answer**: *"Because modifying the system after inspecting held-out failures and re-reporting the held-out score is test-set leakage. We froze the 150-case benchmark at `v1.0.0-benchmark-frozen` (`94.0%`), kept `v1_frozen` as the default for reproducibility, and evaluated `v2_context_aware` on a separate 42-case Multi-SKU stress benchmark (`57.1% -> 100.0%`)."*
3. **"Did you find any flaws in your own evaluation metrics?"**
   - **Answer**: *"Yes (`AUDIT_FINDING_02`). Our original `entity_matching_accuracy` metric checked whether the count of resolved SKU entities matched ground truth (`100%`), which masked 3 multi-SKU cases where a blind parcel photo linked to the first SKU on the PO instead of the second SKU. When we tightened the metric to strict claim-to-SKU attribution, held-out accuracy was `98.0%` (`147/150`) overall and `50.0%` (`3/6`) on multi-SKU cases."*
