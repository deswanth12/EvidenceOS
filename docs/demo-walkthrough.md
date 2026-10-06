# EvidenceOS (`VeriDock`) — 3-Minute Technical & Product Walkthrough

This walkthrough demonstrates the complete **EvidenceOS (`VeriDock`)** architecture in under 3 minutes: from heterogeneous multimodal evidence ingestion (`PDF`, `PNG`, `WAV`) to cross-modal conflict detection, perceptual duplicate fraud checking, deterministic rule evaluation, human override, and live benchmark reproduction.

---

## 1. Prerequisites (`30 seconds`)

Start the FastAPI backend and React 19 frontend workstation:

```bash
# Terminal 1: Start API Server (automatically seeds the 5 canonical cases)
uvicorn apps.api.main:app --reload --port 8000

# Terminal 2: Start Investigation Workstation UI
cd apps/web
npm run dev
```

Open **`http://localhost:5173`** in your browser.

---

## 2. Step-by-Step Investigation Walkthrough (`2 minutes`)

### Step 1: Launch the Flagship Dispute (`Case 3: Conflicting Multimodal Evidence`)
1. Click **"Launch Guided Flagship Demo (Case 3)"** in the top-right header (or select `case_03_conflicting_evidence` from the left sidebar).
2. Observe the **Case Investigation Header**:
   - **Purchase Order**: `PO-2026-1003` (`10` ordered units of `SKU-IND-100` @ `$250/unit`).
   - **System Decision Badge**: `⚠ Manual Review` (`Epistemic Status: UNCERTAINTY`).
   - **Summary**: Delivery Challan reports `8` delivered (`2` short), Voice Report claims `5` damaged boxes, and Dock Inspection Photo supports only `2` damaged boxes.

### Step 2: Inspect Original Evidence & Inline PDF Highlighting
1. In the **Submitted Evidence Artifacts** panel, click **"Inspect Claims & Provenance"** on `DC-2026-1003.pdf` (Delivery Challan).
2. In the **Evidence Inspector Drawer**:
   - Verify the **SHA-256 Content Digest** (`64` hex characters) and **Processing Method**.
   - Scroll to **Inline PDF / Source Evidence Highlighting (`page:1`)** and click the pill **`Delivered: 8 units (SKU-IND-100)`** — the exact line (`L07: ITEM | SKU: SKU-IND-100 ... | DELIVERED: 8`) highlights in amber (`← Extracted Claim Span`).
   - Click **"Open Original File"** to view the raw byte-preserved PDF directly in the browser.

### Step 3: Trace Any Claim End-to-End (`[Why?]`)
1. On the **Overview** or **Claims & [Why?]** tab, click **`[Why?]`** next to `damaged_quantity: 5 box` (`voice_report`).
2. Inspect the **End-to-End Provenance Trace Modal**:
   - **Breadcrumb Chain**: `Decision: MANUAL REVIEW REQUIRED → Rule: RULE_03_CROSS_MODAL_DAMAGE_CORROBORATION → Claim: damaged_quantity=5 → Evidence: ev_...`
   - **Inline Source Highlight**: Highlights the verbatim spoken transcript line (`"Unloading SKU-IND-100 right now, 5 boxes were crushed..."`).
   - **Downstream Rule Impact**: Shows `RULE_03_CROSS_MODAL_DAMAGE_CORROBORATION: REVIEW ⚠` because visual evidence (`2` damaged) disagrees with the voice claim (`5` damaged).

### Step 4: Inspect Side-by-Side Reused Image Fraud (`Case 4: Reused Historical Evidence`)
1. Select **`case_04_reused_historical_evidence`** in the left sidebar and open the **Conflicts** tab.
2. Under **Historical Evidence Reuse Check (`SHA-256` & `64-Bit Perceptual dHash`)**:
   - Observe the **`⚠ Potentially reused evidence`** alert (`Match: PERCEPTUAL_DHASH_NEAR_DUPLICATE • Similarity: 98.4% • Hamming Distance: 1/64`).
   - Inspect the **Side-by-Side Visual Comparison Panel** comparing the **Current Claim Image** against the **Historical Image (Prior Claim)** from `case_02_partial_damage`.

### Step 5: Adjudicate & Verify the Hash-Chained Audit Trail
1. Switch to the **Decision & Review** tab on `Case 3`.
2. Notice the clear attribution badge: **`Decision Source: Deterministic Rule Engine (Automated)`**.
3. Under **Human Adjudicator Review & Override**, enter your reviewer ID, select **`Partially Approved`**, set `Accepted Quantity = 6`, `Verified Damaged Quantity = 2`, add an audit note, and click **"Record Human Override Decision"**.
4. Open the **Audit Trail** tab:
   - Verify **`Chain Integrity: VERIFIED ✓`** and inspect the chronological (`HH:MM:SS`) hash-chained events (`GENESIS → CASE_CREATED → EVIDENCE_INGESTED → ... → HUMAN_REVIEW_OVERRIDE`).

---

## 3. Live Benchmark Verification (`30 seconds`)

1. Click **"Benchmarks (`n=150` Held-Out Suite)"** in the left navigation bar (or run `python -m scripts.run_evaluation` in the terminal).
2. Inspect the live metrics across:
   - **System D (Full EvidenceOS)**: **`94.0%` Decision Accuracy** (`141/150`, 95% Wilson CI `[89.0%, 96.8%]`), **`91.3%` Macro-F1**, **`0.0%` Confident Error Rate**.
   - **System C (Semantic AI Only — No Rule Engine)**: **`44.0%` Decision Accuracy**, **`48.0%` Confident Error Rate** (`72/150` unsafe auto-settlements).
   - **Baselines A & B (Strict Regex / Structured Normalizer)**: **`72.0%` / `78.0%` Decision Accuracy**.
