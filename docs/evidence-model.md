# Evidence & Epistemological Model (`docs/evidence-model.md`)

## 1. Core Epistemological Taxonomy

EvidenceOS enforces a strict epistemological boundary on every piece of information in the system via `EpistemologicalType` (`core/schemas.py`):

1. **`FACT`**
   - **Definition**: Directly extracted from a single piece of primary evidence with high confidence ($\ge 0.75$).
   - **Examples**:
     - Purchase Order `PO-2026-1001` line item states `ordered_quantity = 10` on `page:1`.
     - Inspection image `dock_photo_case2_2damaged.png` shows `damaged_quantity = 2` with `packaging_condition = "crushed_corner"`.

2. **`INFERENCE`**
   - **Definition**: Derived by linking or combining multiple pieces of evidence across modalities.
   - **Examples**:
     - `ResolvedEntity` linking `PO-2026-1002` (`SKU-IND-100`), `DC-2026-1002`, `dock_photo_case2_2damaged.png`, and `dock_voice_case2.wav` to the canonical entity `ITEM:SKU-IND-100`.

3. **`RULE`**
   - **Definition**: Determined by explicit, deterministic Python business logic (`DeterministicRuleEngine`).
   - **Examples**:
     - `RULE_04_CONTRACT_SLA_THRESHOLD`: Damage ratio $2 / 10 = 0.20 \le 0.25$ (`PASS`).
     - Settlement calculation: `accepted_quantity = 10 - 2 = 8`, `recommended_payout_adjustment_usd = 2 * $250.00 = $500.00`.

4. **`UNCERTAINTY`**
   - **Definition**: Insufficient, low-confidence ($< 0.75$), or contradictory evidence across modalities.
   - **Examples**:
     - Blurry/obstructed inspection photo (`confidence = 0.45`, `packaging_condition = "unclear"`).
     - Cross-modal conflict where Voice claims `5` damaged units and Image supports `2` damaged units.

---

## 2. Provenance Contract

Every `NormalizedClaim` and extraction payload carries a mandatory `Provenance` object:

```json
{
  "evidence_id": "ev_9a8b7c6d5e4f",
  "source_type": "pdf",
  "document_role": "purchase_order",
  "location": "page:1",
  "extraction_method": "evidenceos-structured-extractor-v1:document_parser",
  "timestamp": "2026-10-05T21:00:00Z",
  "confidence": 0.96,
  "epistemic_type": "FACT",
  "raw_snippet": "PURCHASE ORDER | DOCUMENT ID: PO-2026-1001 | ITEM | SKU: SKU-IND-100 | ORDERED: 10 | PRICE: 250.0"
}
```

---

## 3. Why Refusing to Invent Visual Facts Matters

In Case 5 (`case_05_insufficient_evidence`), the warehouse voice report claims 4 damaged boxes, while the uploaded dock photograph is low-clarity/obstructed (`confidence = 0.45`).
- A naive LLM wrapper often hallucinates agreement with the prompt or guesses a damage count.
- **EvidenceOS** explicitly sets `visible_quantity = None`, `supports_damage_claim = None`, and `epistemic_type = UNCERTAINTY`, triggering `INSUFFICIENT_VISUAL_CORROBORATION` and routing the case to `MANUAL_REVIEW_REQUIRED`.
