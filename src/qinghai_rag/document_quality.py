from __future__ import annotations

from collections import Counter
from typing import Any

from qinghai_rag.schemas import SourceRecord


def _latest_documents(documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for document in documents:
        source_id = str(document.get("source_id") or "")
        if source_id:
            grouped.setdefault(source_id, []).append(document)
    return {
        source_id: max(
            values,
            key=lambda item: (
                str(item.get("retrieved_at") or ""),
                len(str(item.get("text") or "")),
            ),
        )
        for source_id, values in grouped.items()
    }


def audit_document_quality(
    sources: list[SourceRecord],
    documents: list[dict[str, Any]],
    *,
    minimum_chars: int = 100,
    source_prefix: str = "",
    apply: bool = False,
) -> tuple[list[SourceRecord], dict[str, Any]]:
    if minimum_chars <= 0:
        raise ValueError("minimum_chars must be positive")
    selected = [
        source
        for source in sources
        if not source_prefix or source.source_id.startswith(source_prefix)
    ]
    latest = _latest_documents(documents)
    lengths = {
        source.source_id: len(str(latest[source.source_id].get("text") or ""))
        for source in selected
        if source.source_id in latest
    }
    missing = sorted(source.source_id for source in selected if source.source_id not in latest)
    shallow = sorted(source_id for source_id, length in lengths.items() if length < minimum_chars)
    qualified = sorted(
        source_id for source_id, length in lengths.items() if length >= minimum_chars
    )

    changed = 0
    shallow_set = set(shallow)
    updated = []
    for source in sources:
        if apply and source.source_id in shallow_set and source.crawl_status.value == "parsed":
            length = lengths[source.source_id]
            marker = (
                f"document quality audit: cleaned_text_chars={length} below minimum={minimum_chars}"
            )
            notes = (
                source.notes
                if marker in source.notes
                else "; ".join(filter(None, [source.notes, marker]))
            )
            payload = source.model_dump(mode="json")
            payload.update({"crawl_status": "fetched", "notes": notes})
            source = SourceRecord.model_validate(payload)
            changed += 1
        updated.append(source)

    buckets = Counter()
    for length in lengths.values():
        if length < 20:
            buckets["<20"] += 1
        elif length < 100:
            buckets["20-99"] += 1
        elif length < 300:
            buckets["100-299"] += 1
        else:
            buckets[">=300"] += 1
    return updated, {
        "source_prefix": source_prefix,
        "minimum_chars": minimum_chars,
        "selected_sources": len(selected),
        "documents": len(lengths),
        "qualified_sources": len(qualified),
        "shallow_sources": len(shallow),
        "missing_documents": missing,
        "length_distribution": dict(buckets),
        "shallow_source_ids": shallow,
        "status_changes": changed,
        "applied": apply,
    }
