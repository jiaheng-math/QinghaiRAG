from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import requests

from qinghai_rag.schemas import SourceCandidateRecord, SourceRecord
from qinghai_rag.source_registry import normalize_domain

IHCHINA_CATALOG_ENDPOINT = "https://www.ihchina.cn/getProject.html"
IHCHINA_DETAIL_BASE = "https://www.ihchina.cn/project_details"


def _clean_html_breaks(value: Any) -> str:
    return str(value or "").replace("</br>", " ").replace("<br/>", " ").strip()


def _candidate_id(url: str) -> str:
    return "candidate_" + hashlib.sha256(url.encode()).hexdigest()[:12]


def ihchina_candidate_from_item(
    item: dict[str, Any], discovered_at: str | None = None
) -> SourceCandidateRecord:
    remote_id = str(item["id"]).strip()
    url = f"{IHCHINA_DETAIL_BASE}/{remote_id}.html"
    applicant = str(item.get("province") or "").strip()
    category = str(item.get("type") or "").strip()
    regions = ["青海省"]
    if applicant and applicant not in regions:
        regions.append(applicant)
    return SourceCandidateRecord(
        candidate_id=_candidate_id(url),
        source_id=f"src_ihchina_{remote_id}",
        title=str(item.get("title") or "").strip(),
        publisher="中国非物质文化遗产网",
        source_type="national_official_database",
        url=url,
        domain=normalize_domain(url),
        region=regions,
        topic=[value for value in ["非遗", category] if value],
        license_status="unclear",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        discovery_method="ihchina_catalog",
        discovered_at=discovered_at or date.today().isoformat(),
        catalog_metadata={
            "remote_id": remote_id,
            "project_number": str(item.get("num") or "").strip(),
            "project_sequence": str(item.get("auto_id") or "").strip(),
            "category": category,
            "publication_batch": _clean_html_breaks(item.get("rx_time")),
            "entry_type": str(item.get("cate") or "").strip(),
            "applicant": applicant,
            "protection_unit": str(item.get("protect_unit") or "").strip(),
        },
        notes=(
            "Discovered from the official national ICH catalog; conservative metadata-and-facts-only "
            "policy pending page-level review."
        ),
    )


def candidates_from_ihchina_payload(
    payload: dict[str, Any], discovered_at: str | None = None
) -> list[SourceCandidateRecord]:
    records = [
        ihchina_candidate_from_item(item, discovered_at=discovered_at)
        for item in payload.get("list") or []
        if item.get("id") and item.get("title")
    ]
    return list({record.source_id: record for record in records}.values())


def discover_ihchina_catalog(
    province_code: str = "630000",
    page_size: int = 100,
    endpoint: str = IHCHINA_CATALOG_ENDPOINT,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> list[SourceCandidateRecord]:
    if page_size <= 0 or page_size > 500:
        raise ValueError("page_size must be between 1 and 500")
    client = session or requests.Session()
    common = {
        "province": province_code,
        "rx_time": "",
        "type": "",
        "cate": "",
        "keywords": "",
        "category_id": "16",
        "limit": str(page_size),
    }
    first = client.get(endpoint, params={**common, "p": 1}, timeout=timeout)
    first.raise_for_status()
    first_payload = first.json()
    records = candidates_from_ihchina_payload(first_payload)
    total_pages = int((first_payload.get("links") or {}).get("total_pages") or 1)
    for page in range(2, total_pages + 1):
        response = client.get(endpoint, params={**common, "p": page}, timeout=timeout)
        response.raise_for_status()
        records.extend(candidates_from_ihchina_payload(response.json()))
    deduplicated = {record.source_id: record for record in records}
    return sorted(deduplicated.values(), key=lambda record: record.source_id)


def candidate_to_source(candidate: SourceCandidateRecord) -> SourceRecord:
    return SourceRecord(
        source_id=candidate.source_id,
        title=candidate.title,
        publisher=candidate.publisher,
        source_type=candidate.source_type,
        url=candidate.url,
        domain=candidate.domain,
        province=candidate.province,
        region=candidate.region,
        topic=candidate.topic,
        retrieved_at=candidate.discovered_at,
        license_status=candidate.license_status,
        release_policy=candidate.release_policy,
        raw_text_release=candidate.raw_text_release,
        crawl_status="pending",
        notes=candidate.notes,
    )
