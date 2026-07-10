from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from qinghai_rag.qa_manual_review import qa_sha256
from qinghai_rag.schemas import FactRecord, QARecord

AUDIT_FIELDS = (
    "audit_id",
    "record_type",
    "record_id",
    "record_snapshot",
    "snapshot_sha256",
    "review_label",
    "error_type",
    "correction_result",
    "review_notes",
    "reviewed_at",
    "review_method",
    "source_ids",
)


def _json_snapshot(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _note_value(notes: str, key: str) -> str:
    match = re.search(rf"(?:^|; )?{re.escape(key)}=([^;]+)", notes)
    return match.group(1).strip() if match else ""


def _normalized(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record.get(field, [] if field == "source_ids" else "") for field in AUDIT_FIELDS}


def fact_audit_sample(fact: FactRecord) -> dict[str, Any]:
    snapshot = _json_snapshot(
        {
            "fact_id": fact.fact_id,
            "subject": fact.subject,
            "predicate": fact.predicate,
            "object": fact.object,
            "evidence_source_id": fact.evidence_source_id,
            "evidence_url": fact.evidence_url,
            "evidence_text": fact.evidence_text,
        }
    )
    review_id = _note_value(fact.notes, "manual_review_id") or "manual_fact_review"
    return _normalized(
        {
            "audit_id": f"audit_fact_{fact.fact_id}",
            "record_type": "fact",
            "record_id": fact.fact_id,
            "record_snapshot": snapshot,
            "snapshot_sha256": _sha256(snapshot),
            "review_label": "accepted",
            "error_type": "none",
            "correction_result": "accepted_without_change",
            "review_notes": "Reviewer checked the released relation against its exact registered evidence.",
            "reviewed_at": _note_value(fact.notes, "reviewed_at"),
            "review_method": review_id,
            "source_ids": [fact.evidence_source_id],
        }
    )


def qa_audit_sample(item: QARecord) -> dict[str, Any]:
    snapshot = _json_snapshot(
        {
            "question_id": item.question_id,
            "question": item.question,
            "answer": item.answer,
            "answer_type": item.answer_type,
            "evidence_fact_ids": item.evidence_fact_ids,
            "evidence_source_ids": item.evidence_source_ids,
            "difficulty": item.difficulty,
            "unanswerable": item.unanswerable,
        }
    )
    return _normalized(
        {
            "audit_id": f"audit_qa_{item.question_id}",
            "record_type": "qa",
            "record_id": item.question_id,
            "record_snapshot": snapshot,
            "snapshot_sha256": qa_sha256(item),
            "review_label": "accepted",
            "error_type": "none",
            "correction_result": "accepted_without_change",
            "review_notes": "Reviewer checked the question, expected answer, evidence facts, and source URLs.",
            "reviewed_at": _note_value(item.notes, "reviewed_at"),
            "review_method": _note_value(item.notes, "qa_manual_review_id")
            or "manual_qa_review",
            "source_ids": item.evidence_source_ids,
        }
    )


def load_correction_samples(path: str | Path) -> list[dict[str, Any]]:
    correction_path = Path(path)
    if not correction_path.exists():
        return []
    payload = yaml.safe_load(correction_path.read_text(encoding="utf-8")) or {}
    reviewed_at = str(payload.get("reviewed_at", ""))
    review_method = str(payload.get("review_method", ""))
    output = []
    for raw in payload.get("records", []):
        record = dict(raw)
        snapshot = str(record.get("record_snapshot", ""))
        record.update(
            {
                "snapshot_sha256": _sha256(snapshot),
                "reviewed_at": reviewed_at,
                "review_method": review_method,
            }
        )
        output.append(_normalized(record))
    return output


def build_audit_samples(
    facts: list[FactRecord],
    qa: list[QARecord],
    corrections_path: str | Path,
) -> list[dict[str, Any]]:
    samples = [fact_audit_sample(fact) for fact in facts if fact.manual_checked]
    samples.extend(qa_audit_sample(item) for item in qa if item.manual_checked)
    samples.extend(load_correction_samples(corrections_path))
    return sorted(samples, key=lambda item: item["audit_id"])
