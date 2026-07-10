from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import SourceRecord


@dataclass(frozen=True)
class PolicyDecision:
    license_status: str
    release_policy: str
    raw_text_release: bool
    reason: str


def normalize_domain(url_or_domain: str) -> str:
    parsed = urlparse(url_or_domain if "://" in url_or_domain else f"https://{url_or_domain}")
    return (parsed.hostname or "").lower().removeprefix("www.")


def canonical_source_url(url: str) -> str:
    """Return a stable page identity used to prevent duplicate source records."""
    parsed = urlparse(url)
    domain = normalize_domain(url)
    path = re.sub(r"/+$", "", parsed.path) or "/"
    if domain == "ihchina.cn":
        match = re.fullmatch(r"(/project_details/\d+)(?:\.html)?", path)
        if match:
            path = match.group(1)
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return f"{domain}{path}" + (f"?{query}" if query else "")


def domain_matches(domain: str, candidates: list[str]) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in candidates)


def decide_release_policy(
    url: str,
    text: str = "",
    configured_license: str | None = None,
    configured_policy: str | None = None,
    config: dict | None = None,
) -> PolicyDecision:
    config = config or load_project_config("release_policy.yaml")
    domain = normalize_domain(url)
    restricted = config.get("restricted_domains", [])
    excluded = config.get("excluded_domains", [])
    restriction_phrases = config.get("strong_restriction_phrases", [])
    government = config.get("government_domains", [])

    if domain_matches(domain, excluded):
        return PolicyDecision("forbidden", "exclude", False, "domain is excluded")
    if domain_matches(domain, restricted):
        return PolicyDecision(
            "restricted", "metadata_and_facts_only", False, "domain is restricted"
        )
    matched_phrase = next((phrase for phrase in restriction_phrases if phrase in text), None)
    if matched_phrase:
        return PolicyDecision(
            "restricted",
            "metadata_and_facts_only",
            False,
            f"page contains restriction phrase: {matched_phrase}",
        )
    if configured_policy in {"local_only", "exclude", "metadata_and_facts_only"}:
        return PolicyDecision(
            configured_license or "unclear",
            configured_policy,
            False,
            "explicit conservative policy",
        )
    if domain_matches(domain, government) and configured_policy == "government_public":
        return PolicyDecision(
            "government_public", "government_public", True, "government page without override"
        )
    if configured_license == "open" and configured_policy == "full_text_allowed":
        return PolicyDecision("open", "full_text_allowed", True, "explicit open policy")
    defaults = config.get("defaults", {})
    return PolicyDecision(
        defaults.get("unknown_license_status", "unclear"),
        defaults.get("unknown_release_policy", "metadata_and_facts_only"),
        bool(defaults.get("unknown_raw_text_release", False)),
        "license could not be verified; conservative default applied",
    )


class SourceRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or PATHS.release / "qinghai_sources.jsonl")

    def records(self) -> list[SourceRecord]:
        return read_jsonl(self.path, SourceRecord)  # type: ignore[return-value]

    def by_id(self) -> dict[str, SourceRecord]:
        return {record.source_id: record for record in self.records()}

    def upsert(self, records: list[SourceRecord]) -> None:
        merged = self.by_id()
        url_owners = {
            canonical_source_url(record.url): record.source_id for record in merged.values()
        }
        for record in records:
            url_key = canonical_source_url(record.url)
            owner = url_owners.get(url_key)
            if owner is not None and owner != record.source_id:
                continue
            previous = merged.get(record.source_id)
            if previous is not None:
                url_owners.pop(canonical_source_url(previous.url), None)
            merged[record.source_id] = record
            url_owners[url_key] = record.source_id
        write_jsonl_atomic(self.path, merged.values(), sort_key="source_id")

    @staticmethod
    def stable_source_id(url: str) -> str:
        return "src_" + hashlib.sha256(url.encode()).hexdigest()[:12]

    @staticmethod
    def preserve_collection_state(
        configured: SourceRecord, existing: SourceRecord | None
    ) -> SourceRecord:
        if existing is None:
            return configured
        payload = configured.model_dump(mode="json")
        previous = existing.model_dump(mode="json")
        for field in ("retrieved_at", "crawl_status", "content_sha256"):
            payload[field] = previous[field]
        if existing.crawl_status.value != "pending":
            for field in (
                "title",
                "license_status",
                "release_policy",
                "raw_text_release",
                "notes",
            ):
                payload[field] = previous[field]
        return SourceRecord.model_validate(payload)

    @staticmethod
    def from_seed(seed: dict) -> SourceRecord:
        decision = decide_release_policy(
            seed["url"],
            configured_license=seed.get("license_status"),
            configured_policy=seed.get("release_policy"),
        )
        return SourceRecord(
            source_id=seed.get("source_id") or SourceRegistry.stable_source_id(seed["url"]),
            title=seed["title"],
            publisher=seed.get("publisher", ""),
            source_type=seed.get("source_type", "other"),
            url=seed["url"],
            domain=normalize_domain(seed["url"]),
            region=seed.get("region", []),
            topic=seed.get("topic", []),
            retrieved_at=date.today().isoformat(),
            license_status=decision.license_status,
            release_policy=decision.release_policy,
            raw_text_release=decision.raw_text_release,
            crawl_status="pending" if seed.get("enabled", True) else "skipped",
            notes="; ".join(filter(None, [seed.get("notes", ""), decision.reason])),
        )
