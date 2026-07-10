from __future__ import annotations

import hashlib
import re
import unicodedata
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
    "申报地区或单位": "declared_by",
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


def _normalized_project_key(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))


def _matches_source_project(project: str, source: SourceRecord) -> bool:
    if source.domain != "ihchina.cn":
        return True
    page_project = re.split(r"\s+-\s+中国非物质文化遗产网", source.title, maxsplit=1)[0]
    return _normalized_project_key(project) == _normalized_project_key(page_project)


def _matches_source_applicant(declared_by: str, source: SourceRecord) -> bool:
    if not source.source_id.startswith("src_ihchina_"):
        return True
    expected = source.region[-1] if source.region else source.province
    return _normalized_project_key(declared_by) == _normalized_project_key(expected)


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
            cells = [
                re.sub(rf"^\s*{re.escape(header)}\s*", "", value).strip()
                for header, value in zip(headers, cells)
            ]
            values = {field: value for field, value in zip(mapped, cells) if field and value}
            project = values.get("project")
            if not project:
                continue
            if not _matches_source_project(project, source):
                continue
            declared_by = values.get("declared_by", "")
            if declared_by and source.province and source.province not in declared_by:
                continue
            if declared_by and not _matches_source_applicant(declared_by, source):
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
        if not _matches_source_project(match.group("project"), source):
            continue
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


def merge_extracted_facts(
    existing: Iterable[FactRecord], extracted: Iterable[FactRecord]
) -> list[FactRecord]:
    merged = {
        fact.fact_id: fact for fact in existing if fact.verified or fact.manual_checked
    }
    for fact in extracted:
        if fact.fact_id not in merged:
            merged[fact.fact_id] = fact
    return list(merged.values())
