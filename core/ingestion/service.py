"""Evidence Ingestion Service (Phase 2 / Module 1).

Responsibilities:
- Accept files (PDF, Images, Audio, Video, JSON, CSV, Manual text)
- Validate file size limits and MIME / magic byte signatures
- Sanitize filenames against path traversal and control characters
- Generate unique evidence ID (`ev_<hex>`)
- Calculate cryptographic SHA-256 hash
- Calculate 64-bit perceptual difference hash (dHash) for images
- Preserve immutable original evidence in StorageProvider
- Record ingestion event in tamper-evident AuditService
"""

import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image
from sqlalchemy.orm import Session

from core.audit.logger import AuditService
from core.config import get_settings
from core.db.models import CaseModel, EvidenceRecordModel
from core.schemas import DocumentRole, EvidenceModality, new_id
from core.storage.provider import StorageProvider, get_storage_provider

ALLOWED_EXTENSIONS = {
    ".pdf": (EvidenceModality.PDF, "application/pdf"),
    ".png": (EvidenceModality.IMAGE, "image/png"),
    ".jpg": (EvidenceModality.IMAGE, "image/jpeg"),
    ".jpeg": (EvidenceModality.IMAGE, "image/jpeg"),
    ".webp": (EvidenceModality.IMAGE, "image/webp"),
    ".wav": (EvidenceModality.AUDIO, "audio/wav"),
    ".mp3": (EvidenceModality.AUDIO, "audio/mpeg"),
    ".m4a": (EvidenceModality.AUDIO, "audio/mp4"),
    ".mp4": (EvidenceModality.VIDEO, "video/mp4"),
    ".json": (EvidenceModality.JSON, "application/json"),
    ".csv": (EvidenceModality.CSV, "text/csv"),
    ".txt": (EvidenceModality.MANUAL, "text/plain"),
}

SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._-]")


class IngestionValidationError(ValueError):
    """Raised when an uploaded file fails security, size, or MIME validation."""


def sanitize_filename(filename: str) -> str:
    """Strip directory paths and replace unsafe characters."""
    if not filename or not filename.strip():
        raise IngestionValidationError("Filename cannot be empty.")
    # Prevent path traversal by taking only the final name component
    base = Path(filename.replace("\\", "/")).name
    cleaned = SAFE_FILENAME_RE.sub("_", base).strip("._")
    if not cleaned:
        cleaned = "uploaded_evidence"
    ext = Path(base).suffix.lower()
    if ext and not cleaned.lower().endswith(ext):
        cleaned = f"{cleaned}{ext}"
    return cleaned[:180]


def validate_magic_bytes(content: bytes, modality: EvidenceModality, ext: str) -> None:
    """Verify file magic headers match claimed extension where applicable."""
    if len(content) == 0:
        raise IngestionValidationError("Uploaded evidence file is empty (0 bytes).")

    if modality == EvidenceModality.PDF:
        if not content.startswith(b"%PDF-"):
            raise IngestionValidationError("Invalid PDF signature: file does not start with %PDF- header.")
    elif modality == EvidenceModality.IMAGE:
        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
        except Exception as exc:
            raise IngestionValidationError(f"Invalid or corrupted image file: {exc}") from exc
    elif modality == EvidenceModality.AUDIO and ext == ".wav":
        if not (content.startswith(b"RIFF") and content[8:12] == b"WAVE"):
            raise IngestionValidationError("Invalid WAV audio signature: missing RIFF/WAVE header.")


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def compute_image_dhash(content: bytes, hash_size: int = 8) -> Optional[str]:
    """Compute a 64-bit difference hash (dHash) for visual similarity comparison.

    Resizes grayscale image to (hash_size + 1, hash_size) and compares adjacent
    horizontal pixel intensities, yielding a 16-character hex string.
    """
    try:
        with Image.open(io.BytesIO(content)) as img:
            gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = list(gray.getdata())
            bits = 0
            for row in range(hash_size):
                row_offset = row * (hash_size + 1)
                for col in range(hash_size):
                    left_pixel = pixels[row_offset + col]
                    right_pixel = pixels[row_offset + col + 1]
                    bits = (bits << 1) | (1 if left_pixel > right_pixel else 0)
            return f"{bits:016x}"
    except Exception:
        return None


def infer_document_role(filename: str, modality: EvidenceModality, explicit_role: Optional[str] = None) -> DocumentRole:
    """Infer document role from explicit hint or filename conventions."""
    if explicit_role:
        try:
            return DocumentRole(explicit_role.lower())
        except ValueError:
            pass

    lower = filename.lower()
    if modality == EvidenceModality.IMAGE:
        return DocumentRole.INSPECTION_IMAGE
    if modality == EvidenceModality.AUDIO:
        return DocumentRole.VOICE_REPORT
    if any(k in lower for k in ["po", "purchase_order", "purchase-order"]):
        return DocumentRole.PURCHASE_ORDER
    if any(k in lower for k in ["challan", "delivery_note", "dc_", "packing_slip", "pod"]):
        return DocumentRole.DELIVERY_CHALLAN
    if any(k in lower for k in ["inv", "invoice"]):
        return DocumentRole.INVOICE
    if any(k in lower for k in ["voice", "audio", "transcript"]):
        return DocumentRole.VOICE_REPORT
    if any(k in lower for k in ["inspect", "report"]):
        return DocumentRole.INSPECTION_REPORT
    return DocumentRole.UNKNOWN


def identify_modality_and_mime(filename: str, declared_mime: Optional[str] = None) -> Tuple[EvidenceModality, str, str]:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestionValidationError(
            f"Unsupported file extension '{ext}'. Supported extensions: {', '.join(sorted(ALLOWED_EXTENSIONS.keys()))}"
        )
    modality, canonical_mime = ALLOWED_EXTENSIONS[ext]
    return modality, canonical_mime, ext


class EvidenceIngestionService:
    """Handles secure ingestion, validation, hashing, and storage of raw evidence."""

    def __init__(self, storage: Optional[StorageProvider] = None) -> None:
        self.storage = storage or get_storage_provider()
        self.settings = get_settings()

    def ingest_file(
        self,
        db: Session,
        case_id: str,
        filename: str,
        content: bytes,
        document_role: Optional[str] = None,
        declared_mime: Optional[str] = None,
        actor: str = "user",
    ) -> EvidenceRecordModel:
        case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
        if not case:
            raise ValueError(f"Case '{case_id}' does not exist.")

        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise IngestionValidationError(
                f"File size ({len(content)} bytes) exceeds maximum allowed limit ({max_bytes} bytes)."
            )

        safe_name = sanitize_filename(filename)
        modality, canonical_mime, ext = identify_modality_and_mime(safe_name, declared_mime)
        validate_magic_bytes(content, modality, ext)

        role = infer_document_role(safe_name, modality, document_role)
        evidence_id = new_id("ev")
        sha256_hash = compute_sha256(content)
        dhash = compute_image_dhash(content) if modality == EvidenceModality.IMAGE else None

        storage_key = self.storage.save(
            case_id=case_id,
            evidence_id=evidence_id,
            safe_filename=safe_name,
            content=content,
        )

        record = EvidenceRecordModel(
            id=evidence_id,
            case_id=case_id,
            original_filename=filename,
            safe_filename=safe_name,
            storage_key=storage_key,
            mime_type=canonical_mime,
            modality=modality.value,
            document_role=role.value,
            file_size_bytes=len(content),
            sha256_hash=sha256_hash,
            perceptual_hash=dhash,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(record)

        if case.status == "created":
            case.status = "evidence_uploaded"
        checklist = dict(case.pipeline_Checklist or {})
        checklist["evidence_received"] = True
        case.pipeline_Checklist = checklist

        db.commit()
        db.refresh(record)

        AuditService.record_event(
            db=db,
            case_id=case_id,
            event_type="EVIDENCE_INGESTED",
            stage="ingestion",
            actor=actor,
            details={
                "evidence_id": evidence_id,
                "safe_filename": safe_name,
                "modality": modality.value,
                "document_role": role.value,
                "file_size_bytes": len(content),
                "sha256_hash": sha256_hash,
                "perceptual_hash": dhash,
            },
        )
        return record
