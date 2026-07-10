from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Any
from urllib.parse import urlencode

import requests

from qinghai_rag.schemas import SourceCandidateRecord
from qinghai_rag.source_registry import normalize_domain

TIBETAN_MUSEUM_API_BASE = "https://uc.tibetanculturemuseum.com.cn"
TIBETAN_MUSEUM_EXHIBIT_LIST = f"{TIBETAN_MUSEUM_API_BASE}/gwebapi/exhibit/list"
TIBETAN_MUSEUM_EXHIBIT_DETAIL = f"{TIBETAN_MUSEUM_API_BASE}/gwebapi/exhibit/detail"
TIBETAN_MUSEUM_PUBLISHER = "青海藏文化博物院"


def _candidate_id(url: str) -> str:
    return "candidate_" + hashlib.sha256(url.encode()).hexdigest()[:12]


def tibetan_museum_exhibit_candidate(
    item: dict[str, Any], discovered_at: str | None = None
) -> SourceCandidateRecord:
    exhibit_id = str(item["exhibit_id"]).strip()
    url = f"{TIBETAN_MUSEUM_EXHIBIT_DETAIL}?{urlencode({'exhibit_id': exhibit_id, 'p': 'w'})}"
    category = str(item.get("cate_name") or "").strip()
    topics = ["博物馆与文化场馆", "民族文化", "馆藏文物"]
    if category:
        topics.append(category)
    return SourceCandidateRecord(
        candidate_id=_candidate_id(url),
        source_id=f"src_tibetan_museum_exhibit_{exhibit_id}",
        title=str(item.get("exhibit_name") or "").strip(),
        publisher=TIBETAN_MUSEUM_PUBLISHER,
        source_type="museum_or_scenic_spot_official",
        url=url,
        domain=normalize_domain(url),
        region=["青海省", "西宁市"],
        topic=topics,
        license_status="unclear",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        discovery_method="tibetan_museum_exhibit",
        discovered_at=discovered_at or date.today().isoformat(),
        catalog_metadata={
            "exhibit_id": exhibit_id,
            "museum_id": str(item.get("museum_id") or ""),
            "museum_name": str(item.get("museum_name") or "").strip(),
            "category_id": str(item.get("cate_id") or ""),
            "category": category,
            "period": str(item.get("year_name") or "").strip(),
            "texture": str(item.get("texture_name") or "").strip(),
            "has_3d": "true" if item.get("three_url") else "false",
        },
        notes=(
            "Discovered from the official Qinghai Tibetan Culture Museum exhibit API; "
            "metadata-and-facts-only pending detail-level review. Images, 3D assets, and "
            "description text are not approved for release."
        ),
    )


def candidates_from_tibetan_museum_payload(
    payload: dict[str, Any], discovered_at: str | None = None
) -> tuple[list[SourceCandidateRecord], dict[str, int]]:
    if int(payload.get("status") or 0) != 1:
        raise ValueError(f"Museum API returned unsuccessful status: {payload.get('msg', '')}")
    data = payload.get("data") or {}
    rows = data.get("list") or []
    records = [
        tibetan_museum_exhibit_candidate(item, discovered_at=discovered_at)
        for item in rows
        if item.get("exhibit_id") and item.get("exhibit_name")
    ]
    deduplicated = {record.source_id: record for record in records}
    return sorted(deduplicated.values(), key=lambda record: record.source_id), {
        "reported_total": int(data.get("count") or len(records)),
        "returned": len(rows),
    }


def discover_tibetan_museum_exhibits(
    *,
    page_size: int = 500,
    timeout: float = 30.0,
    no_env_proxy: bool = False,
    session: requests.Session | None = None,
) -> tuple[list[SourceCandidateRecord], dict[str, int]]:
    if page_size <= 0 or page_size > 500:
        raise ValueError("page_size must be between 1 and 500")
    client = session or requests.Session()
    if session is None:
        client.trust_env = not no_env_proxy
    common = {"p": "w", "limit": page_size, "cate_id": 0}
    first = client.get(
        TIBETAN_MUSEUM_EXHIBIT_LIST,
        params={**common, "page": 1},
        timeout=timeout,
    )
    first.raise_for_status()
    records, metadata = candidates_from_tibetan_museum_payload(first.json())
    total_pages = max(1, math.ceil(metadata["reported_total"] / page_size))
    for page in range(2, total_pages + 1):
        response = client.get(
            TIBETAN_MUSEUM_EXHIBIT_LIST,
            params={**common, "page": page},
            timeout=timeout,
        )
        response.raise_for_status()
        discovered, _ = candidates_from_tibetan_museum_payload(response.json())
        records.extend(discovered)
    deduplicated = {record.source_id: record for record in records}
    return sorted(deduplicated.values(), key=lambda record: record.source_id), {
        **metadata,
        "fetched_pages": total_pages,
    }
