# AI vs. Deterministic Pipeline (`docs/ai-pipeline.md`)

## 1. Strict Separation of Concerns

EvidenceOS separates **probabilistic AI perception** from **deterministic business verification**:

| Task Category | Handled By | Implementation | Why |
| :--- | :--- | :--- | :--- |
| **Document Parsing & Field Extraction** | AI / Structured Parser | `core/extraction/service.py` + `core/ai/provider.py` | Converts unstructured/semi-structured PDFs, CSVs, and JSON into `DocumentExtractionResult`. |
| **Visual Damage & Label Observation** | Vision Model / Inspector | `AIProvider.analyze_image()` | Identifies packaging condition, visible SKU labels, and damage counts from dock photos. |
| **Speech-to-Claim Extraction** | Audio / Transcript Parser | `AIProvider.analyze_voice()` | Extracts structured claim tuples (`claim_type`, `claimed_quantity`, `event_stage`) from audio. |
| **Semantic Entity Embeddings** | 64-D L2-Normalized Vector | `compute_deterministic_embedding()` | Enables cross-modal cosine similarity linking in PostgreSQL (`pgvector`) or SQLite. |
| **Cryptographic Duplicate Detection** | Deterministic SHA-256 | `compute_sha256()` | Exact byte-for-byte duplicate identification. |
| **Perceptual Image Similarity** | Deterministic 64-bit dHash | `compute_image_dhash()` + `hamming_distance_hex()` | Detects re-compressed or slightly altered duplicate photos without black-box embeddings. |
| **Arithmetic & Settlement Math** | Deterministic Python | `DeterministicRuleEngine` | Computes `accepted_quantity`, `disputed_quantity`, and `recommended_payout_adjustment_usd`. |
| **Contract & SLA Evaluation** | Deterministic Python | `DeterministicRuleEngine.evaluate_rules()` | Evaluates `RULE_01` through `RULE_05` with explicit input/output traces. |
| **Final Decision State Machine** | Deterministic Python | `DecisionEngineService.compute_decision()` | Maps rule traces, conflicts, and historical warnings to `DecisionOutcome`. |

---

## 2. Swappable AI Provider Architecture

`core/ai/provider.py` defines the abstract `AIProvider` interface with two built-in implementations:

1. **`HeuristicLocalAIProvider` (`AI_PROVIDER=heuristic_local`)**:
   - Inspects real PDF text streams (`pypdf`), PNG image statistics and embedded inspection metadata (`Pillow`), and RIFF/WAVE audio chunks (`wave`).
   - Runs 100% offline in `< 200 ms` per case with `$0.00` API cost, guaranteeing reproducible CI tests and instant local evaluation.
2. **`GeminiAIProvider` (`AI_PROVIDER=gemini`)**:
   - Uses the official `google-genai` SDK (`gemini-2.5-flash` by default) with `temperature=0.0` and `response_mime_type="application/json"`.
   - Wraps untrusted document content inside `<untrusted_document_data>` XML tags after stripping prompt injection patterns, and validates all outputs through Pydantic models.
