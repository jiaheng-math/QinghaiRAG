from __future__ import annotations

import hashlib
from collections import defaultdict

from rapidfuzz import fuzz, process

from qinghai_rag.normalize import ENTITY_ALIASES, normalize_entity_name, normalize_text_key
from qinghai_rag.schemas import EntityRecord, FactRecord


def stable_entity_id(name: str, entity_type: str) -> str:
    digest = hashlib.sha256(f"{entity_type}\0{name}".encode()).hexdigest()[:12]
    return f"ent_{digest}"


def suggest_fuzzy_matches(
    name: str, candidates: list[str], threshold: int = 90
) -> list[tuple[str, float]]:
    """Suggest only. Callers must not auto-merge fuzzy candidates."""
    return [
        (match, float(score))
        for match, score, _ in process.extract(name, candidates, scorer=fuzz.WRatio)
        if score >= threshold
    ]


def build_entities(facts: list[FactRecord]) -> tuple[list[EntityRecord], dict[str, str]]:
    grouped: dict[tuple[str, str], dict] = {}
    observed_aliases: dict[str, set[str]] = defaultdict(set)
    for fact in facts:
        for raw_name, entity_type in (
            (fact.subject, fact.subject_type),
            (fact.object, fact.object_type),
        ):
            canonical = normalize_entity_name(raw_name)
            key = (canonical, entity_type)
            observed_aliases[canonical].add(raw_name)
            if key not in grouped:
                grouped[key] = {
                    "source_id": fact.evidence_source_id,
                    "regions": set(),
                    "confidence": fact.confidence,
                }
            if entity_type == "REGION":
                grouped[key]["regions"].add(canonical)
            if fact.predicate == "located_in" and raw_name == fact.subject:
                grouped[key]["regions"].add(normalize_entity_name(fact.object))

    inverse_configured: dict[str, set[str]] = defaultdict(set)
    for alias, canonical in ENTITY_ALIASES.items():
        inverse_configured[canonical].add(alias)

    records: list[EntityRecord] = []
    alias_mapping: dict[str, str] = {}
    for (name, entity_type), metadata in sorted(grouped.items()):
        aliases = sorted((observed_aliases[name] | inverse_configured[name]) - {name})
        for alias in aliases:
            alias_mapping[normalize_text_key(alias)] = name
        records.append(
            EntityRecord(
                entity_id=stable_entity_id(name, entity_type),
                name=name,
                type=entity_type,
                aliases=aliases,
                description="",
                regions=sorted(metadata["regions"]),
                canonical_source_id=metadata["source_id"],
                confidence=metadata["confidence"],
                notes="Automatically built from evidence-backed facts; fuzzy matches require review.",
            )
        )
    return records, alias_mapping
