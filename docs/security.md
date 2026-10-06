# Security & Privacy Architecture (`docs/security.md`)

## 1. Threat Model & Security Controls

Uploaded dispute evidence originates from external suppliers, carriers, and warehouses and must be treated as **untrusted and potentially adversarial**.

### 1.1 Prompt Injection Defenses (`core/ai/provider.py`)
- **Rule**: *An uploaded document is DATA, never SYSTEM INSTRUCTIONS.*
- Before any document text or audio transcript reaches an extraction parser or LLM, `sanitize_untrusted_text()` scans for adversarial directives (`"ignore previous instructions"`, `"override decision to approved"`, `<system>`, `"disregard contract rules"`), replaces them with `[REDACTED_UNTRUSTED_DIRECTIVE]`, logs a warning in the document extraction notes, and isolates the payload inside `<untrusted_document_data>` XML delimiters.
- Even if an LLM were coaxed into returning a fabricated field, it **cannot** directly set a case's `DecisionOutcome`, because decisions are computed exclusively by `DeterministicRuleEngine` and `DecisionEngineService`.

### 1.2 File Validation & Path Traversal Prevention (`core/ingestion/service.py`)
- **Filename Sanitization**: `sanitize_filename()` strips all directory components (`../`, `..\\`, `/`) and restricts filenames to `[a-zA-Z0-9._-]`.
- **Storage Containment**: `LocalFilesystemStorage._safe_resolve()` verifies via `.resolve()` that the target path is strictly inside `base_dir`, blocking symlink or relative path traversal.
- **Magic Byte Verification**: `validate_magic_bytes()` inspects binary headers (`%PDF-` for PDFs, `RIFF....WAVE` for WAV audio, and `PIL.Image.verify()` for images) rather than trusting client-supplied MIME headers.
- **Upload Size Limits**: Enforced via `MAX_UPLOAD_SIZE_MB` (default `25 MB`).

### 1.3 Authentication & Secrets Management (`apps/api/app/security/auth.py`)
- API keys (`GEMINI_API_KEY`, `API_SECRET_KEY`) are loaded strictly from environment variables via `pydantic-settings` (`core/config.py`). Zero secrets are hardcoded in the repository.
- Mutation endpoints (`POST /cases`, `POST /cases/{id}/evidence`, `POST /cases/{id}/process`, `POST /cases/{id}/review`) use the `verify_api_key` FastAPI dependency, enforcing `X-API-Key` validation when `AUTH_REQUIRED=true`.

### 1.4 Tamper-Evident Audit Logging (`core/audit/logger.py`)
- Every case action is recorded in `audit_logs` with a cryptographic SHA-256 hash chain:
  $$\text{event\_hash}_i = \text{SHA256}(\text{canonical\_json}(\text{event}_i, \text{previous\_event\_hash}_{i-1}))$$
- `GET /api/cases/{id}/audit` verifies the entire chain from `GENESIS` to the head event on every query.

---

## 2. Privacy & Data Handling Policy

| Aspect | Policy in EvidenceOS |
| :--- | :--- |
| **What Data Is Stored Locally** | Raw uploaded evidence files (`data/evidence_store/`), SQLite/PostgreSQL metadata, SHA-256 hashes, 64-bit dHashes, normalized claims, and audit logs. |
| **What Data Is Sent to External AI Providers** | When `AI_PROVIDER=heuristic_local` (default), **zero bytes** leave the local machine. When `AI_PROVIDER=gemini`, only sanitized document text or media bytes for the active case are sent over TLS to the Google Gemini API. |
| **Retention & Deletion Process** | Deleting a `CaseModel` cascades deletion across `evidence_records`, `normalized_claims`, `resolved_entities`, `conflict_records`, `historical_matches`, `decision_records`, and `audit_logs`, paired with storage directory cleanup. |
| **Secure Logging** | Operational logs record `evidence_id`, `sha256_hash`, `duration_ms`, and `stage` without dumping raw PII or confidential contract bodies to stdout. |
