from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml
from pydantic import Field, field_validator, model_validator

from qinghai_rag.fact_extraction import stable_fact_id
from qinghai_rag.io_utils import sha256_bytes
from qinghai_rag.normalize import normalize_entity_name, normalize_region
from qinghai_rag.schemas import FactRecord, SourceRecord, StrictRecord
from qinghai_rag.source_registry import normalize_domain


class ReviewedCatalogRow(StrictRecord):
    sequence: int = Field(ge=1)
    project_number: str
    project_name: str
    category: str
    circulation_area: str


class ReviewedInheritorRow(StrictRecord):
    sequence: int = Field(ge=1)
    project_name: str
    person_name: str


class ReviewedCatalogBase(StrictRecord):
    review_id: str
    reviewed_at: str
    reviewer_role: str
    review_method: str
    source_id: str
    title: str
    publisher: str
    parent_page_url: str
    attachment_url: str
    attachment_sha256: str
    raw_path: str
    region: list[str]
    topic: list[str]
    batch: str
    expected_rows: int = Field(ge=1)

    @field_validator("reviewed_at")
    @classmethod
    def valid_review_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @field_validator("attachment_sha256")
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("attachment_sha256 must be a lowercase SHA-256 digest")
        return value


class ReviewedLocalCatalog(ReviewedCatalogBase):
    catalog_kind: Literal["project"] = "project"
    level: str
    publication_status: Literal["final", "proposed"] = "final"
    proposed_concept: str | None = None
    rows: list[ReviewedCatalogRow]

    @model_validator(mode="after")
    def valid_rows(self) -> "ReviewedLocalCatalog":
        if len(self.rows) != self.expected_rows:
            raise ValueError("expected_rows does not match reviewed rows")
        sequences = [row.sequence for row in self.rows]
        if sequences != list(range(1, self.expected_rows + 1)):
            raise ValueError("reviewed row sequences must be contiguous and ordered")
        if len({row.project_name for row in self.rows}) != len(self.rows):
            raise ValueError("reviewed project names must be unique")
        if len({row.project_number for row in self.rows}) != len(self.rows):
            raise ValueError("reviewed project numbers must be unique")
        if self.publication_status == "proposed" and not self.proposed_concept:
            raise ValueError("proposed catalogs require proposed_concept")
        return self


class ReviewedLocalInheritorCatalog(ReviewedCatalogBase):
    catalog_kind: Literal["inheritor"] = "inheritor"
    excluded_fields: list[str]
    rows: list[ReviewedInheritorRow]

    @model_validator(mode="after")
    def valid_rows(self) -> "ReviewedLocalInheritorCatalog":
        if len(self.rows) != self.expected_rows:
            raise ValueError("expected_rows does not match reviewed rows")
        sequences = [row.sequence for row in self.rows]
        if sequences != list(range(1, self.expected_rows + 1)):
            raise ValueError("reviewed row sequences must be contiguous and ordered")
        pairs = {(row.project_name, row.person_name) for row in self.rows}
        if len(pairs) != len(self.rows):
            raise ValueError("reviewed project-person pairs must be unique")
        return self


ReviewedCatalog = ReviewedLocalCatalog | ReviewedLocalInheritorCatalog


def load_reviewed_catalog(path: str | Path) -> ReviewedCatalog:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if payload.get("catalog_kind", "project") == "inheritor":
        return ReviewedLocalInheritorCatalog.model_validate(payload)
    return ReviewedLocalCatalog.model_validate(payload)


def verify_reviewed_attachment(review: ReviewedCatalog, path: str | Path) -> str:
    attachment = Path(path)
    if not attachment.exists():
        raise FileNotFoundError(f"Reviewed attachment is missing: {attachment}")
    actual = sha256_bytes(attachment.read_bytes())
    if actual != review.attachment_sha256:
        raise ValueError(
            f"Attachment SHA-256 mismatch: expected {review.attachment_sha256}, got {actual}"
        )
    return actual


def build_reviewed_catalog_source(review: ReviewedCatalog) -> SourceRecord:
    return SourceRecord(
        source_id=review.source_id,
        title=review.title,
        publisher=review.publisher,
        source_type="municipal_or_county_government",
        url=review.attachment_url,
        domain=normalize_domain(review.attachment_url),
        region=review.region,
        topic=review.topic,
        retrieved_at=review.reviewed_at,
        license_status="unclear",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        crawl_status="parsed",
        content_sha256=review.attachment_sha256,
        notes=(
            f"Manually reviewed official {review.catalog_kind} catalog attachment; "
            f"review_id={review.review_id}; parent_page={review.parent_page_url}; "
            "raw attachment is not released."
        ),
    )


def _reviewed_fact(
    review: ReviewedLocalCatalog,
    row: ReviewedCatalogRow,
    predicate: str,
    obj: str,
    object_type: str,
) -> FactRecord:
    subject = normalize_entity_name(row.project_name)
    normalized_object = (
        normalize_region(obj) if object_type == "REGION" else normalize_entity_name(obj)
    )
    evidence = (
        f"人工核验官方附件表格第{row.sequence}行：项目编号：{row.project_number}；"
        f"项目名称：{row.project_name}；项目类别：{row.category}；"
        f"流传地区：{row.circulation_area}；名录批次：{review.batch}"
    )
    return FactRecord(
        fact_id=stable_fact_id(subject, predicate, normalized_object, review.source_id),
        subject=subject,
        subject_type="ICH_PROJECT",
        predicate=predicate,
        object=normalized_object,
        object_type=object_type,
        evidence_source_id=review.source_id,
        evidence_url=review.attachment_url,
        evidence_text=evidence,
        extraction_method="manual_review",
        verified=True,
        confidence="high",
        manual_checked=True,
        notes=(
            f"review_id={review.review_id}; reviewed_at={review.reviewed_at}; "
            f"attachment_sha256={review.attachment_sha256}"
        ),
    )


def _reviewed_inheritor_fact(
    review: ReviewedLocalInheritorCatalog,
    row: ReviewedInheritorRow,
) -> FactRecord:
    subject = normalize_entity_name(row.project_name)
    person = normalize_entity_name(row.person_name)
    evidence = (
        f"人工核验官方附件表格第{row.sequence}行：项目名称：{row.project_name}；"
        f"代表性传承人：{row.person_name}；名录批次：{review.batch}"
    )
    return FactRecord(
        fact_id=stable_fact_id(subject, "inherited_by", person, review.source_id),
        subject=subject,
        subject_type="ICH_PROJECT",
        predicate="inherited_by",
        object=person,
        object_type="PERSON",
        evidence_source_id=review.source_id,
        evidence_url=review.attachment_url,
        evidence_text=evidence,
        extraction_method="manual_review",
        verified=True,
        confidence="high",
        manual_checked=True,
        notes=(
            f"review_id={review.review_id}; reviewed_at={review.reviewed_at}; "
            f"attachment_sha256={review.attachment_sha256}; excluded_fields="
            + ",".join(review.excluded_fields)
        ),
    )


def build_reviewed_catalog_facts(review: ReviewedCatalog) -> list[FactRecord]:
    if isinstance(review, ReviewedLocalInheritorCatalog):
        return sorted(
            (_reviewed_inheritor_fact(review, row) for row in review.rows),
            key=lambda fact: fact.fact_id,
        )
    facts = []
    for row in review.rows:
        facts.append(
            _reviewed_fact(review, row, "belongs_to_category", row.category, "CATEGORY")
        )
        if review.publication_status == "proposed":
            facts.append(
                _reviewed_fact(
                    review,
                    row,
                    "related_to_concept",
                    review.proposed_concept or "",
                    "CONCEPT",
                )
            )
        else:
            facts.extend(
                [
                    _reviewed_fact(review, row, "located_in", row.circulation_area, "REGION"),
                    _reviewed_fact(review, row, "has_level", review.level, "CONCEPT"),
                ]
            )
    return sorted(facts, key=lambda fact: fact.fact_id)


def merge_reviewed_catalog_facts(
    existing: Iterable[FactRecord], generated: Iterable[FactRecord]
) -> tuple[list[FactRecord], dict[str, Any]]:
    existing_records = list(existing)
    generated_records = list(generated)
    merged = {fact.fact_id: fact for fact in existing_records}
    semantic_owner = {
        (fact.subject, fact.predicate, fact.object): fact.fact_id for fact in existing_records
    }
    retained = 0
    skipped_semantic_duplicates = []
    for fact in generated_records:
        key = (fact.subject, fact.predicate, fact.object)
        owner = semantic_owner.get(key)
        if owner and owner != fact.fact_id:
            skipped_semantic_duplicates.append({"fact_id": fact.fact_id, "existing_fact_id": owner})
            continue
        if fact.fact_id not in merged:
            retained += 1
        merged[fact.fact_id] = fact
        semantic_owner[key] = fact.fact_id
    return sorted(merged.values(), key=lambda fact: fact.fact_id), {
        "generated_facts": len(generated_records),
        "retained_new_facts": retained,
        "skipped_semantic_duplicates": skipped_semantic_duplicates,
        "projected_fact_total": len(merged),
        "manual_checked_before": sum(fact.manual_checked for fact in existing_records),
        "manual_checked_after": sum(fact.manual_checked for fact in merged.values()),
    }
