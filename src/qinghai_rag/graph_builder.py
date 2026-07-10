from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import networkx as nx

from qinghai_rag.io_utils import write_json_atomic
from qinghai_rag.normalize import normalize_entity_name
from qinghai_rag.schemas import EntityRecord, FactRecord, SourceRecord


def entity_node_id(name: str, entity_type: str) -> str:
    digest = hashlib.sha256(f"{entity_type}\0{name}".encode()).hexdigest()[:16]
    return f"entity:{digest}"


def build_graph(
    facts: list[FactRecord],
    entities: list[EntityRecord],
    sources: list[SourceRecord],
) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(dataset="QinghaiRAG", schema_version="0.1.0")
    entity_lookup: dict[tuple[str, str], str] = {}
    for entity in entities:
        node_id = entity_node_id(entity.name, entity.type)
        entity_lookup[(normalize_entity_name(entity.name), entity.type)] = node_id
        graph.add_node(
            node_id,
            kind="entity",
            name=entity.name,
            entity_type=entity.type,
            aliases=entity.aliases,
            confidence=entity.confidence,
        )
    for source in sources:
        graph.add_node(
            f"source:{source.source_id}",
            kind="source",
            name=source.title,
            source_id=source.source_id,
            url=source.url,
        )
    for fact in facts:
        subject_key = (normalize_entity_name(fact.subject), fact.subject_type)
        object_key = (normalize_entity_name(fact.object), fact.object_type)
        subject_id = entity_lookup.get(subject_key) or entity_node_id(*subject_key)
        object_id = entity_lookup.get(object_key) or entity_node_id(*object_key)
        if subject_id not in graph:
            graph.add_node(
                subject_id,
                kind="entity",
                name=fact.subject,
                entity_type=fact.subject_type,
                aliases=[],
                confidence=fact.confidence,
            )
        if object_id not in graph:
            graph.add_node(
                object_id,
                kind="entity",
                name=fact.object,
                entity_type=fact.object_type,
                aliases=[],
                confidence=fact.confidence,
            )
        graph.add_edge(
            subject_id,
            object_id,
            key=fact.fact_id,
            predicate=fact.predicate,
            fact_id=fact.fact_id,
            source_id=fact.evidence_source_id,
            source_url=fact.evidence_url,
            evidence_text=fact.evidence_text,
            confidence=fact.confidence,
            verified=fact.verified,
        )
        source_node = f"source:{fact.evidence_source_id}"
        if source_node in graph:
            graph.add_edge(
                subject_id,
                source_node,
                key=f"provenance:{fact.fact_id}",
                predicate="supported_by",
                fact_id=fact.fact_id,
                source_id=fact.evidence_source_id,
                confidence=fact.confidence,
            )
    return graph


def save_graph(graph: nx.MultiDiGraph, path: str | Path) -> None:
    payload: dict[str, Any] = nx.node_link_data(graph, edges="links")
    write_json_atomic(path, payload)


def load_graph(path: str | Path) -> nx.MultiDiGraph:
    import json

    with Path(path).open("r", encoding="utf-8") as handle:
        return nx.node_link_graph(
            json.load(handle), directed=True, multigraph=True, edges="links"
        )
