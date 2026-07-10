from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from qinghai_rag.catalog_verification import normalize_catalog_value
from qinghai_rag.fact_extraction import stable_fact_id
from qinghai_rag.normalize import normalize_entity_name
from qinghai_rag.schemas import FactRecord, SourceCandidateRecord

VERIFICATION_NOTE = (
    "Deterministically verified by exact agreement between the official inheritor "
    "catalog and detail-page structured fields; biography prose was not released or used."
)


def _fact(
    subject: str,
    subject_type: str,
    predicate: str,
    obj: str,
    object_type: str,
    candidate: SourceCandidateRecord,
    evidence: str,
) -> FactRecord:
    subject = normalize_entity_name(subject)
    obj = normalize_entity_name(obj)
    return FactRecord(
        fact_id=stable_fact_id(subject, predicate, obj, candidate.source_id),
        subject=subject,
        subject_type=subject_type,
        predicate=predicate,
        object=obj,
        object_type=object_type,
        evidence_source_id=candidate.source_id,
        evidence_url=candidate.url,
        evidence_text=evidence[:300],
        extraction_method="rule",
        verified=True,
        confidence="high",
        manual_checked=False,
        notes=VERIFICATION_NOTE,
    )


def build_inheritor_facts(
    candidates: Iterable[SourceCandidateRecord],
    documents: Iterable[dict[str, Any]],
) -> tuple[list[FactRecord], dict[str, Any]]:
    document_by_source = {item["source_id"]: item for item in documents}
    facts: list[FactRecord] = []
    issues: list[dict[str, Any]] = []
    checked_sources = 0
    eligible_sources = 0
    skipped_empty_ethnic_group = 0

    for candidate in candidates:
        if candidate.discovery_method != "ihchina_inheritor_catalog":
            continue
        checked_sources += 1
        metadata = candidate.catalog_metadata
        document = document_by_source.get(candidate.source_id)
        reasons: list[str] = []
        required = ("person", "project", "category", "applicant", "project_number")
        for field in required:
            if not metadata.get(field):
                reasons.append(f"missing_{field}")
        if document is None:
            reasons.append("missing_document")
        else:
            page_text = normalize_catalog_value(str(document.get("text") or ""))
            page_title = str(document.get("title") or "").split(" - ", maxsplit=1)[0]
            if normalize_catalog_value(metadata.get("person", "")) != normalize_catalog_value(
                page_title
            ):
                reasons.append("person_title_mismatch")
            for field in ("person", "project", "category", "applicant"):
                value = metadata.get(field, "")
                if value and normalize_catalog_value(value) not in page_text:
                    reasons.append(f"page_missing_{field}")
            ethnic_group = metadata.get("ethnic_group", "")
            if ethnic_group and normalize_catalog_value(ethnic_group) not in page_text:
                reasons.append("page_missing_ethnic_group")
        if reasons:
            issues.append({"source_id": candidate.source_id, "reasons": sorted(set(reasons))})
            continue

        eligible_sources += 1
        person = metadata["person"]
        project = metadata["project"]
        category = metadata["category"]
        applicant = metadata["applicant"]
        ethnic_group = metadata.get("ethnic_group", "")
        evidence = "；".join(
            value
            for value in [
                f"姓名：{person}",
                f"民族：{ethnic_group}" if ethnic_group else "",
                f"类别：{category}",
                f"项目编号：{metadata['project_number']}",
                f"项目名称：{project}",
                f"申报地区或单位：{applicant}",
            ]
            if value
        )
        facts.extend(
            [
                _fact(
                    project,
                    "ICH_PROJECT",
                    "inherited_by",
                    person,
                    "PERSON",
                    candidate,
                    evidence,
                ),
                _fact(
                    project,
                    "ICH_PROJECT",
                    "belongs_to_category",
                    category,
                    "CATEGORY",
                    candidate,
                    evidence,
                ),
                _fact(
                    project,
                    "ICH_PROJECT",
                    "declared_by",
                    applicant,
                    "ORGANIZATION",
                    candidate,
                    evidence,
                ),
                _fact(
                    project,
                    "ICH_PROJECT",
                    "has_level",
                    "国家级",
                    "CONCEPT",
                    candidate,
                    evidence,
                ),
            ]
        )
        if ethnic_group:
            facts.append(
                _fact(
                    person,
                    "PERSON",
                    "associated_with_ethnic_group",
                    ethnic_group,
                    "ETHNIC_GROUP",
                    candidate,
                    evidence,
                )
            )
        else:
            skipped_empty_ethnic_group += 1

    deduplicated = {fact.fact_id: fact for fact in facts}
    records = list(deduplicated.values())
    return records, {
        "checked_sources": checked_sources,
        "eligible_sources": eligible_sources,
        "issues": issues,
        "generated_facts": len(records),
        "relation_distribution": dict(Counter(fact.predicate for fact in records)),
        "skipped_empty_ethnic_group": skipped_empty_ethnic_group,
    }


def merge_inheritor_facts(
    existing: Iterable[FactRecord], generated: Iterable[FactRecord]
) -> tuple[list[FactRecord], int]:
    preserved = [
        fact
        for fact in existing
        if not fact.evidence_source_id.startswith("src_ihchina_inheritor_")
        or fact.manual_checked
    ]
    merged = {fact.fact_id: fact for fact in preserved}
    semantic_keys = {(fact.subject, fact.predicate, fact.object) for fact in preserved}
    retained_generated = 0
    for fact in sorted(generated, key=lambda item: item.fact_id):
        key = (fact.subject, fact.predicate, fact.object)
        if key in semantic_keys:
            continue
        merged[fact.fact_id] = fact
        semantic_keys.add(key)
        retained_generated += 1
    return list(merged.values()), retained_generated
