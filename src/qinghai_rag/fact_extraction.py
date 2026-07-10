from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from bs4 import BeautifulSoup

from qinghai_rag.normalize import normalize_entity_name, normalize_region
from qinghai_rag.schemas import FactRecord, SourceRecord

HEADER_MAP = {
    "项目名称": "project",
    "名称": "project",
    "子项名称": "project",
    "类别": "category",
    "项目类别": "category",
    "所属地区": "region",
    "申报地区": "declared_by",
    "申报单位": "declared_by",
    "保护单位": "protected_by",
    "代表性传承人": "inherited_by",
    "传承人": "inherited_by",
    "级别": "level",
    "项目级别": "level",
}

RELATIONS = {
    "category": ("belongs_to_category", "CATEGORY"),
    "region": ("located_in", "REGION"),
    "declared_by": ("declared_by", "ORGANIZATION"),
    "protected_by": ("protected_by", "ORGANIZATION"),
    "inherited_by": ("inherited_by", "PERSON"),
    "level": ("has_level", "CONCEPT"),
}


def stable_fact_id(subject: str, predicate: str, obj: str, source_id: str) -> str:
    digest = hashlib.sha256(f"{subject}\0{predicate}\0{obj}\0{source_id}".encode()).hexdigest()[:12]
    return f"fact_{digest}"


def make_fact(
    project: str,
    predicate: str,
    obj: str,
    object_type: str,
    source: SourceRecord,
    evidence: str | None,
    method: str = "table_parse",
    verified: bool = False,
    confidence: str = "medium",
) -> FactRecord:
    project = normalize_entity_name(project)
    obj = normalize_region(obj) if object_type == "REGION" else normalize_entity_name(obj)
    return FactRecord(
        fact_id=stable_fact_id(project, predicate, obj, source.source_id),
        subject=project,
        subject_type="ICH_PROJECT",
        predicate=predicate,
        object=obj,
        object_type=object_type,
        evidence_source_id=source.source_id,
        evidence_url=source.url,
        evidence_text=(evidence[:300] if evidence else None),
        extraction_method=method,
        verified=verified,
        confidence=confidence,
        notes="Automatically extracted; review before treating as authoritative.",
    )


def extract_table_facts(html: str, source: SourceRecord) -> list[FactRecord]:
    soup = BeautifulSoup(html, "lxml")
    facts: list[FactRecord] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])]
        mapped = [HEADER_MAP.get(re.sub(r"\s+", "", header)) for header in headers]
        if "project" not in mapped:
            continue
        for row in rows[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if len(cells) != len(mapped):
                continue
            values = {field: value for field, value in zip(mapped, cells) if field and value}
            project = values.get("project")
            if not project:
                continue
            evidence = "；".join(f"{header}：{value}" for header, value in zip(headers, cells))
            for field, (predicate, object_type) in RELATIONS.items():
                for obj in re.split(r"[、,，;/；]", values.get(field, "")):
                    if obj.strip():
                        facts.append(
                            make_fact(
                                project, predicate, obj.strip(), object_type, source, evidence
                            )
                        )
    return deduplicate_facts(facts)


def extract_semistructured_facts(text: str, source: SourceRecord) -> list[FactRecord]:
    facts: list[FactRecord] = []
    pattern = re.compile(
        r"(?:项目名称|名称)\s*[：:]\s*(?P<project>[^\n；;]{2,80}).{0,100}?"
        r"(?:类别|项目类别)\s*[：:]\s*(?P<category>[^\n；;]{2,40})",
        re.S,
    )
    for match in pattern.finditer(text):
        evidence = re.sub(r"\s+", " ", match.group(0))[:300]
        facts.append(
            make_fact(
                match.group("project"),
                "belongs_to_category",
                match.group("category"),
                "CATEGORY",
                source,
                evidence,
                method="rule",
                confidence="medium",
            )
        )
    return deduplicate_facts(facts)


def deduplicate_facts(facts: Iterable[FactRecord]) -> list[FactRecord]:
    return list({fact.fact_id: fact for fact in facts}.values())
