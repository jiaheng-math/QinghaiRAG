from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Any, Iterable

from qinghai_rag.schemas import ChunkRecord, EntityRecord, FactRecord, QARecord, SourceRecord


def _distribution(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _tier_assessment(counts: dict[str, int], targets: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    meets_minimum = True
    for metric, bounds in targets.items():
        if metric == "label":
            continue
        value = counts.get(metric, 0)
        minimum, maximum = int(bounds["min"]), int(bounds["max"])
        if value < minimum:
            status = "below"
            meets_minimum = False
        elif value > maximum:
            status = "above"
        else:
            status = "in_range"
        result[metric] = {
            "value": value,
            "min": minimum,
            "max": maximum,
            "status": status,
        }
    return {
        "label": targets.get("label", ""),
        "meets_minimum": meets_minimum,
        "metrics": result,
    }


def compute_dataset_stats(
    sources: list[SourceRecord],
    entities: list[EntityRecord],
    facts: list[FactRecord],
    chunks: list[ChunkRecord],
    qa: list[QARecord],
    scale_targets: dict[str, Any] | None = None,
    restricted_domains: list[str] | None = None,
) -> dict[str, Any]:
    fact_contributions = Counter(fact.evidence_source_id for fact in facts)
    chunk_contributions = Counter(chunk.source_id for chunk in chunks)
    qa_contributions: Counter[str] = Counter()
    for item in qa:
        qa_contributions.update(set(item.evidence_source_ids))

    source_ids = [source.source_id for source in sources]
    per_source = {
        source_id: {
            "facts": fact_contributions[source_id],
            "chunks": chunk_contributions[source_id],
            "qa": qa_contributions[source_id],
        }
        for source_id in source_ids
    }
    source_count = max(len(sources), 1)
    chunk_lengths = [len(chunk.text) for chunk in chunks]
    restricted_source_ids = {
        source.source_id
        for source in sources
        if source.license_status.value in {"restricted", "forbidden"}
        or source.release_policy.value in {"local_only", "exclude", "metadata_and_facts_only"}
        or any(
            source.domain == domain or source.domain.endswith(f".{domain}")
            for domain in (restricted_domains or [])
        )
    }
    restricted_chunks = [chunk for chunk in chunks if chunk.source_id in restricted_source_ids]
    restricted_open_text = [chunk for chunk in restricted_chunks if chunk.chunk_kind == "open_text"]

    counts = {
        "sources": len(sources),
        "entities": len(entities),
        "facts": len(facts),
        "chunks": len(chunks),
        "qa": len(qa),
        "manually_checked_facts": sum(fact.manual_checked for fact in facts),
        "manually_checked_qa": sum(item.manual_checked for item in qa),
    }
    targets = (scale_targets or {}).get("tiers", {})
    return {
        "counts": counts,
        "sources": {
            "source_type_distribution": _distribution(
                source.source_type.value for source in sources
            ),
            "release_policy_distribution": _distribution(
                source.release_policy.value for source in sources
            ),
            "topic_distribution": _distribution(
                topic for source in sources for topic in source.topic
            ),
            "region_distribution": _distribution(
                region for source in sources for region in source.region
            ),
        },
        "entities": {
            "type_distribution": _distribution(entity.type for entity in entities),
        },
        "facts": {
            "relation_distribution": _distribution(fact.predicate for fact in facts),
            "verified": sum(fact.verified for fact in facts),
            "manually_checked": counts["manually_checked_facts"],
        },
        "chunks": {
            "count": len(chunks),
            "average_length_chars": mean(chunk_lengths) if chunk_lengths else 0.0,
            "median_length_chars": median(chunk_lengths) if chunk_lengths else 0.0,
            "kind_distribution": _distribution(chunk.chunk_kind for chunk in chunks),
        },
        "qa": {
            "type_distribution": _distribution(item.answer_type for item in qa),
            "unanswerable_count": sum(item.unanswerable for item in qa),
            "unanswerable_ratio": (sum(item.unanswerable for item in qa) / len(qa) if qa else 0.0),
            "manually_checked": counts["manually_checked_qa"],
        },
        "source_contributions": {
            "average_facts_per_source": len(facts) / source_count,
            "average_chunks_per_source": len(chunks) / source_count,
            "average_qa_per_source": sum(qa_contributions.values()) / source_count,
            "per_source": per_source,
        },
        "restricted_source_chunk_audit": {
            "restricted_or_non_fulltext_source_count": len(restricted_source_ids),
            "all_chunk_records": len(restricted_chunks),
            "synthetic_fact_chunks": sum(
                chunk.chunk_kind == "synthetic_fact" for chunk in restricted_chunks
            ),
            "open_text_violations": len(restricted_open_text),
            "violation_chunk_ids": [chunk.chunk_id for chunk in restricted_open_text],
            "passed": not restricted_open_text,
            "note": (
                "Synthetic fact chunks may cite restricted sources because their text is project-authored; "
                "open-text chunks from those sources are violations."
            ),
        },
        "scale_assessment": {
            tier: _tier_assessment(counts, tier_targets) for tier, tier_targets in targets.items()
        },
    }


def render_stats_markdown(stats: dict[str, Any]) -> str:
    lines = ["# QinghaiRAG dataset statistics", "", "## Dataset counts", ""]
    lines.extend(["| Metric | Count |", "|---|---:|"])
    lines.extend(f"| {key} | {value} |" for key, value in stats["counts"].items())

    lines.extend(["", "## Scale assessment", ""])
    for tier, assessment in stats["scale_assessment"].items():
        lines.extend(
            [
                f"### {tier}: {assessment['label']}",
                "",
                f"Meets all minimums: **{assessment['meets_minimum']}**",
                "",
                "| Metric | Current | Target | Status |",
                "|---|---:|---:|---|",
            ]
        )
        for metric, item in assessment["metrics"].items():
            lines.append(
                f"| {metric} | {item['value']} | {item['min']}–{item['max']} | {item['status']} |"
            )

    distribution_sections = [
        ("Source type distribution", stats["sources"]["source_type_distribution"]),
        ("Release policy distribution", stats["sources"]["release_policy_distribution"]),
        ("Topic distribution", stats["sources"]["topic_distribution"]),
        ("Region distribution", stats["sources"]["region_distribution"]),
        ("Entity type distribution", stats["entities"]["type_distribution"]),
        ("Relation type distribution", stats["facts"]["relation_distribution"]),
        ("QA type distribution", stats["qa"]["type_distribution"]),
    ]
    for title, distribution in distribution_sections:
        lines.extend(["", f"## {title}", "", "| Value | Count |", "|---|---:|"])
        lines.extend(f"| {key} | {value} |" for key, value in distribution.items())

    chunks = stats["chunks"]
    qa_stats = stats["qa"]
    contributions = stats["source_contributions"]
    audit = stats["restricted_source_chunk_audit"]
    lines.extend(
        [
            "",
            "## Chunk and QA summary",
            "",
            f"- Mean chunk length: {chunks['average_length_chars']:.2f} characters",
            f"- Median chunk length: {chunks['median_length_chars']:.2f} characters",
            f"- Unanswerable QA ratio: {qa_stats['unanswerable_ratio']:.2%}",
            "",
            "## Average contribution per registered source",
            "",
            f"- Facts: {contributions['average_facts_per_source']:.2f}",
            f"- Chunks: {contributions['average_chunks_per_source']:.2f}",
            f"- QA source links: {contributions['average_qa_per_source']:.2f}",
            "",
            "## Restricted-source chunk audit",
            "",
            f"- Passed: **{audit['passed']}**",
            f"- Project-authored synthetic chunks citing restricted/non-fulltext sources: {audit['synthetic_fact_chunks']}",
            f"- Open-text violations: {audit['open_text_violations']}",
            "",
            audit["note"],
            "",
        ]
    )
    return "\n".join(lines)
