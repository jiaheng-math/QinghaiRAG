from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from qinghai_rag.schemas import ChunkRecord, EntityRecord, FactRecord, SourceRecord

BOUNDARY_RE = re.compile(r"[。！？；\n]+")

PREDICATE_SUMMARY_TEMPLATES = {
    "belongs_to_category": "所属类别为“{object}”",
    "located_in": "所在地为“{object}”",
    "declared_by": "申报地区或单位为“{object}”",
    "protected_by": "保护单位为“{object}”",
    "inherited_by": "代表性传承人为“{object}”",
    "associated_with_ethnic_group": "相关民族为“{object}”",
    "related_to_festival": "相关节庆或活动为“{object}”",
    "mentioned_in_source": "相关来源或概念为“{object}”",
    "has_level": "项目级别为“{object}”",
    "related_to_concept": "相关概念为“{object}”",
}


def stable_chunk_id(doc_id: str, start: int, end: int, text: str) -> str:
    digest = hashlib.sha256(f"{doc_id}\0{start}\0{end}\0{text}".encode()).hexdigest()[:12]
    return f"chk_{digest}"


def split_text(
    text: str, chunk_size_chars: int = 500, overlap_chars: int = 80
) -> list[tuple[int, int, str]]:
    if chunk_size_chars <= 0 or overlap_chars < 0 or overlap_chars >= chunk_size_chars:
        raise ValueError("Require chunk_size_chars > overlap_chars >= 0")
    text = text.strip()
    if not text:
        return []
    boundaries = [match.end() for match in BOUNDARY_RE.finditer(text)]
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(text):
        target = min(start + chunk_size_chars, len(text))
        candidates = [point for point in boundaries if start < point <= target]
        end = max(candidates) if candidates else target
        if end <= start:
            end = min(start + chunk_size_chars, len(text))
        value = text[start:end].strip()
        leading = len(text[start:end]) - len(text[start:end].lstrip())
        trailing = len(text[start:end]) - len(text[start:end].rstrip())
        real_start, real_end = start + leading, end - trailing
        if value:
            chunks.append((real_start, real_end, value))
        if end >= len(text):
            break
        proposed = max(end - overlap_chars, start + 1)
        previous_boundaries = [point for point in boundaries if start < point <= proposed]
        start = max(previous_boundaries) if previous_boundaries else proposed
    return chunks


def infer_labels(text: str, entities: list[EntityRecord]) -> tuple[list[str], list[str], list[str]]:
    mentions, regions, topics = [], [], []
    topic_terms = ["非遗", "民族文化", "生态旅游", "博物馆", "传统美术", "传统技艺"]
    for entity in entities:
        names = [entity.name, *entity.aliases]
        if any(name and name in text for name in names):
            mentions.append(entity.name)
            if entity.type == "REGION":
                regions.append(entity.name)
            if entity.type == "CATEGORY":
                topics.append(entity.name)
    topics.extend(term for term in topic_terms if term in text)
    return sorted(set(topics)), sorted(set(regions)), sorted(set(mentions))


def build_open_chunks(
    documents: list[dict],
    sources: dict[str, SourceRecord],
    entities: list[EntityRecord],
    chunk_size_chars: int = 500,
    overlap_chars: int = 80,
) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    for document in documents:
        source = sources.get(document["source_id"])
        if (
            not source
            or not source.raw_text_release
            or source.release_policy.value
            not in {
                "full_text_allowed",
                "government_public",
            }
        ):
            continue
        for start, end, text in split_text(document["text"], chunk_size_chars, overlap_chars):
            topics, regions, mentions = infer_labels(text, entities)
            records.append(
                ChunkRecord(
                    chunk_id=stable_chunk_id(document["doc_id"], start, end, text),
                    doc_id=document["doc_id"],
                    source_id=source.source_id,
                    text=text,
                    char_start=start,
                    char_end=end,
                    topic_labels=sorted(set(source.topic) | set(topics)),
                    region_labels=sorted(set(source.region) | set(regions)),
                    entity_mentions=mentions,
                    license_status=source.license_status,
                    release_policy=source.release_policy,
                    source_url=source.url,
                    retrieved_at=source.retrieved_at,
                    notes=document.get("attribution")
                    or "Built from release-approved open text.",
                )
            )
    return records


def build_synthetic_fact_chunks(
    facts: list[FactRecord], sources: dict[str, SourceRecord]
) -> list[ChunkRecord]:
    grouped: dict[tuple[str, str], list[FactRecord]] = defaultdict(list)
    for fact in facts:
        if fact.verified and fact.confidence in {"high", "medium"}:
            grouped[(fact.subject, fact.evidence_source_id)].append(fact)
    chunks: list[ChunkRecord] = []
    for (subject, source_id), group in grouped.items():
        source = sources.get(source_id)
        if not source:
            continue
        statements = [
            PREDICATE_SUMMARY_TEMPLATES[fact.predicate].format(object=fact.object)
            for fact in group
        ]
        text = (
            f"以下是 QinghaiRAG 根据已核验结构化事实生成的中性摘要，并非来源原文："
            f"关于{subject}，" + "；".join(statements) + f"。依据来源编号 {source_id}。"
        )
        doc_id = f"doc_synthetic_{hashlib.sha256((subject + source_id).encode()).hexdigest()[:12]}"
        chunks.append(
            ChunkRecord(
                chunk_id=stable_chunk_id(doc_id, 0, len(text), text),
                doc_id=doc_id,
                source_id=source_id,
                text=text,
                char_start=0,
                char_end=len(text),
                topic_labels=sorted(set(source.topic)),
                region_labels=sorted(set(source.region)),
                entity_mentions=sorted(
                    {fact.subject for fact in group} | {fact.object for fact in group}
                ),
                license_status="open",
                release_policy="full_text_allowed",
                source_url=source.url,
                retrieved_at=source.retrieved_at,
                chunk_kind="synthetic_fact",
                notes="Project-authored synthetic summary; not a quotation from the source.",
            )
        )
    return chunks
