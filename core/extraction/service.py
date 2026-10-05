"""Multimodal Structured Extraction Service (Phase 3 / Modules 2, 3, 4).

Orchestrates extraction from:
- PDF documents (using pypdf text extraction + AIProvider structured parser)
- JSON / CSV / Manual text documents
- Product/delivery inspection images
- Warehouse/driver voice reports
"""

import csv
import io
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pypdf import PdfReader
from sqlalchemy.orm import Session

from core.ai.provider import AIProvider, compute_deterministic_embedding, get_ai_provider
from core.audit.logger import AuditService
from core.db.models import EvidenceRecordModel
from core.schemas import DocumentRole, EvidenceModality
from core.storage.provider import StorageProvider, get_storage_provider


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text across all pages of a PDF file using pypdf."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []
    for idx, page in enumerate(reader.pages):
        txt = page.extract_text() or ""
        pages_text.append(f"--- PAGE {idx + 1} ---\n{txt}")
    return "\n".join(pages_text)


def convert_csv_to_structured_text(csv_bytes: bytes) -> str:
    text = csv_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    lines = []
    for row in reader:
        sku = row.get("sku") or row.get("SKU") or "SKU-IND-100"
        name = row.get("name") or row.get("item") or "Industrial Component"
        ordered = row.get("ordered_quantity") or row.get("ordered") or ""
        delivered = row.get("delivered_quantity") or row.get("delivered") or ""
        damaged = row.get("damaged_quantity") or row.get("damaged") or "0"
        price = row.get("unit_price") or row.get("price") or "100.0"
        part = f"ITEM | SKU: {sku} | NAME: {name}"
        if ordered:
            part += f" | ORDERED: {ordered}"
        if delivered:
            part += f" | DELIVERED: {delivered}"
        part += f" | DAMAGED: {damaged} | PRICE: {price}"
        lines.append(part)
    return "\n".join(lines) if lines else text


class MultimodalExtractionService:
    """Extracts typed, provenance-backed payloads from ingested evidence records."""

    def __init__(
        self,
        ai_provider: Optional[AIProvider] = None,
        storage: Optional[StorageProvider] = None,
    ) -> None:
        self.ai = ai_provider or get_ai_provider()
        self.storage = storage or get_storage_provider()

    def extract_evidence_record(
        self,
        db: Session,
        record: EvidenceRecordModel,
    ) -> Dict[str, Any]:
        start_ts = time.perf_counter()
        raw_bytes = self.storage.read(record.storage_key)
        modality = EvidenceModality(record.modality)
        role = DocumentRole(record.document_role)

        payload_dict: Dict[str, Any] = {}
        summary_text_for_embedding = ""

        if modality == EvidenceModality.PDF:
            raw_text = extract_text_from_pdf_bytes(raw_bytes)
            doc_res = self.ai.extract_document(
                evidence_id=record.id,
                raw_text=raw_text,
                hint_role=role,
                modality=modality,
            )
            record.document_role = doc_res.document_type.value
            payload_dict = doc_res.model_dump(mode="json")
            summary_text_for_embedding = f"{doc_res.document_type.value} {doc_res.document_id} {raw_text}"

        elif modality == EvidenceModality.JSON:
            parsed_json = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(parsed_json, dict) and "items" in parsed_json:
                # Format into canonical text for unified validation
                lines = [
                    f"DOCUMENT ID: {parsed_json.get('document_id', 'DOC-JSON')}",
                    f"SUPPLIER: {parsed_json.get('supplier', 'Apex Industrial Components Ltd.')}",
                    f"BUYER: {parsed_json.get('buyer', 'Vertex Logistics & Manufacturing Corp.')}",
                ]
                for it in parsed_json.get("items", []):
                    part = f"ITEM | SKU: {it.get('sku', 'SKU-IND-100')} | NAME: {it.get('name', 'Item')}"
                    if it.get("ordered_quantity") is not None:
                        part += f" | ORDERED: {it['ordered_quantity']}"
                    if it.get("delivered_quantity") is not None:
                        part += f" | DELIVERED: {it['delivered_quantity']}"
                    if it.get("damaged_quantity") is not None:
                        part += f" | DAMAGED: {it['damaged_quantity']}"
                    if it.get("unit_price") is not None:
                        part += f" | PRICE: {it['unit_price']}"
                    lines.append(part)
                raw_text = "\n".join(lines)
            else:
                raw_text = json.dumps(parsed_json)

            doc_res = self.ai.extract_document(
                evidence_id=record.id,
                raw_text=raw_text,
                hint_role=role,
                modality=modality,
            )
            record.document_role = doc_res.document_type.value
            payload_dict = doc_res.model_dump(mode="json")
            summary_text_for_embedding = raw_text

        elif modality == EvidenceModality.CSV:
            raw_text = convert_csv_to_structured_text(raw_bytes)
            doc_res = self.ai.extract_document(
                evidence_id=record.id,
                raw_text=raw_text,
                hint_role=role,
                modality=modality,
            )
            record.document_role = doc_res.document_type.value
            payload_dict = doc_res.model_dump(mode="json")
            summary_text_for_embedding = raw_text

        elif modality == EvidenceModality.IMAGE:
            img_res = self.ai.analyze_image(
                evidence_id=record.id,
                image_bytes=raw_bytes,
                filename=record.original_filename,
            )
            record.document_role = DocumentRole.INSPECTION_IMAGE.value
            payload_dict = img_res.model_dump(mode="json")
            summary_text_for_embedding = (
                f"image {img_res.detected_sku or ''} {img_res.packaging_condition} {img_res.visual_summary}"
            )

        elif modality in (EvidenceModality.AUDIO, EvidenceModality.VIDEO):
            voice_res = self.ai.analyze_voice(
                evidence_id=record.id,
                audio_or_transcript_bytes=raw_bytes,
                filename=record.original_filename,
                modality=modality,
            )
            record.document_role = DocumentRole.VOICE_REPORT.value
            payload_dict = voice_res.model_dump(mode="json")
            summary_text_for_embedding = f"voice {voice_res.claim_type} {voice_res.transcript}"

        else:
            # Manual text note or transcript
            raw_text = raw_bytes.decode("utf-8", errors="ignore")
            if role == DocumentRole.VOICE_REPORT or "unload" in raw_text.lower() or "box" in raw_text.lower():
                voice_res = self.ai.analyze_voice(
                    evidence_id=record.id,
                    audio_or_transcript_bytes=raw_bytes,
                    filename=record.original_filename,
                    modality=modality,
                )
                record.document_role = DocumentRole.VOICE_REPORT.value
                payload_dict = voice_res.model_dump(mode="json")
                summary_text_for_embedding = voice_res.transcript
            else:
                doc_res = self.ai.extract_document(
                    evidence_id=record.id,
                    raw_text=raw_text,
                    hint_role=role,
                    modality=modality,
                )
                record.document_role = doc_res.document_type.value
                payload_dict = doc_res.model_dump(mode="json")
                summary_text_for_embedding = raw_text

        duration_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
        record.extracted_payload = payload_dict
        record.embedding_vector = compute_deterministic_embedding(summary_text_for_embedding)
        record.extraction_metadata = {
            "provider": self.ai.provider_name,
            "duration_ms": duration_ms,
            "modality": modality.value,
            "resolved_role": record.document_role,
        }
        record.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)

        AuditService.record_event(
            db=db,
            case_id=record.case_id,
            event_type="EVIDENCE_EXTRACTED",
            stage="extraction",
            duration_ms=duration_ms,
            model_used=self.ai.provider_name,
            details={
                "evidence_id": record.id,
                "modality": modality.value,
                "document_role": record.document_role,
                "confidence": payload_dict.get("provenance", {}).get("confidence", 1.0),
                "epistemic_type": payload_dict.get("provenance", {}).get("epistemic_type", "FACT"),
            },
        )
        return payload_dict
