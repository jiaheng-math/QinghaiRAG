from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import UnicodeDammit

from qinghai_rag.clean_text import clean_html, make_doc_id
from qinghai_rag.config import PATHS, ProjectPaths, load_project_config
from qinghai_rag.io_utils import sha256_bytes, upsert_jsonl
from qinghai_rag.schemas import SourceRecord
from qinghai_rag.source_registry import SourceRegistry, decide_release_policy

LOGGER = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    source: SourceRecord
    document: dict | None


class FriendlyCrawler:
    def __init__(
        self,
        paths: ProjectPaths = PATHS,
        interval_seconds: float | None = None,
        contact: str | None = None,
        timeout: float = 30.0,
    ):
        config = load_project_config("sources_seed.yaml", paths)
        self.paths = paths
        self.paths.ensure()
        self.interval = float(
            interval_seconds
            if interval_seconds is not None
            else config.get("request_interval_seconds", 1.0)
        )
        self.contact = (
            contact
            or os.getenv("QINGHAI_RAG_CONTACT")
            or config.get("project_contact", "contact-not-configured")
        )
        self.user_agent = f"QinghaiRAG/0.1 (+{self.contact}; provenance-first research crawler)"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": self.user_agent, "Accept-Language": "zh-CN,zh;q=0.9"}
        )
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request_at = 0.0

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            robots_url = urljoin(origin, "/robots.txt")
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                self._throttle()
                response = self.session.get(robots_url, timeout=min(self.timeout, 10))
                self._last_request_at = time.monotonic()
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                    self._robots[origin] = parser
                else:
                    LOGGER.warning("robots.txt returned %s for %s", response.status_code, origin)
                    self._robots[origin] = None
            except requests.RequestException as exc:
                LOGGER.warning("Could not read robots.txt for %s: %s", origin, exc)
                self._robots[origin] = None
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(self.user_agent, url)

    def _throttle(self) -> None:
        remaining = self.interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def fetch(self, source: SourceRecord, force: bool = False) -> CrawlResult:
        raw_path = self.paths.raw / f"{source.source_id}.html"
        if raw_path.exists() and source.crawl_status in {"fetched", "parsed"} and not force:
            html_bytes = raw_path.read_bytes()
            LOGGER.info("Resume: reusing %s", raw_path)
        else:
            if not self._robots_allowed(source.url):
                LOGGER.warning("robots.txt disallows %s", source.url)
                return CrawlResult(
                    source.model_copy(
                        update={
                            "crawl_status": "skipped",
                            "notes": source.notes + "; robots disallowed",
                        }
                    ),
                    None,
                )
            try:
                self._throttle()
                response = self.session.get(source.url, timeout=self.timeout)
                self._last_request_at = time.monotonic()
                response.raise_for_status()
                html_bytes = response.content
                temporary = raw_path.with_suffix(".html.tmp")
                with temporary.open("wb") as handle:
                    handle.write(html_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(raw_path)
            except (requests.RequestException, OSError) as exc:
                LOGGER.warning("Fetch failed for %s: %s", source.url, exc)
                return CrawlResult(
                    source.model_copy(
                        update={
                            "crawl_status": "failed",
                            "notes": source.notes + f"; fetch failed: {exc}",
                        }
                    ),
                    None,
                )

        html = UnicodeDammit(html_bytes, is_html=True).unicode_markup
        if html is None:
            html = html_bytes.decode("utf-8", errors="replace")
        title, text = clean_html(html)
        decision = decide_release_policy(
            source.url,
            text=html,
            configured_license=source.license_status.value,
            configured_policy=source.release_policy.value,
        )
        updated = source.model_copy(
            update={
                "title": title or source.title,
                "retrieved_at": date.today().isoformat(),
                "content_sha256": sha256_bytes(html_bytes),
                "crawl_status": "parsed",
                "license_status": decision.license_status,
                "release_policy": decision.release_policy,
                "raw_text_release": decision.raw_text_release,
                "notes": source.notes + f"; policy after fetch: {decision.reason}",
            }
        )
        document = {
            "doc_id": make_doc_id(source.source_id, text),
            "source_id": source.source_id,
            "source_url": source.url,
            "title": updated.title,
            "text": text,
            "retrieved_at": updated.retrieved_at,
            "license_status": decision.license_status,
            "release_policy": decision.release_policy,
            "raw_text_release": decision.raw_text_release,
            "raw_path": str(raw_path),
        }
        return CrawlResult(updated, document)

    def collect(
        self, sources: list[SourceRecord], force: bool = False
    ) -> tuple[list[SourceRecord], list[dict]]:
        updated: list[SourceRecord] = []
        documents: list[dict] = []
        registry = SourceRegistry(self.paths.release / "qinghai_sources.jsonl")
        for source in sources:
            result = self.fetch(source, force=force)
            updated.append(result.source)
            registry.upsert([result.source])  # checkpoint after every source
            if result.document:
                documents.append(result.document)
                upsert_jsonl(
                    self.paths.interim / "documents.jsonl", [result.document], key="doc_id"
                )
        return updated, documents
