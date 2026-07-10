from __future__ import annotations

import hashlib
import re
import time
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from qinghai_rag.schemas import SourceCandidateRecord
from qinghai_rag.source_registry import normalize_domain

WHLYT_BASE_URL = "http://whlyt.qinghai.gov.cn"
WHLYT_SEARCH_URL = f"{WHLYT_BASE_URL}/search"
WHLYT_PUBLISHER = "青海省文化和旅游厅"


def _candidate_id(url: str) -> str:
    return "candidate_" + hashlib.sha256(url.encode()).hexdigest()[:12]


def _http_content_url(href: str) -> str:
    absolute = urljoin(WHLYT_BASE_URL, href)
    parsed = urlparse(absolute)
    return urlunparse(("http", "whlyt.qinghai.gov.cn", parsed.path, "", "", ""))


def inspect_whlyt_article(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    def meta(name: str) -> str:
        node = soup.find("meta", attrs={"name": name})
        return str(node.get("content") or "").strip() if node else ""

    content_source = meta("ContentSource")
    author = meta("Author") or meta("ArticleAuthor")
    body = soup.select_one(".app-content-body")
    body_text = body.get_text(" ", strip=True) if body else ""
    restriction_phrases = ["未经许可不得转载", "严禁转载", "禁止转载", "禁止复制"]
    matched_restrictions = [phrase for phrase in restriction_phrases if phrase in body_text]
    eligible_full_text = bool(
        body_text
        and content_source == WHLYT_PUBLISHER
        and not author
        and not matched_restrictions
    )
    reasons = []
    if not body_text:
        reasons.append("missing_article_body")
    if content_source != WHLYT_PUBLISHER:
        reasons.append("third_party_or_missing_content_source")
    if author:
        reasons.append("signed_article")
    if matched_restrictions:
        reasons.append("page_specific_restriction")
    return {
        "content_source": content_source,
        "author": author,
        "body_text": body_text,
        "matched_restrictions": matched_restrictions,
        "eligible_full_text": eligible_full_text,
        "reasons": reasons,
    }


def parse_whlyt_search_page(
    html: str,
    *,
    keyword: str = "非遗",
    category: str = "wldt",
    scope: str = "title",
    discovered_at: str | None = None,
) -> tuple[list[SourceCandidateRecord], dict[str, int]]:
    soup = BeautifulSoup(html, "lxml")
    total_text = soup.select_one(".search-info .total")
    total_match = re.search(r"[\d,]+", total_text.get_text(" ", strip=True)) if total_text else None
    reported_total = int(total_match.group().replace(",", "")) if total_match else 0

    pages = [1]
    for link in soup.select(".app-pagination a[href]"):
        query = parse_qs(urlparse(link.get("href", "")).query)
        if query.get("page"):
            pages.append(int(query["page"][0]))
    total_pages = max(pages)

    records: list[SourceCandidateRecord] = []
    for item in soup.select("a.app-article-item[href]"):
        title_node = item.select_one(".app-article-title")
        date_node = item.select_one(".app-article-date")
        title = title_node.get_text(" ", strip=True) if title_node else ""
        published_at = date_node.get_text(" ", strip=True) if date_node else ""
        if not title:
            continue
        url = _http_content_url(item.get("href", ""))
        path_match = re.fullmatch(r"/content/(\d+)", urlparse(url).path)
        url_content_id = path_match.group(1) if path_match else ""
        source_suffix = url_content_id or hashlib.sha256(url.encode()).hexdigest()[:12]
        records.append(
            SourceCandidateRecord(
                candidate_id=_candidate_id(url),
                source_id=f"src_whlyt_content_{source_suffix}",
                title=title,
                publisher=WHLYT_PUBLISHER,
                source_type="provincial_culture_tourism_department",
                url=url,
                domain=normalize_domain(url),
                region=["青海省"],
                topic=["非遗", "文旅动态"],
                license_status="government_public",
                release_policy="government_public",
                raw_text_release=True,
                discovery_method="whlyt_search",
                discovered_at=discovered_at or date.today().isoformat(),
                catalog_metadata={
                    "published_at": published_at,
                    "column_id": str(item.get("cid") or ""),
                    "search_content_id": str(item.get("contentid") or ""),
                    "url_content_id": url_content_id,
                    "keyword": keyword,
                    "category": category,
                    "scope": scope,
                },
                notes=(
                    "Official Qinghai culture-tourism search result. Maintainer confirmed full-text "
                    "republication permission with attribution. Every released chunk must state "
                    "'资料来源：青海省文化和旅游厅官网' and preserve the source URL. Third-party, "
                    "signed, or page-restricted content is downgraded after fetch. HTTPS certificate "
                    "was expired during review, so the official HTTP endpoint and content hash are recorded."
                ),
            )
        )
    deduplicated = {record.source_id: record for record in records}
    return list(deduplicated.values()), {
        "reported_total": reported_total,
        "total_pages": total_pages,
    }


def discover_whlyt_articles(
    *,
    keyword: str = "非遗",
    category: str = "wldt",
    scope: str = "title",
    time_filter: str = "all",
    timeout: float = 30.0,
    interval_seconds: float = 1.0,
    max_pages: int | None = None,
    session: requests.Session | None = None,
) -> tuple[list[SourceCandidateRecord], dict[str, int]]:
    client = session or requests.Session()
    if session is None:
        client.trust_env = False
    common: dict[str, Any] = {
        "keyword": keyword,
        "category": category,
        "scope": scope,
        "time": time_filter,
    }
    first = client.get(WHLYT_SEARCH_URL, params={**common, "page": 1}, timeout=timeout)
    first.raise_for_status()
    records, metadata = parse_whlyt_search_page(
        first.text, keyword=keyword, category=category, scope=scope
    )
    total_pages = metadata["total_pages"]
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)
    for page in range(2, total_pages + 1):
        if interval_seconds > 0:
            time.sleep(interval_seconds)
        response = client.get(
            WHLYT_SEARCH_URL, params={**common, "page": page}, timeout=timeout
        )
        response.raise_for_status()
        page_records, _ = parse_whlyt_search_page(
            response.text, keyword=keyword, category=category, scope=scope
        )
        records.extend(page_records)
    deduplicated = {record.source_id: record for record in records}
    metadata["fetched_pages"] = total_pages
    return sorted(deduplicated.values(), key=lambda item: item.source_id), metadata
