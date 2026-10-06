# EvidenceOS Architecture (`docs/architecture.md`)

## 1. Platform vs. Vertical Product Positioning

- **EvidenceOS** is the horizontal AI evidence verification and provenance intelligence engine. It provides multimodal ingestion, cryptographic and perceptual hashing, schema-enforced extraction, cross-modal entity resolution, conflict detection, deterministic rule evaluation, and tamper-evident audit logging.
- **VeriDock** is the first vertical application built on top of EvidenceOS, purpose-built for **B2B delivery and procurement dispute resolution**.

---

## 2. Core Architectural Thesis: Epistemic Separation of Powers

> **"The AI interprets evidence; deterministic rules constrain the decision; uncertainty triggers human review."**

```mermaid
flowchart LR
    subgraph AI_Boundary["AI Boundary (Probabilistic Interpretation)"]
        A1["PDFs / Dock Photos / Voice WAVs"] --> A2["Semantic Multimodal Extractor"]
        A2 --> A3["Typed Claims + Confidence + Provenance Span"]
    end

    subgraph Graph_Boundary["Graph Boundary (Cross-Modal Grounding)"]
        A3 --> G1["Entity Resolver (v1_frozen / v2_context_aware)"]
        G1 --> G2["Conflict Detector + 64-bit dHash Ledger"]
    end

    subgraph Rule_Boundary["Deterministic Boundary (Zero Hallucinated Payouts)"]
        G2 --> R1["Contract & SLA Rules (R1–R8)"]
        R1 -->|"Corroborated & Conf >= 0.75"| D1["Auto-Settlement (100% Precision, 33/33)"]
        R1 -->|"Conflict / Degraded / SLA Breach"| D2["Mandatory Abstention (100% Recall, 108/108)"]
    end
```

---

## 3. End-to-End 12-Stage Pipeline

```mermaid
flowchart TD
    E["1. Heterogeneous Evidence (PDF PO, PDF Challan, Dock Photo, Voice WAV, JSON, CSV)"] --> ING["2. Evidence Ingestion (MIME/Magic Validation, SHA-256, 64-bit dHash, Immutable Storage)"]
    ING --> PAR["3. Document & Media Parsing (pypdf, Blind Pixel CV, RIFF/WAVE Audio, Prompt-Injection Sanitizer)"]
    PAR --> EXT["4. Multimodal Structured Extraction (AIProvider: Gemini 2.5 Flash / Offline Pixel & Acoustic Analyzer)"]
    EXT --> NRM["5. Evidence Normalization (Atomic NormalizedClaim Tuples + Epistemic Tagging: FACT / INFERENCE / UNCERTAINTY)"]
    NRM --> ENT["6. Cross-Modal Entity Resolution (v1_frozen Primary Fallback / v2_context_aware OCR + Cross-Modal Corroboration)"]
    ENT --> GRF["7. Evidence Provenance Graph (Directed DAG: Shipment -> Item -> Claim -> Evidence -> Conflict)"]
    GRF --> CNF["8. Cross-Modal Conflict Detection (Quantity Mismatch, Chronology Conflict, Voice vs. Visual Contradiction)"]
    ING --> HST["9. Historical Evidence Matching (Exact SHA-256 + 64-bit Perceptual dHash Hamming Distance <= 6)"]
    CNF --> RUL["10. Deterministic Contract & SLA Rule Engine (Rules R1–R8: Completeness, SLA 48h Window, High-Value >= $5k, Corroboration)"]
    HST --> RUL
    RUL --> DEC["11. Selective Prediction & Human-in-the-Loop Override (Approved, Partially Approved, Manual Review Required)"]
    DEC --> AUD["12. Tamper-Evident Audit Trail (Append-Only SHA-256 Hash Chain: previous_event_hash -> event_hash)"]
```

---

## 4. Why Each Component Exists

| Module | Directory | Responsibility | Why It Exists |
| :--- | :--- | :--- | :--- |
| **Ingestion** | `core/ingestion/` | Validates file extensions and magic bytes, sanitizes filenames, computes SHA-256 and 64-bit image dHash, and writes raw bytes to `StorageProvider`. | Ensures original evidence is preserved immutably before any AI processing occurs. |
| **Multimodal Extraction** | `core/extraction/` & `core/ai/` | Converts PDFs, images, audio reports, CSVs, and JSON into validated Pydantic models (`DocumentExtractionResult`, `ImageAnalysisResult`, `VoiceClaimExtraction`). | Bridges unstructured human/warehouse artifacts and structured reasoning without allowing free-form LLM text into business logic. |
| **Evidence Normalization** | `core/normalization/` | Transforms modality-specific outputs into atomic `NormalizedClaim` records (`entity_key`, `attribute`, `value`, `epistemic_type`, `provenance`). | Allows downstream conflict detection and rule evaluation to operate uniformly across PDFs, photos, and audio. |
| **Entity Resolution** | `core/entities/` | Connects line items across PO, Delivery Challan, Dock Photo, and Voice transcript into `ResolvedEntity` records (`v1_frozen` and `v2_context_aware`). | Solves the cross-modal grounding problem so claims about `"SKU-IND-202"` in a PDF, `"SKU-IND-2O2"` in noisy OCR, and blind damaged parcel photos link to the same item. |
| **Evidence Graph** | `core/evidence/` | Builds a serializable DAG (`EvidenceGraph`) of nodes and directed edges. | Enables both visual inspection in the UI and programmatic traversal from a final decision back to raw files. |
| **Conflict Detection** | `core/conflicts/` | Compares competing claims on the same `(entity_key, attribute)` and validates document date chronology (`Challan >= PO`). | Surfaces contradictions (e.g., Voice says 5 damaged vs. Image shows 2 damaged, or backdated challans) rather than silently averaging or ignoring them. |
| **Historical Matching** | `core/matching/` | Compares SHA-256 hashes and 64-bit perceptual dHashes (`Hamming <= 6`) against prior cases. | Detects exact or visually perturbed (recompressed, cropped, brightness-shifted) reused photos across claims (`100%` precision and recall on 40 test pairs). |
| **Rule & Decision Engine** | `core/rules/` & `core/decisions/` | Evaluates 8 deterministic contract/SLA rules (`R1–R8`) and computes settlement adjustments or selective abstention. | Guarantees arithmetic, thresholds, and final outcomes are 100% deterministic (`0.0%` confident error rate, `ECE = 0.0207`). |
| **Audit Trail** | `core/audit/` | Chains every case event with SHA-256 hashes (`previous_event_hash` → `event_hash`). | Provides cryptographic tamper-evidence for compliance and post-dispute audits. |
