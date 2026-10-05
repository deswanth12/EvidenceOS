"""Historical Evidence Matching Service (Phase 6 / Module 9).

Detects potentially reused or duplicated evidence across cases using:
1. Cryptographic SHA-256 hash comparison for exact byte duplicates.
2. 64-bit Perceptual Difference Hash (dHash) Hamming distance for visually
   similar or re-saved/cropped/compressed images.

Important Epistemological Rule:
Never label something fraudulent solely because it is similar.
Always use neutral, verifiable language: "Potentially reused evidence detected."
"""

from typing import List

from sqlalchemy.orm import Session

from core.audit.logger import AuditService
from core.config import get_settings
from core.db.models import EvidenceRecordModel, HistoricalMatchModel
from core.schemas import HistoricalMatchWarning


def hamming_distance_hex(hash1: str, hash2: str) -> int:
    """Compute bit-level Hamming distance between two 64-bit hex dHash strings."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 64
    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    return (val1 ^ val2).bit_count()


class HistoricalMatchingService:
    """Compares current case evidence against all historical cases in the database."""

    @staticmethod
    def match_against_historical_cases(
        db: Session,
        case_id: str,
        current_records: List[EvidenceRecordModel],
    ) -> List[HistoricalMatchWarning]:
        db.query(HistoricalMatchModel).filter(HistoricalMatchModel.case_id == case_id).delete()
        db.commit()

        settings = get_settings()
        max_hamming = settings.perceptual_hash_hamming_threshold

        # Compare against prior historical cases (uploaded earlier than the current case's first evidence)
        earliest_curr_upload = min((r.uploaded_at for r in current_records), default=None)
        query = db.query(EvidenceRecordModel).filter(EvidenceRecordModel.case_id != case_id)
        if earliest_curr_upload is not None:
            query = query.filter(EvidenceRecordModel.uploaded_at < earliest_curr_upload)
        historical_records = query.all()

        warnings: List[HistoricalMatchWarning] = []

        for curr in current_records:
            for hist in historical_records:
                # 1. Exact SHA-256 cryptographic match
                if curr.sha256_hash and curr.sha256_hash == hist.sha256_hash:
                    warnings.append(
                        HistoricalMatchWarning(
                            case_id=case_id,
                            current_evidence_id=curr.id,
                            historical_case_id=hist.case_id,
                            historical_evidence_id=hist.id,
                            match_type="exact_sha256",
                            similarity_score=1.0,
                            hamming_distance=0,
                            warning_message=(
                                f"Potentially reused evidence detected: Exact SHA-256 cryptographic match "
                                f"with evidence '{hist.original_filename}' ({hist.id}) from historical case '{hist.case_id}'."
                            ),
                        )
                    )
                    continue

                # 2. Perceptual dHash match for images
                if curr.perceptual_hash and hist.perceptual_hash:
                    dist = hamming_distance_hex(curr.perceptual_hash, hist.perceptual_hash)
                    if dist <= max_hamming:
                        sim_score = round(1.0 - (dist / 64.0), 4)
                        warnings.append(
                            HistoricalMatchWarning(
                                case_id=case_id,
                                current_evidence_id=curr.id,
                                historical_case_id=hist.case_id,
                                historical_evidence_id=hist.id,
                                match_type="perceptual_dhash",
                                similarity_score=sim_score,
                                hamming_distance=dist,
                                warning_message=(
                                    f"Potentially reused evidence detected: Visual perceptual similarity "
                                    f"({sim_score * 100:.1f}%, Hamming distance {dist}/64) with image "
                                    f"'{hist.original_filename}' ({hist.id}) from historical case '{hist.case_id}'."
                                ),
                            )
                        )

        for w in warnings:
            db_w = HistoricalMatchModel(
                id=w.match_id,
                case_id=case_id,
                current_evidence_id=w.current_evidence_id,
                historical_case_id=w.historical_case_id,
                historical_evidence_id=w.historical_evidence_id,
                match_type=w.match_type,
                similarity_score=w.similarity_score,
                hamming_distance=w.hamming_distance,
                warning_message=w.warning_message,
                detected_at=w.detected_at,
            )
            db.add(db_w)

        db.commit()

        AuditService.record_event(
            db=db,
            case_id=case_id,
            event_type="HISTORICAL_MATCHING_COMPLETED",
            stage="historical_matching",
            details={
                "warnings_detected": len(warnings),
                "matches": [
                    {
                        "current_evidence_id": w.current_evidence_id,
                        "historical_case_id": w.historical_case_id,
                        "match_type": w.match_type,
                        "similarity_score": w.similarity_score,
                    }
                    for w in warnings
                ],
            },
        )
        return warnings
