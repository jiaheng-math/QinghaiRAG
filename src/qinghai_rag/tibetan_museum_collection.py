from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from qinghai_rag.clean_text import make_doc_id
from qinghai_rag.config import PATHS, ProjectPaths
from qinghai_rag.io_utils import sha256_bytes, upsert_jsonl
from qinghai_rag.schemas import SourceRecord
from qinghai_rag.source_registry import SourceRegistry
from qinghai_rag.tibetan_museum_discovery import TIBETAN_MUSEUM_PUBLISHER

LOGGER = logging.getLogger(__name__)


def parse_tibetan_museum_detail(
    payload: dict[str, Any], *, expected_exhibit_id: str | None = None
) -> tuple[dict[str, Any], str]:
    if int(payload.get("status") or 0) != 1:
        raise ValueError(
            f"Museum detail API returned unsuccessful status: {payload.get('msg', '')}"
        )
    data = payload.get("data") or {}
    exhibit_id = str(data.get("exhibit_id") or "")
    if expected_exhibit_id and exhibit_id != str(expected_exhibit_id):
        raise ValueError(
            f"Museum exhibit ID mismatch: expected {expected_exhibit_id}, got {exhibit_id}"
        )
    if data.get("museum_name") != TIBETAN_MUSEUM_PUBLISHER:
        raise ValueError(f"Unexpected museum owner: {data.get('museum_name', '')}")
    exhibit_name = str(data.get("exhibit_name") or "").strip()
    if not exhibit_name:
        raise ValueError("Museum detail is missing exhibit_name")
    content = BeautifulSoup(str(data.get("content") or ""), "lxml").get_text("\n", strip=True)
    fields = [
        ("文物名称", exhibit_name),
        ("馆藏机构", str(data.get("museum_name") or "").strip()),
        ("文物类别", str(data.get("cate_name") or "").strip()),
        ("年代", str(data.get("year_name") or "").strip()),
        ("质地", str(data.get("texture_name") or "").strip()),
    ]
    lines = [f"{label}：{value}" for label, value in fields if value]
    if content:
        lines.append(f"馆藏说明：{content}")
    return data, "\n".join(lines)


class TibetanMuseumCollector:
    def __init__(
        self,
        paths: ProjectPaths = PATHS,
        *,
        interval_seconds: float = 0.5,
        timeout: float = 30.0,
        contact: str | None = None,
        trust_env: bool = True,
        session: requests.Session | None = None,
    ):
        self.paths = paths
        self.paths.ensure()
        self.interval = interval_seconds
        self.timeout = timeout
        self.contact = contact or os.getenv("QINGHAI_RAG_CONTACT") or "contact-not-configured"
        self.session = session or requests.Session()
        if session is None:
            self.session.trust_env = trust_env
            retry = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET"}),
            )
            self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update(
            {
                "User-Agent": (
                    f"QinghaiRAG/0.1 (+{self.contact}; provenance-first research crawler)"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        remaining = self.interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _updated_source(source: SourceRecord, **updates: object) -> SourceRecord:
        payload = source.model_dump(mode="json")
        payload.update(updates)
        return SourceRecord.model_validate(payload)

    @staticmethod
    def _expected_exhibit_id(source: SourceRecord) -> str:
        return source.source_id.removeprefix("src_tibetan_museum_exhibit_")

    def collect(
        self,
        sources: list[SourceRecord],
        *,
        force: bool = False,
    ) -> tuple[list[SourceRecord], list[dict[str, Any]]]:
        registry = SourceRegistry(self.paths.release / "qinghai_sources.jsonl")
        raw_directory = self.paths.raw / "tibetan_museum"
        raw_directory.mkdir(parents=True, exist_ok=True)
        updated_sources = []
        documents = []
        for source in sources:
            raw_path = raw_directory / f"{source.source_id}.json"
            try:
                if raw_path.exists() and not force:
                    raw_bytes = raw_path.read_bytes()
                else:
                    self._throttle()
                    response = self.session.get(source.url, timeout=self.timeout)
                    self._last_request_at = time.monotonic()
                    response.raise_for_status()
                    raw_bytes = response.content
                    temporary = raw_path.with_suffix(".json.tmp")
                    with temporary.open("wb") as handle:
                        handle.write(raw_bytes)
                        handle.flush()
                        os.fsync(handle.fileno())
                    temporary.replace(raw_path)
                payload = json.loads(raw_bytes)
                data, text = parse_tibetan_museum_detail(
                    payload,
                    expected_exhibit_id=self._expected_exhibit_id(source),
                )
                marker = "museum detail API verified; description and media are not released"
                notes = (
                    source.notes
                    if marker in source.notes
                    else "; ".join(filter(None, [source.notes, marker]))
                )
                updated = self._updated_source(
                    source,
                    title=str(data["exhibit_name"]),
                    retrieved_at=date.today().isoformat(),
                    content_sha256=sha256_bytes(raw_bytes),
                    crawl_status="parsed",
                    license_status="unclear",
                    release_policy="metadata_and_facts_only",
                    raw_text_release=False,
                    notes=notes,
                )
                document = {
                    "doc_id": make_doc_id(source.source_id, text),
                    "source_id": source.source_id,
                    "source_url": source.url,
                    "title": updated.title,
                    "text": text,
                    "retrieved_at": updated.retrieved_at,
                    "license_status": "unclear",
                    "release_policy": "metadata_and_facts_only",
                    "raw_text_release": False,
                    "raw_path": str(raw_path),
                    "attribution": "",
                }
                registry.upsert([updated])
                upsert_jsonl(self.paths.interim / "documents.jsonl", [document], key="doc_id")
                documents.append(document)
            except (requests.RequestException, OSError, ValueError, json.JSONDecodeError) as exc:
                LOGGER.warning("Museum detail fetch failed for %s: %s", source.source_id, exc)
                marker = f"museum detail fetch failed: {exc}"
                updated = self._updated_source(
                    source,
                    crawl_status="failed",
                    notes="; ".join(filter(None, [source.notes, marker])),
                )
                registry.upsert([updated])
            updated_sources.append(updated)
        return updated_sources, documents
