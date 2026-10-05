"""Integration tests for the FastAPI REST API and all 5 canonical VeriDock cases."""

from fastapi.testclient import TestClient

from apps.api.app.main import app


def test_health_and_canonical_5_cases_end_to_end():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["service"] == "EvidenceOS"

        # Seed canonical 5 cases
        seed_res = client.post("/api/demo/seed")
        assert seed_res.status_code == 200
        assert seed_res.json()["seeded_cases"] == 5

        # Case 1: Clean delivery -> approved
        c1 = client.get("/api/cases/case_01_clean_delivery").json()
        assert c1["latest_decision"]["outcome"] == "approved"
        assert c1["latest_decision"]["ordered_quantity"] == 10
        assert c1["latest_decision"]["delivered_quantity"] == 10
        assert c1["latest_decision"]["verified_damaged_quantity"] == 0
        assert len(c1["conflicts"]) == 0

        # Case 2: Legitimate partial damage -> partially_approved
        c2 = client.get("/api/cases/case_02_partial_damage").json()
        assert c2["latest_decision"]["outcome"] == "partially_approved"
        assert c2["latest_decision"]["verified_damaged_quantity"] == 2
        assert c2["latest_decision"]["accepted_quantity"] == 8
        assert c2["latest_decision"]["disputed_quantity"] == 2
        assert c2["latest_decision"]["recommended_payout_adjustment_usd"] == 500.0

        # Case 3: Conflicting evidence (PO 10, Challan 8, Voice 5 damaged, Image 2 damaged) -> manual_review_required
        c3 = client.get("/api/cases/case_03_conflicting_evidence").json()
        assert c3["latest_decision"]["outcome"] == "manual_review_required"
        assert len(c3["conflicts"]) == 2
        conflict_types = {cf["conflict_type"] for cf in c3["conflicts"]}
        assert "SHORT_DELIVERY_MISMATCH" in conflict_types
        assert "DAMAGE_QUANTITY_CONTRADICTION" in conflict_types

        # Case 4: Potentially reused evidence -> manual_review_required + historical warning
        c4 = client.get("/api/cases/case_04_reused_evidence").json()
        assert c4["latest_decision"]["outcome"] == "manual_review_required"
        assert len(c4["historical_warnings"]) >= 1
        assert "Potentially reused evidence detected" in c4["historical_warnings"][0]["warning_message"]

        # Case 5: Insufficient evidence -> manual_review_required
        c5 = client.get("/api/cases/case_05_insufficient_evidence").json()
        assert c5["latest_decision"]["outcome"] == "manual_review_required"
        assert len(c5["conflicts"]) == 1
        assert c5["conflicts"][0]["conflict_type"] == "INSUFFICIENT_VISUAL_CORROBORATION"

        # Verify audit trail hash chain integrity on Case 3
        audit3 = client.get("/api/cases/case_03_conflicting_evidence/audit").json()
        assert audit3["chain_integrity"]["valid"] is True
        assert len(audit3["events"]) >= 6

        # Test human review override workflow on Case 3
        override_res = client.post(
            "/api/cases/case_03_conflicting_evidence/review",
            json={
                "outcome": "partially_approved",
                "reviewer": "senior_procurement_auditor",
                "notes": "Verified physical dock count of 8 delivered and 2 damaged after carrier sign-off.",
                "accepted_quantity": 6,
                "verified_damaged_quantity": 2,
            },
        )
        assert override_res.status_code == 200
        override_data = override_res.json()
        assert override_data["is_human_override"] is True
        assert override_data["outcome"] == "partially_approved"
        assert override_data["accepted_quantity"] == 6

        # Test empirical evaluation endpoint
        eval_res = client.get("/api/evaluation/run")
        assert eval_res.status_code == 200
        metrics = eval_res.json()["metrics"]
        assert metrics["decision_accuracy"] == 1.0
        assert metrics["extraction_accuracy"] == 1.0
        assert metrics["conflict_detection_precision"] == 1.0
        assert metrics["conflict_detection_recall"] == 1.0
