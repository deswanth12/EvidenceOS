# Deterministic Rules & Decision Engine (`docs/decisions.md`)

## 1. Contract & SLA Rules (`core/rules/engine.py`)

VeriDock evaluates five explicit, deterministic rules over resolved entities, conflicts, and historical matches:

1. **`RULE_01_EVIDENCE_SUFFICIENCY`** (*Evidence Completeness & Confidence Threshold*):
   - Verifies that primary documents exist, no evidence item has `epistemic_type == UNCERTAINTY`, and `min_observed_confidence >= min_confidence_threshold` (default `0.75`).
2. **`RULE_02_DELIVERY_COMPLETENESS`** (*Purchase Order vs. Delivery Challan Match*):
   - Verifies `ordered_quantity == delivered_quantity`. Flags any short delivery.
3. **`RULE_03_CROSS_MODAL_DAMAGE_CORROBORATION`** (*Multi-Modal Physical Damage Corroboration*):
   - Requires that any positive damage claim (`> 0`) be corroborated across visual inspection (`inspection_image`) and receiving reports (`voice_report` / `delivery_challan`) without contradiction.
4. **`RULE_04_CONTRACT_SLA_THRESHOLD`** (*Contract SLA Maximum Auto-Approval Damage Ratio*):
   - Verifies that $\frac{\text{verified\_damaged\_quantity}}{\text{ordered\_quantity}} \le \text{sla\_max\_damage\_ratio}$ (default `0.25` or `25%`).
5. **`RULE_05_HISTORICAL_EVIDENCE_UNIQUENESS`** (*Cryptographic & Perceptual Historical Uniqueness Check*):
   - Verifies `len(historical_warnings) == 0` across SHA-256 exact match and 64-bit perceptual dHash Hamming distance ($\le 10$).

---

## 2. Decision State Machine (`core/decisions/engine.py`)

```mermaid
flowchart TD
    START["Evaluate Rules 01-05, Conflicts & Historical Matches"] --> E0{"Any Evidence Uploaded?"}
    E0 -- "No" --> OUT_INS["INSUFFICIENT_EVIDENCE"]
    E0 -- "Yes" --> H0{"Historical Reuse Warning?"}
    H0 -- "Yes" --> OUT_MR1["MANUAL_REVIEW_REQUIRED<br/>('Potentially reused evidence detected.')"]
    H0 -- "No" --> U0{"Low Confidence (< 0.75) or<br/>Uncertain Visual Evidence?"}
    U0 -- "Yes" --> OUT_MR2["MANUAL_REVIEW_REQUIRED<br/>(Insufficient Visual Corroboration)"]
    U0 -- "No" --> C0{"Cross-Modal Conflicts > 0?"}
    C0 -- "Yes" --> OUT_MR3["MANUAL_REVIEW_REQUIRED<br/>(Reconcile Competing Quantities)"]
    C0 -- "No" --> D0{"Delivered == Ordered AND<br/>Verified Damage == 0?"}
    D0 -- "Yes" --> OUT_APP["APPROVED<br/>(Full Invoice Settlement)"]
    D0 -- "No" --> P0{"Delivered == Ordered AND<br/>Verified Damage > 0 AND<br/>All SLA Rules Pass?"}
    P0 -- "Yes" --> OUT_PART["PARTIALLY_APPROVED<br/>(Auto-Compute Buyer Credit Note)"]
    P0 -- "No" --> OUT_MR4["MANUAL_REVIEW_REQUIRED"]
```

---

## 3. Human-in-the-Loop Override Workflow

Uncertain or conflicting cases never silently guess a payout. Instead, human procurement adjudicators can submit a review via `POST /api/cases/{case_id}/review` (or the **Human Adjudicator Review & Override** panel in the UI), recording:
- `outcome` (`approved`, `partially_approved`, `disputed`, `manual_review_required`)
- `reviewer` identifier
- `accepted_quantity` & `verified_damaged_quantity`
- `notes` (mandatory rationale appended to the SHA-256 hash-chained audit trail)
