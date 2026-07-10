from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
import unicodedata
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from qinghai_rag.schemas import SourceCandidateRecord
from qinghai_rag.source_registry import normalize_domain

GUIDE_BASE_URL = "https://www.guide.gov.cn"
GUIDE_TOURISM_BASE = f"{GUIDE_BASE_URL}/gdly"
GUIDE_PUBLISHER = "贵德县人民政府"
GUIDE_SECTIONS = {
    "wlzx": ("文旅资讯", ["文旅动态"]),
    "yxgd": ("印象贵德", ["景区与文化地点"]),
    "jqjd": ("景区景点", ["景区与文化地点"]),
    "tscp": ("特色产品", ["特色文旅产品"]),
    "tsms": ("特色美食", ["地方饮食文化"]),
    "gdzs": ("贵德住宿", ["旅游服务"]),
}


def guide_user_agent(contact: str | None = None) -> str:
    maintainer = contact or os.getenv("QINGHAI_RAG_CONTACT") or "contact-not-configured"
    return (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        f"QinghaiRAG/0.1 (+{maintainer}; provenance-first research crawler)"
    )


def guide_section_page_url(section: str, page: int) -> str:
    if section not in GUIDE_SECTIONS:
        raise ValueError(f"Unknown Guide tourism section: {section}")
    if page <= 0:
        raise ValueError("page must be positive")
    suffix = "" if page == 1 else f"_{page}"
    return f"{GUIDE_TOURISM_BASE}/{section}{suffix}"


def _candidate_id(url: str) -> str:
    return "candidate_" + hashlib.sha256(url.encode()).hexdigest()[:12]


def _canonical_guide_url(href: str) -> str:
    parsed = urlparse(urljoin(GUIDE_BASE_URL, href))
    return urlunparse(("https", "www.guide.gov.cn", parsed.path, "", "", ""))


def _title_key(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split())


def _article_metadata(node: Any) -> tuple[str, str]:
    title_attribute = str(node.get("title") or "")
    title_match = re.search(r"标题：(.*?)(?:点击数：|发表时间：|$)", title_attribute, re.S)
    date_match = re.search(r"发表时间：([^\r\n]+)", title_attribute)
    title = title_match.group(1).strip() if title_match else node.get_text(" ", strip=True)
    published_at = date_match.group(1).strip() if date_match else ""
    return title, published_at


def _topics_for_article(section: str, title: str) -> list[str]:
    topics = list(GUIDE_SECTIONS[section][1])
    keyword_topics = {
        "非遗": ["非遗", "非物质文化遗产"],
        "民族文化": ["民族", "藏族", "回族", "土族", "蒙古族", "撒拉族"],
        "景区与文化地点": ["景区", "景点", "旅游线路", "公园", "古城", "遗址", "寺"],
        "博物馆与文化场馆": ["博物馆", "文化馆", "展览馆", "非遗馆", "保护中心"],
        "生态旅游": ["生态", "湿地", "地质公园", "自然保护区", "黄河", "青海湖"],
        "文旅政策": ["政策", "规划", "条例", "办法", "通知", "公示", "实施方案"],
    }
    for topic, keywords in keyword_topics.items():
        if any(keyword in title for keyword in keywords):
            topics.append(topic)
    return list(dict.fromkeys(topics))


def parse_guide_tourism_page(
    html: str,
    *,
    section: str,
    discovered_at: str | None = None,
) -> tuple[list[SourceCandidateRecord], dict[str, int]]:
    if section not in GUIDE_SECTIONS:
        raise ValueError(f"Unknown Guide tourism section: {section}")
    soup = BeautifulSoup(html, "lxml")
    total_text = soup.select_one(".page .total")
    total_match = (
        re.search(
            r"共\s*(\d+)\s*条信息\s*/\s*共\s*(\d+)\s*页", total_text.get_text(" ", strip=True)
        )
        if total_text
        else None
    )
    reported_total = int(total_match.group(1)) if total_match else 0
    total_pages = int(total_match.group(2)) if total_match else 1
    section_name = GUIDE_SECTIONS[section][0]

    records: list[SourceCandidateRecord] = []
    for node in soup.select(f'a[href*="/gdly/{section}/content_"]'):
        url = _canonical_guide_url(str(node.get("href") or ""))
        if normalize_domain(url) != "guide.gov.cn":
            continue
        content_match = re.search(r"/content_(\d+)$", urlparse(url).path)
        if not content_match:
            continue
        title, published_at = _article_metadata(node)
        if not title:
            continue
        content_id = content_match.group(1)
        records.append(
            SourceCandidateRecord(
                candidate_id=_candidate_id(url),
                source_id=f"src_guide_content_{content_id}",
                title=title,
                publisher=GUIDE_PUBLISHER,
                source_type="municipal_or_county_government",
                url=url,
                domain=normalize_domain(url),
                region=["青海省", "海南藏族自治州", "贵德县"],
                topic=_topics_for_article(section, title),
                license_status="unclear",
                release_policy="metadata_and_facts_only",
                raw_text_release=False,
                discovery_method="guide_tourism",
                discovered_at=discovered_at or date.today().isoformat(),
                catalog_metadata={
                    "content_id": content_id,
                    "section": section,
                    "section_name": section_name,
                    "published_at": published_at,
                },
                notes=(
                    "Discovered from the official Guide County all-for-one tourism portal; "
                    "conservative metadata-and-facts-only policy pending page-level source and "
                    "reuse review. Site publisher does not imply authorship of every hosted article."
                ),
            )
        )
    deduplicated = {record.source_id: record for record in records}
    return sorted(deduplicated.values(), key=lambda item: item.source_id), {
        "reported_total": reported_total,
        "total_pages": total_pages,
    }


def deduplicate_guide_candidates(
    records: list[SourceCandidateRecord],
) -> list[SourceCandidateRecord]:
    by_source = {record.source_id: record for record in records}
    by_title: dict[str, SourceCandidateRecord] = {}
    for record in by_source.values():
        key = _title_key(record.title)
        current = by_title.get(key)
        if current is None:
            by_title[key] = record
            continue
        candidate_priority = (record.catalog_metadata.get("published_at", ""), record.url)
        current_priority = (current.catalog_metadata.get("published_at", ""), current.url)
        if candidate_priority > current_priority:
            by_title[key] = record
    return sorted(by_title.values(), key=lambda item: item.source_id)


def _curl_fetcher(
    *, timeout: float, contact: str | None, no_env_proxy: bool
) -> Callable[[str], str]:
    def fetch(url: str) -> str:
        command = [
            "curl",
            "-4",
            "--http1.1",
            "-L",
            "-sS",
            "--retry",
            "3",
            "--retry-all-errors",
            "--retry-delay",
            "2",
            "--max-time",
            str(timeout),
            "--user-agent",
            guide_user_agent(contact),
        ]
        if no_env_proxy:
            command.extend(["--noproxy", "*"])
        command.append(url)
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode:
            error = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"curl failed for {url}: {error}")
        return result.stdout.decode("utf-8", errors="replace")

    return fetch


def _requests_fetcher(
    *, timeout: float, contact: str | None, no_env_proxy: bool
) -> Callable[[str], str]:
    client = requests.Session()
    client.trust_env = not no_env_proxy
    client.headers.update(
        {
            "User-Agent": guide_user_agent(contact),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": GUIDE_TOURISM_BASE,
        }
    )

    def fetch(url: str) -> str:
        response = client.get(url, timeout=timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text

    return fetch


def discover_guide_tourism(
    *,
    sections: list[str] | None = None,
    timeout: float = 30.0,
    interval_seconds: float = 1.0,
    max_pages: int | None = None,
    contact: str | None = None,
    no_env_proxy: bool = False,
    transport: str = "requests",
    fetch_html: Callable[[str], str] | None = None,
) -> tuple[list[SourceCandidateRecord], dict[str, Any]]:
    selected_sections = sections or list(GUIDE_SECTIONS)
    unknown = [section for section in selected_sections if section not in GUIDE_SECTIONS]
    if unknown:
        raise ValueError(f"Unknown Guide tourism sections: {', '.join(unknown)}")
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be positive")
    if fetch_html is None:
        if transport == "curl":
            fetch_html = _curl_fetcher(timeout=timeout, contact=contact, no_env_proxy=no_env_proxy)
        elif transport == "requests":
            fetch_html = _requests_fetcher(
                timeout=timeout, contact=contact, no_env_proxy=no_env_proxy
            )
        else:
            raise ValueError("transport must be 'requests' or 'curl'")

    records: list[SourceCandidateRecord] = []
    section_report: dict[str, dict[str, int]] = {}
    fetched_pages = 0
    for section in selected_sections:
        first_url = guide_section_page_url(section, 1)
        first_html = fetch_html(first_url)
        page_records, metadata = parse_guide_tourism_page(first_html, section=section)
        records.extend(page_records)
        total_pages = metadata["total_pages"]
        pages_to_fetch = min(total_pages, max_pages) if max_pages is not None else total_pages
        for page in range(2, pages_to_fetch + 1):
            if interval_seconds > 0:
                time.sleep(interval_seconds)
            page_html = fetch_html(guide_section_page_url(section, page))
            discovered, _ = parse_guide_tourism_page(page_html, section=section)
            records.extend(discovered)
        fetched_pages += pages_to_fetch
        section_report[section] = {
            "reported_total": metadata["reported_total"],
            "total_pages": total_pages,
            "fetched_pages": pages_to_fetch,
        }

    unique_by_source = {record.source_id: record for record in records}
    unique_records = deduplicate_guide_candidates(list(unique_by_source.values()))
    return unique_records, {
        "reported_total": sum(item["reported_total"] for item in section_report.values()),
        "total_pages": sum(item["total_pages"] for item in section_report.values()),
        "fetched_pages": fetched_pages,
        "deduplicated_titles": len(unique_by_source) - len(unique_records),
        "sections": section_report,
    }
