# Reproducibility Guide

EvidenceOS is engineered so that any researcher, reviewer, or developer can reproduce every dataset split, baseline comparison, modality ablation, perceptual hashing test, and prompt injection evaluation with a single deterministic command.

---

## 1. Environment & Determinism Guarantees

- **Python Version**: Python `3.11+` (tested on Python `3.12.7`)
- **Frontend Runtime**: Node.js `20+` / `24+` with `npm`
- **Deterministic Seed**: `seed = 42` across all dataset generators (`core/datasets_generator.py` and `evaluation/datasets/generator.py`)
- **Zero External API Dependency for Reproducible Benchmarks**: All four benchmarked systems (`Baseline A`, `Baseline B`, `System C`, `System D`) and all 6 modality ablations run 100% deterministically offline with blind pixel-level computer vision (`analyze_pallet_pixels_blind`) and acoustic/transcript parsing.

---

## 2. Step-by-Step Reproduction Commands

### Step 1: Install Backend & Frontend Dependencies
```bash
# From the repository root (c:\gitprojects\evidenceos)
pip install -e ".[dev]"

# Install frontend dependencies
cd apps/web
npm install
cd ../..
```

### Step 2: Run the Full Research Evaluation Suite
Execute the master evaluation runner:
```bash
python -m scripts.run_evaluation
```
*(Alternatively: `python evaluation/scripts/run_evaluation.py`)*

**What this command executes (`~65 seconds` total runtime)**:
1. **Generates and verifies all three dataset splits (`seed=42`)**:
   - `canonical_5` (`5` cases, `20` files)
   - `development_60` (`60` cases, `234` files across `10` categories)
   - `heldout_150` (`150` blind held-out cases, `564` files across `25` categories with generic filenames `artifact_01.pdf`..`artifact_04.wav` and zero PNG metadata leakage)
2. **Generates the 30-case stratified human audit sample**:
   - Writes [`evaluation/datasets/human_validation_sample_30.json`](../evaluation/datasets/human_validation_sample_30.json) and [`evaluation/datasets/heldout_test_150_manifest.json`](../evaluation/datasets/heldout_test_150_manifest.json).
3. **Evaluates all 4 System Architectures on `heldout_150`**:
   - `Baseline A` (Strict Regex + Rules)
   - `Baseline B` (Structured Deterministic Normalizer + Rules)
   - `System C` (Semantic Multimodal AI Only — No Rule Engine)
   - `System D` (Full EvidenceOS — Semantic AI + Perceptual `dHash` + Deterministic Rules)
4. **Executes the 6-Stage Modality Ablation Study (`Ablation A` through `Ablation F`)** on `heldout_150`.
5. **Executes the 40-Pair Perceptual Hashing (`64-bit dHash`) vs. `SHA-256` Benchmark**.
6. **Executes the 15-Case Adversarial Prompt Injection Suite** across 5 injection vectors.
7. **Writes all machine-readable and human-readable outputs**:
   - [`evaluation/results.json`](../evaluation/results.json) (Primary evaluation artifact)
   - [`evaluation/failures.json`](../evaluation/failures.json) (Every failure trace across all 4 systems with taxonomy codes)
   - [`evaluation/results/experiments_registry.jsonl`](../evaluation/results/experiments_registry.jsonl) (Append-only experiment log with Git commit hash and timestamp)
   - [`evaluation/reports/latest_evaluation_summary.md`](../evaluation/reports/latest_evaluation_summary.md) (Auto-generated markdown summary tables)

---

## 3. Running Automated Test & Lint Suites

```bash
# 1. Python linter & formatter check
python -m ruff check .

# 2. Backend unit & integration test suite
python -m pytest -v

# 3. Frontend unit test suite (Vitest)
cd apps/web
npm test -- --run

# 4. Production TypeScript & Vite bundle build
npm run build
cd ../..
```

---

## 4. Verifying Benchmark Leakage Controls

To verify that the 150-case Held-Out Test Set contains **zero filename hints, zero case-ID hints, and zero PNG text metadata chunks**, inspect:
1. [`evaluation/datasets/heldout_test_150_manifest.json`](../evaluation/datasets/heldout_test_150_manifest.json): Every case uses neutral identifiers (`heldout_case_001`..`heldout_case_150`) and blind filenames (`artifact_01.pdf`, `artifact_02.pdf`, `artifact_03.png`, `artifact_04.wav`).
2. [`core/datasets_generator.py`](../core/datasets_generator.py): When `blind_mode=True`, `generate_inspection_png_bytes()` omits all `tEXt` PNG metadata chunks and renders physical scenes purely through pixel luminance, variance, occlusion bands, and parcel chromaticity.
3. [`core/ai/provider.py`](../core/ai/provider.py): `analyze_pallet_pixels_blind()` computes image claims exclusively from RGB pixel arrays (`mean_luma`, `std_luma`, `center_band_std`, and `2x5` parcel cell red/green ratios) without inspecting filenames or metadata.
