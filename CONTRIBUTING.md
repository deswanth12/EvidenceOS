# Contributing to EvidenceOS

Thank you for your interest in contributing to **EvidenceOS** and **VeriDock**.

## Engineering Principles

1. **Epistemological Honesty**: Every extracted or derived claim must preserve its `Provenance` (`evidence_id`, `source_type`, `location`, `extraction_method`, `confidence`, `epistemic_type`). Never allow an LLM to silently fabricate facts or compute final financial settlements.
2. **Strict Separation of AI & Deterministic Rules**: AI modules (`core/ai/`, `core/extraction/`) handle perception and structured extraction. Deterministic modules (`core/rules/`, `core/decisions/`, `core/matching/`) handle arithmetic, perceptual hashing, SLA evaluation, and final decision routing.
3. **Security First**: Treat all uploaded files as untrusted data. Sanitize filenames, verify file magic bytes, and neutralize prompt injection patterns before model invocation.

## Development Workflow

### 1. Backend Setup & Tests

```bash
python -m pip install -e ".[dev]"
python -m pytest -v
python -m ruff check .
```

### 2. Frontend Setup, Tests & Build

```bash
cd apps/web
npm install
npm run test
npm run build
```

### 3. Running the Empirical Benchmark

Before opening a pull request that modifies extraction, entity resolution, conflict detection, or rule logic, run the benchmark suite and ensure all metrics remain reproducible:

```bash
python -m evaluation.runner
```
