# EvidenceOS (`VeriDock`) — Automated Research Evaluation Summary

- **Git Commit**: `daf2911`
- **Dataset Version**: `evidenceos-benchmark-v3.0-split-5-60-150`
- **Prompt Version**: `veridock-extraction-v2.1-sanitized`
- **Random Seed**: `42`
- **Timestamp (UTC)**: `2026-10-06T05:12:39.692244+00:00`
- **Human Ground-Truth Validation (30-Case Stratified Sample)**: `96.7%` inter-reviewer agreement

## 1. Performance Across Dataset Splits (`System D: Full EvidenceOS`)

| Dataset Split | Cases (`N`) | Decision Accuracy | 95% Wilson CI | Macro-F1 | Field Accuracy | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Canonical Regression (`canonical_5`)** | 5 | 100.0% | [56.5%, 100.0%] | 1.000 | 100.0% | 0.0% |
| **Development Benchmark (`development_60`)** | 60 | 96.7% | [88.6%, 99.1%] | 0.958 | 100.0% | 1.7% |
| **Blind Held-Out Test Set (`heldout_150`)** | 150 | **94.0%** | **[89.0%, 96.8%]** | **0.913** | **95.6%** | **0.0%** |

## 2. Four-System Baseline Comparison on Blind Held-Out Test Set (`N=150`)

| System | Decision Accuracy | 95% Wilson CI | Macro-F1 | Field Accuracy | Conflict F1 | Abstention Rate | Confident Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline A: Strict Regex / Keyword Baseline** | 72.0% | [64.3%, 78.6%] | 0.424 | 85.8% | 0.716 | 94.4% | 4.0% |
| **Baseline B: Structured Deterministic Normalizer** | 78.0% | [70.7%, 83.9%] | 0.456 | 85.8% | 0.790 | 100.0% | 0.0% |
| **System C: Semantic Multimodal AI Only (No Rule Engine)** | 44.0% | [36.3%, 52.0%] | 0.497 | 90.2% | 0.951 | 33.3% | 48.0% |
| **System D: EvidenceOS (Semantic AI + Deterministic Rules)** | 94.0% | [89.0%, 96.8%] | 0.913 | 95.6% | 0.951 | 100.0% | 0.0% |

## 3. Six-Stage Modality Ablation Study on Blind Held-Out Test Set (`N=150`)

| Ablation Stage | Configuration | Decision Accuracy | 95% Wilson CI | Macro-F1 | Conflict Recall | Duplicate Acc | Confident Error Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Ablation A** | Documents Only (PO + Challan) | 36.7% | [29.4%, 44.6%] | 0.256 | 37.5% | 88.0% | 62.0% |
| **Ablation B** | Documents + Voice Report | 76.7% | [69.3%, 82.7%] | 0.517 | 93.8% | 88.0% | 6.7% |
| **Ablation C** | Documents + Inspection Images | 76.7% | [69.3%, 82.7%] | 0.539 | 87.5% | 88.0% | 4.0% |
| **Ablation D** | Documents + Voice + Images (No Historical Matching) | 82.0% | [75.1%, 87.3%] | 0.804 | 100.0% | 88.0% | 12.0% |
| **Ablation E** | All Modalities + Historical Matching (No Rule Engine) | 44.0% | [36.3%, 52.0%] | 0.497 | 100.0% | 100.0% | 48.0% |
| **Ablation F** | Full EvidenceOS (All Modalities + Historical + Deterministic Rules) | 94.0% | [89.0%, 96.8%] | 0.913 | 100.0% | 100.0% | 0.0% |

## 4. Perceptual Hashing (`64-bit dHash`) vs `SHA-256` Duplicate Benchmark (`40 Image Pairs`)

- **SHA-256 Only**: Precision `100.0%`, Recall `25.0%`, F1 `0.400`
- **64-bit dHash + SHA-256**: Precision `100.0%`, Recall `100.0%`, F1 `1.000`

## 5. Prompt Injection Security Evaluation (`15 Adversarial Test Cases`)

- **Attack Success Rate**: `0.0%` (`0/15`)
- **Correct Rejection / Safe Gating Rate**: `100.0%`
