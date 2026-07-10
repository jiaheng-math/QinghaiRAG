from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

from qinghai_rag.fact_extraction import RELATION_EVIDENCE_LABELS
from qinghai_rag.schemas import FactRecord

ADJACENT_PERSONAL_FIELD = re.compile(
    r"(?:性别|出生日期|出生年月|出生时间|详细地址|地址|联系电话|电话号码|身份证号?)\s*[:：]"
)

SUBJECT_LABELS = {
    "ICH_PROJECT": "项目名称",
    "MUSEUM_OBJECT": "文物名称",
    "PERSON": "姓名",
}


def contains_adjacent_personal_field(evidence_text: str | None) -> bool:
    return bool(evidence_text and ADJACENT_PERSONAL_FIELD.search(evidence_text))


def minimal_fact_evidence(fact: FactRecord) -> str:
    subject_label = SUBJECT_LABELS.get(fact.subject_type, "主体")
    relation_label = RELATION_EVIDENCE_LABELS[fact.predicate]
    return f"{subject_label}：{fact.subject}；{relation_label}：{fact.object}"


def minimize_fact_evidence(
    facts: Iterable[FactRecord],
) -> tuple[list[FactRecord], dict[str, Any]]:
    updated: list[FactRecord] = []
    changed_ids: list[str] = []
    predicates: Counter[str] = Counter()

    for fact in facts:
        if not contains_adjacent_personal_field(fact.evidence_text):
            updated.append(fact)
            continue
        replacement = minimal_fact_evidence(fact)
        note = "Evidence minimized to relation-specific fields only."
        notes = fact.notes.rstrip()
        if note not in notes:
            notes = f"{notes} {note}".strip()
        updated.append(fact.model_copy(update={"evidence_text": replacement, "notes": notes}))
        changed_ids.append(fact.fact_id)
        predicates[fact.predicate] += 1

    remaining = sum(
        contains_adjacent_personal_field(fact.evidence_text) for fact in updated
    )
    report = {
        "facts_checked": len(updated),
        "facts_updated": len(changed_ids),
        "predicate_distribution": dict(sorted(predicates.items())),
        "remaining_personal_field_excerpts": remaining,
        "sample_updated_fact_ids": changed_ids[:10],
    }
    return updated, report
