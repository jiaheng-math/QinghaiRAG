from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from qinghai_rag.fact_extraction import stable_fact_id
from qinghai_rag.io_utils import sha256_bytes
from qinghai_rag.normalize import normalize_entity_name
from qinghai_rag.schemas import FactRecord, SourceCandidateRecord, SourceRecord
from qinghai_rag.tibetan_museum_collection import parse_tibetan_museum_detail


def _museum_fact(
    *,
    subject: str,
    predicate: str,
    obj: str,
    object_type: str,
    source: SourceRecord,
    evidence: str,
) -> FactRecord:
    normalized_object = normalize_entity_name(obj)
    return FactRecord(
        fact_id=stable_fact_id(subject, predicate, normalized_object, source.source_id),
        subject=subject,
        subject_type="MUSEUM_OBJECT",
        predicate=predicate,
        object=normalized_object,
        object_type=object_type,
        evidence_source_id=source.source_id,
        evidence_url=source.url,
        evidence_text=evidence,
        extraction_method="rule",
        verified=True,
        confidence="high",
        manual_checked=False,
        notes=(
            "Deterministically verified by exact agreement between official list metadata, "
            "detail API fields, and the stored response hash; not manually reviewed."
        ),
    )


def build_tibetan_museum_facts(
    candidates: list[SourceCandidateRecord],
    sources: list[SourceRecord],
    raw_directory: str | Path,
) -> tuple[list[FactRecord], dict[str, Any]]:
    source_by_id = {source.source_id: source for source in sources}
    title_counts = Counter(candidate.title for candidate in candidates)
    raw_directory = Path(raw_directory)
    facts = []
    issues = []
    checked = 0
    for candidate in candidates:
        source = source_by_id.get(candidate.source_id)
        if source is None:
            issues.append({"source_id": candidate.source_id, "issue": "missing_registry_source"})
            continue
        raw_path = raw_directory / f"{candidate.source_id}.json"
        if not raw_path.exists():
            issues.append({"source_id": candidate.source_id, "issue": "missing_raw_detail"})
            continue
        raw_bytes = raw_path.read_bytes()
        actual_sha256 = sha256_bytes(raw_bytes)
        if source.content_sha256 != actual_sha256:
            issues.append(
                {
                    "source_id": candidate.source_id,
                    "issue": "content_sha256_mismatch",
                    "expected": source.content_sha256,
                    "actual": actual_sha256,
                }
            )
            continue
        exhibit_id = candidate.catalog_metadata["exhibit_id"]
        try:
            data, _ = parse_tibetan_museum_detail(
                json.loads(raw_bytes), expected_exhibit_id=exhibit_id
            )
        except (ValueError, json.JSONDecodeError) as exc:
            issues.append(
                {"source_id": candidate.source_id, "issue": "invalid_detail", "detail": str(exc)}
            )
            continue
        comparisons = {
            "title": (candidate.title, str(data.get("exhibit_name") or "").strip()),
            "museum_name": (
                candidate.catalog_metadata["museum_name"],
                str(data.get("museum_name") or "").strip(),
            ),
            "category": (
                candidate.catalog_metadata["category"],
                str(data.get("cate_name") or "").strip(),
            ),
            "period": (
                candidate.catalog_metadata["period"],
                str(data.get("year_name") or "").strip(),
            ),
            "texture": (
                candidate.catalog_metadata["texture"],
                str(data.get("texture_name") or "").strip(),
            ),
        }
        source_issues = [
            {
                "source_id": candidate.source_id,
                "issue": "metadata_mismatch",
                "field": field,
                "expected": expected,
                "actual": actual,
            }
            for field, (expected, actual) in comparisons.items()
            if expected != actual
        ]
        if source.crawl_status.value != "parsed":
            source_issues.append(
                {
                    "source_id": candidate.source_id,
                    "issue": "source_not_parsed",
                    "actual": source.crawl_status.value,
                }
            )
        if source.url != candidate.url:
            source_issues.append(
                {
                    "source_id": candidate.source_id,
                    "issue": "source_url_mismatch",
                    "expected": candidate.url,
                    "actual": source.url,
                }
            )
        if source_issues:
            issues.extend(source_issues)
            continue

        title = candidate.title
        subject = f"{title}（展品ID：{exhibit_id}）" if title_counts[title] > 1 else title
        museum = str(data["museum_name"]).strip()
        category = str(data.get("cate_name") or "").strip()
        period = str(data.get("year_name") or "").strip()
        texture = str(data.get("texture_name") or "").strip()
        evidence = (
            f"青海藏文化博物院官方API记录：展品ID：{exhibit_id}；文物名称：{title}；"
            f"馆藏机构：{museum}；文物类别：{category or '未标注'}；"
            f"年代：{period or '未标注'}；质地：{texture or '未标注'}"
        )
        relations = [
            ("held_by", museum, "ORGANIZATION"),
            ("made_of", texture, "MATERIAL"),
        ]
        if category:
            relations.append(("belongs_to_category", category, "CATEGORY"))
        if period:
            relations.append(("created_in_period", period, "HISTORICAL_PERIOD"))
        facts.extend(
            _museum_fact(
                subject=subject,
                predicate=predicate,
                obj=obj,
                object_type=object_type,
                source=source,
                evidence=evidence,
            )
            for predicate, obj, object_type in relations
        )
        checked += 1

    unique = {fact.fact_id: fact for fact in facts}
    records = sorted(unique.values(), key=lambda fact: fact.fact_id)
    return records, {
        "checked_sources": len(candidates),
        "eligible_sources": checked,
        "issues": issues,
        "generated_facts": len(records),
        "relation_distribution": dict(Counter(fact.predicate for fact in records)),
        "duplicate_title_records": sum(count for count in title_counts.values() if count > 1),
    }


def merge_tibetan_museum_facts(
    existing: Iterable[FactRecord], generated: Iterable[FactRecord]
) -> tuple[list[FactRecord], dict[str, Any]]:
    existing_records = list(existing)
    generated_records = list(generated)
    merged = {fact.fact_id: fact for fact in existing_records}
    semantic_owner = {
        (
            fact.subject,
            fact.subject_type,
            fact.predicate,
            fact.object,
            fact.object_type,
        ): fact.fact_id
        for fact in existing_records
    }
    retained = 0
    skipped = []
    for fact in generated_records:
        key = (
            fact.subject,
            fact.subject_type,
            fact.predicate,
            fact.object,
            fact.object_type,
        )
        owner = semantic_owner.get(key)
        if owner and owner != fact.fact_id:
            skipped.append({"fact_id": fact.fact_id, "existing_fact_id": owner})
            continue
        if fact.fact_id not in merged:
            retained += 1
        merged[fact.fact_id] = fact
        semantic_owner[key] = fact.fact_id
    return sorted(merged.values(), key=lambda fact: fact.fact_id), {
        "retained_new_facts": retained,
        "skipped_semantic_duplicates": skipped,
        "projected_fact_total": len(merged),
        "manual_checked_before": sum(fact.manual_checked for fact in existing_records),
        "manual_checked_after": sum(fact.manual_checked for fact in merged.values()),
    }
