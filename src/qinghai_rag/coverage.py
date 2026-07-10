from __future__ import annotations

from collections import Counter
from typing import Any

from qinghai_rag.schemas import SourceRecord


def _matches(text: str, aliases: list[str]) -> bool:
    return any(alias and alias in text for alias in aliases)


def _assessment(count: int, minimum: int) -> dict[str, Any]:
    return {
        "count": count,
        "minimum": minimum,
        "status": "met" if count >= minimum else "below",
        "gap": max(minimum - count, 0),
    }


def compute_source_coverage(sources: list[SourceRecord], targets: dict[str, Any]) -> dict[str, Any]:
    level_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    region_counts: Counter[str] = Counter()
    source_topics: dict[str, list[str]] = {}
    source_regions: dict[str, list[str]] = {}

    level_targets = targets.get("source_levels", {})
    topic_targets = targets.get("topics", {})
    region_targets = targets.get("regions", {})
    coverage_sources = [source for source in sources if source.crawl_status.value == "parsed"]

    for source in coverage_sources:
        source_type = source.source_type.value
        for level, config in level_targets.items():
            if source_type in config.get("source_types", []):
                level_counts[level] += 1

        topic_text = " ".join([source.title, *source.topic])
        matched_topics = [
            topic
            for topic, config in topic_targets.items()
            if _matches(topic_text, config.get("aliases", [topic]))
        ]
        source_topics[source.source_id] = matched_topics
        topic_counts.update(matched_topics)

        region_text = " ".join(source.region)
        matched_regions = [
            region
            for region, config in region_targets.items()
            if _matches(region_text, config.get("aliases", [region]))
        ]
        source_regions[source.source_id] = matched_regions
        region_counts.update(matched_regions)

    matrix = {
        region: {
            topic: sum(
                region in source_regions[source.source_id]
                and topic in source_topics[source.source_id]
                for source in coverage_sources
            )
            for topic in topic_targets
        }
        for region in region_targets
    }
    total = len(sources)
    metadata = {
        "publisher": sum(bool(source.publisher) for source in sources),
        "topic": sum(bool(source.topic) for source in sources),
        "region": sum(bool(source.region) for source in sources),
        "release_policy": sum(bool(source.release_policy.value) for source in sources),
    }
    assessments = {
        "source_levels": {
            key: {
                "label": config.get("label", key),
                **_assessment(level_counts[key], int(config.get("min_sources", 1))),
            }
            for key, config in level_targets.items()
        },
        "topics": {
            key: _assessment(topic_counts[key], int(config.get("min_sources", 1)))
            for key, config in topic_targets.items()
        },
        "regions": {
            key: _assessment(region_counts[key], int(config.get("min_sources", 1)))
            for key, config in region_targets.items()
        },
    }
    gaps = [
        {"dimension": dimension, "value": key, **item}
        for dimension, values in assessments.items()
        for key, item in values.items()
        if item["status"] == "below"
    ]
    return {
        "registered_sources": total,
        "coverage_sources": len(coverage_sources),
        "crawl_status_distribution": dict(
            sorted(Counter(source.crawl_status.value for source in sources).items())
        ),
        "unique_publishers": len({source.publisher for source in sources if source.publisher}),
        "unique_domains": len({source.domain for source in sources if source.domain}),
        "metadata_completeness": {
            key: {
                "count": count,
                "ratio": count / total if total else 0.0,
            }
            for key, count in metadata.items()
        },
        "assessment": assessments,
        "region_topic_matrix": matrix,
        "gaps": gaps,
        "passed": not gaps,
        "classification_note": (
            "Topic coverage uses explicit topic labels plus title keywords; region coverage uses "
            "only registry region metadata and configured administrative aliases."
        ),
    }


def render_coverage_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# QinghaiRAG source coverage audit",
        "",
        f"- Registered sources: {report['registered_sources']}",
        f"- Parsed sources counted toward coverage: {report['coverage_sources']}",
        f"- Unique publishers: {report['unique_publishers']}",
        f"- Unique domains: {report['unique_domains']}",
        f"- All coverage targets met: **{report['passed']}**",
        "",
        report["classification_note"],
    ]
    for dimension, heading in (
        ("source_levels", "Source level coverage"),
        ("topics", "Topic coverage"),
        ("regions", "Prefecture-level region coverage"),
    ):
        lines.extend(
            [
                "",
                f"## {heading}",
                "",
                "| Value | Count | Minimum | Gap | Status |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for key, item in report["assessment"][dimension].items():
            label = item.get("label", key)
            lines.append(
                f"| {label} | {item['count']} | {item['minimum']} | {item['gap']} | {item['status']} |"
            )

    topics = list(report["assessment"]["topics"])
    lines.extend(
        [
            "",
            "## Region × topic matrix",
            "",
            "| Region | " + " | ".join(topics) + " |",
            "|---|" + "---:|" * len(topics),
        ]
    )
    for region, counts in report["region_topic_matrix"].items():
        lines.append(f"| {region} | " + " | ".join(str(counts[t]) for t in topics) + " |")
    return "\n".join(lines) + "\n"
