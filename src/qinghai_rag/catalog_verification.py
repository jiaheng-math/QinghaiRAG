from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Iterable
from typing import Any

from qinghai_rag.schemas import FactRecord, SourceCandidateRecord

VERIFICATION_NOTE = (
    "Deterministically verified by exact agreement between official catalog metadata "
    "and page-table evidence; not manually checked."
)


def normalize_catalog_value(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split())


def crosscheck_catalog_facts(
    facts: Iterable[FactRecord],
    candidates: Iterable[SourceCandidateRecord],
    *,
    apply: bool = False,
) -> tuple[list[FactRecord], dict[str, Any]]:
    fact_records = list(facts)
    candidate_by_source = {item.source_id: item for item in candidates}
    triple_counts = Counter(
        (fact.subject, fact.predicate, fact.object) for fact in fact_records
    )
    checked = 0
    eligible = 0
    updated = 0
    issues: list[dict[str, Any]] = []
    output: list[FactRecord] = []

    for fact in fact_records:
        if fact.verified or not fact.evidence_source_id.startswith("src_ihchina_"):
            output.append(fact)
            continue

        checked += 1
        reasons: list[str] = []
        candidate = candidate_by_source.get(fact.evidence_source_id)
        if candidate is None:
            reasons.append("missing_candidate")
        else:
            if normalize_catalog_value(fact.subject) != normalize_catalog_value(
                candidate.title
            ):
                reasons.append("subject_mismatch")
            expected = {
                "belongs_to_category": candidate.catalog_metadata.get("category", ""),
                "declared_by": candidate.catalog_metadata.get("applicant", ""),
            }.get(fact.predicate)
            if not expected:
                reasons.append("unsupported_or_empty_catalog_field")
            elif normalize_catalog_value(fact.object) != normalize_catalog_value(expected):
                reasons.append("object_mismatch")
        if not fact.evidence_text:
            reasons.append("missing_page_evidence")
        key = (fact.subject, fact.predicate, fact.object)
        if triple_counts[key] > 1:
            reasons.append("duplicate_semantic_triple")

        if reasons:
            issues.append({"fact_id": fact.fact_id, "reasons": reasons})
            output.append(fact)
            continue

        eligible += 1
        if not apply:
            output.append(fact)
            continue
        payload = fact.model_dump(mode="json")
        payload["verified"] = True
        payload["notes"] = "; ".join(
            value for value in [fact.notes.rstrip("; "), VERIFICATION_NOTE] if value
        )
        output.append(FactRecord.model_validate(payload))
        updated += 1

    return output, {
        "checked": checked,
        "eligible": eligible,
        "updated": updated,
        "issues": issues,
        "manual_checked_before": sum(fact.manual_checked for fact in fact_records),
        "manual_checked_after": sum(fact.manual_checked for fact in output),
    }
