from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator

from qinghai_rag.schemas import FactRecord, SourceRecord, StrictRecord


class MuseumManualReviewRow(StrictRecord):
    source_id: str
    exhibit_id: int = Field(ge=1)
    name: str
    category: str
    period: str
    museum: str
    material: str


class MuseumManualReview(StrictRecord):
    review_id: str
    reviewed_at: str
    reviewer_role: str
    review_method: str
    expected_sources: int = Field(ge=1)
    expected_facts: int = Field(ge=1)
    rows: list[MuseumManualReviewRow]

    @field_validator("reviewed_at")
    @classmethod
    def valid_review_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def valid_rows(self) -> "MuseumManualReview":
        if len(self.rows) != self.expected_sources:
            raise ValueError("expected_sources does not match reviewed rows")
        if self.expected_facts != self.expected_sources * 4:
            raise ValueError("museum review requires exactly four facts per source")
        source_ids = [row.source_id for row in self.rows]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("reviewed source IDs must be unique")
        for row in self.rows:
            expected_source_id = f"src_tibetan_museum_exhibit_{row.exhibit_id}"
            if row.source_id != expected_source_id:
                raise ValueError(
                    f"source_id and exhibit_id disagree: {row.source_id} != {expected_source_id}"
                )
        return self


def load_museum_manual_review(path: str | Path) -> MuseumManualReview:
    with Path(path).open("r", encoding="utf-8") as handle:
        return MuseumManualReview.model_validate(yaml.safe_load(handle))


def mark_museum_manual_review(
    facts: list[FactRecord],
    sources: list[SourceRecord],
    review: MuseumManualReview,
) -> tuple[list[FactRecord], dict[str, Any]]:
    source_by_id = {source.source_id: source for source in sources}
    facts_by_source: dict[str, list[FactRecord]] = {}
    for fact in facts:
        facts_by_source.setdefault(fact.evidence_source_id, []).append(fact)

    issues = []
    matched_fact_ids = set()
    source_hashes = {}
    for row in review.rows:
        source = source_by_id.get(row.source_id)
        if source is None:
            issues.append({"source_id": row.source_id, "issue": "missing_registry_source"})
            continue
        if source.crawl_status.value != "parsed":
            issues.append(
                {
                    "source_id": row.source_id,
                    "issue": "source_not_parsed",
                    "actual": source.crawl_status.value,
                }
            )
        if len(source.content_sha256) != 64:
            issues.append({"source_id": row.source_id, "issue": "missing_content_sha256"})
        source_hashes[row.source_id] = source.content_sha256

        selected = facts_by_source.get(row.source_id, [])
        expected_relations = {
            "belongs_to_category": row.category,
            "created_in_period": row.period,
            "held_by": row.museum,
            "made_of": row.material,
        }
        actual_relations = {
            fact.predicate: fact.object for fact in selected if fact.subject_type == "MUSEUM_OBJECT"
        }
        if len(selected) != 4 or actual_relations != expected_relations:
            issues.append(
                {
                    "source_id": row.source_id,
                    "issue": "fact_set_mismatch",
                    "expected": expected_relations,
                    "actual": actual_relations,
                }
            )
            continue
        for fact in selected:
            if fact.subject != row.name:
                issues.append(
                    {
                        "source_id": row.source_id,
                        "issue": "subject_mismatch",
                        "expected": row.name,
                        "actual": fact.subject,
                    }
                )
            if not fact.verified or fact.confidence != "high":
                issues.append(
                    {
                        "source_id": row.source_id,
                        "issue": "fact_not_high_confidence_verified",
                        "fact_id": fact.fact_id,
                    }
                )
            matched_fact_ids.add(fact.fact_id)

    if issues:
        matched_fact_ids.clear()
    manual_before = sum(fact.manual_checked for fact in facts)
    newly_marked = 0
    updated = []
    for fact in facts:
        if fact.fact_id in matched_fact_ids:
            if not fact.manual_checked:
                newly_marked += 1
            marker = (
                f"manual_review_id={review.review_id}; reviewed_at={review.reviewed_at}; "
                f"source_content_sha256={source_hashes[fact.evidence_source_id]}"
            )
            notes = (
                fact.notes
                if marker in fact.notes
                else "; ".join(filter(None, [fact.notes, marker]))
            )
            payload = fact.model_dump(mode="json")
            payload.update({"manual_checked": True, "notes": notes})
            fact = FactRecord.model_validate(payload)
        updated.append(fact)
    return updated, {
        "review_id": review.review_id,
        "reviewed_sources": len(review.rows),
        "matched_facts": len(matched_fact_ids),
        "new_manual_checks": newly_marked,
        "issues": issues,
        "manual_checked_before": manual_before,
        "manual_checked_after": sum(fact.manual_checked for fact in updated),
    }
