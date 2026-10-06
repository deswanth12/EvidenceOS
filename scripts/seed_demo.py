"""CLI utility to seed the 5 canonical VeriDock cases and print a summary table."""

from pathlib import Path

from apps.api.app.routes.cases import seed_canonical_demo_cases
from core.datasets_generator import write_synthetic_datasets_to_disk
from core.db.models import CaseModel, DecisionRecordModel, get_session_factory, init_db


def main() -> None:
    init_db()
    datasets_dir = Path("datasets/synthetic_cases")
    write_synthetic_datasets_to_disk(datasets_dir)

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        result = seed_canonical_demo_cases(db)
        print(f"Seeded {result['seeded_cases']} canonical VeriDock cases:")
        for cid in result["case_ids"]:
            case = db.query(CaseModel).filter(CaseModel.id == cid).first()
            dec = (
                db.query(DecisionRecordModel)
                .filter(DecisionRecordModel.case_id == cid)
                .order_by(DecisionRecordModel.decided_at.desc())
                .first()
            )
            outcome = dec.outcome if dec else "none"
            print(f"  - {cid:<30} | Outcome: {outcome:<24} | Title: {case.title if case else ''}")


if __name__ == "__main__":
    main()
