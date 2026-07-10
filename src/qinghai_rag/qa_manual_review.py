from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from typing import Any, Literal

from pydantic import field_validator

from qinghai_rag.schemas import FactRecord, QARecord, SourceRecord, StrictRecord

QA_TYPE_WEIGHTS = {
    "single_fact": 0.4,
    "regional_aggregation": 0.2,
    "multi_hop": 0.2,
    "comparison": 0.1,
    "unanswerable": 0.1,
}


class QAManualReviewDecision(StrictRecord):
    review_id: str
    batch_id: str
    question_id: str
    qa_sha256: str
    decision: Literal["accepted"] = "accepted"
    reviewed_at: str
    reviewer: str

    @field_validator("reviewed_at")
    @classmethod
    def valid_review_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value


def qa_sha256(item: QARecord) -> str:
    payload = {
        "question_id": item.question_id,
        "question": item.question,
        "answer": item.answer,
        "answer_type": item.answer_type,
        "evidence_fact_ids": item.evidence_fact_ids,
        "evidence_source_ids": item.evidence_source_ids,
        "required_entities": item.required_entities,
        "difficulty": item.difficulty,
        "unanswerable": item.unanswerable,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_order(item: QARecord, review_id: str) -> str:
    return hashlib.sha256(f"{review_id}:{item.question_id}".encode()).hexdigest()


def _allocate_targets(qa: list[QARecord], target: int) -> dict[str, int]:
    if target <= 0:
        raise ValueError("manual QA review target must be positive")
    if target > len(qa):
        raise ValueError(f"manual QA review target {target} exceeds QA count {len(qa)}")

    available = Counter(item.answer_type for item in qa)
    allocation = {
        answer_type: min(available[answer_type], int(target * weight))
        for answer_type, weight in QA_TYPE_WEIGHTS.items()
    }
    remaining = target - sum(allocation.values())
    order = list(QA_TYPE_WEIGHTS)
    while remaining:
        changed = False
        for answer_type in order:
            if allocation[answer_type] < available[answer_type]:
                allocation[answer_type] += 1
                remaining -= 1
                changed = True
                if not remaining:
                    break
        if not changed:
            raise ValueError("not enough QA records to allocate the review sample")
    return allocation


def select_review_sample(
    qa: list[QARecord], target: int, review_id: str
) -> list[QARecord]:
    allocation = _allocate_targets(qa, target)
    selected = []
    for answer_type in QA_TYPE_WEIGHTS:
        candidates = sorted(
            (item for item in qa if item.answer_type == answer_type),
            key=lambda item: _stable_order(item, review_id),
        )
        selected.extend(candidates[: allocation[answer_type]])
    return sorted(selected, key=lambda item: _stable_order(item, review_id))


def prepare_review_batch(
    qa: list[QARecord],
    decisions: list[QAManualReviewDecision],
    review_id: str,
    target: int,
    batch_size: int,
) -> tuple[list[QARecord], dict[str, Any]]:
    if batch_size <= 0:
        raise ValueError("batch size must be positive")
    sample = select_review_sample(qa, target, review_id)
    accepted_ids = {
        decision.question_id
        for decision in decisions
        if decision.review_id == review_id and decision.decision == "accepted"
    }
    pending = [
        item for item in sample if item.question_id not in accepted_ids and not item.manual_checked
    ]
    accepted_in_sample = sum(
        item.question_id in accepted_ids or item.manual_checked for item in sample
    )
    batch = pending[:batch_size]
    batch_number = accepted_in_sample // batch_size + 1
    return batch, {
        "review_id": review_id,
        "target": target,
        "accepted": accepted_in_sample,
        "remaining": len(pending),
        "batch_id": f"batch_{batch_number:03d}" if batch else None,
        "batch_size": len(batch),
        "sample_type_distribution": dict(Counter(item.answer_type for item in sample)),
    }


def build_batch_decisions(
    batch: list[QARecord], review_id: str, batch_id: str, reviewer: str
) -> list[QAManualReviewDecision]:
    if not reviewer.strip():
        raise ValueError("reviewer must not be empty")
    reviewed_at = date.today().isoformat()
    return [
        QAManualReviewDecision(
            review_id=review_id,
            batch_id=batch_id,
            question_id=item.question_id,
            qa_sha256=qa_sha256(item),
            reviewed_at=reviewed_at,
            reviewer=reviewer,
        )
        for item in batch
    ]


def render_review_batch(
    batch: list[QARecord], facts: list[FactRecord], sources: list[SourceRecord]
) -> str:
    fact_by_id = {fact.fact_id: fact for fact in facts}
    source_by_id = {source.source_id: source for source in sources}
    lines = []
    for index, item in enumerate(batch, start=1):
        lines.extend(
            [
                f"\n[{index}/{len(batch)}] {item.question_id} | {item.answer_type} | {item.difficulty}",
                f"问题：{item.question}",
                f"答案：{item.answer}",
            ]
        )
        if item.unanswerable:
            lines.append("证据：不可回答题；请确认当前事实表没有回答该问题所需的信息。")
            lines.append(f"涉及实体：{'、'.join(item.required_entities) or '无'}")
            continue
        lines.append("证据事实：")
        for fact_id in item.evidence_fact_ids:
            fact = fact_by_id.get(fact_id)
            if fact is None:
                lines.append(f"  - {fact_id}: [缺失]")
                continue
            lines.append(
                f"  - {fact.fact_id}: {fact.subject} — {fact.predicate} — {fact.object}"
            )
            if fact.evidence_text:
                lines.append(f"    原始证据：{' '.join(fact.evidence_text.split())}")
        lines.append("来源：")
        for source_id in item.evidence_source_ids:
            source = source_by_id.get(source_id)
            if source is None:
                lines.append(f"  - {source_id}: [缺失]")
            else:
                lines.append(f"  - {source_id}: {source.title}")
                lines.append(f"    {source.url}")
    return "\n".join(lines).lstrip()


def apply_qa_manual_review(
    qa: list[QARecord],
    decisions: list[QAManualReviewDecision],
    review_id: str,
    minimum_accepted: int,
) -> tuple[list[QARecord], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    decision_by_id: dict[str, QAManualReviewDecision] = {}
    for decision in decisions:
        if decision.review_id != review_id:
            continue
        previous = decision_by_id.get(decision.question_id)
        if previous and previous.qa_sha256 != decision.qa_sha256:
            issues.append(
                {"question_id": decision.question_id, "issue": "conflicting_review_snapshots"}
            )
        decision_by_id[decision.question_id] = decision

    qa_by_id = {item.question_id: item for item in qa}
    valid_ids = set()
    for question_id, decision in decision_by_id.items():
        item = qa_by_id.get(question_id)
        if item is None:
            issues.append({"question_id": question_id, "issue": "missing_qa_record"})
        elif qa_sha256(item) != decision.qa_sha256:
            issues.append({"question_id": question_id, "issue": "qa_snapshot_changed"})
        else:
            valid_ids.add(question_id)

    if len(valid_ids) < minimum_accepted:
        issues.append(
            {
                "issue": "accepted_below_minimum",
                "accepted": len(valid_ids),
                "minimum": minimum_accepted,
            }
        )
    if issues:
        valid_ids.clear()

    manual_before = sum(item.manual_checked for item in qa)
    newly_marked = 0
    updated = []
    for item in qa:
        if item.question_id in valid_ids:
            if not item.manual_checked:
                newly_marked += 1
            decision = decision_by_id[item.question_id]
            marker = (
                f"qa_manual_review_id={review_id}; reviewed_at={decision.reviewed_at}; "
                f"reviewer={decision.reviewer}; qa_sha256={decision.qa_sha256}"
            )
            notes = item.notes if marker in item.notes else "; ".join(filter(None, [item.notes, marker]))
            payload = item.model_dump(mode="json")
            payload.update({"manual_checked": True, "notes": notes})
            item = QARecord.model_validate(payload)
        updated.append(item)
    return updated, {
        "review_id": review_id,
        "accepted_decisions": len(decision_by_id),
        "valid_decisions": len(valid_ids),
        "new_manual_checks": newly_marked,
        "issues": issues,
        "manual_checked_before": manual_before,
        "manual_checked_after": sum(item.manual_checked for item in updated),
    }
