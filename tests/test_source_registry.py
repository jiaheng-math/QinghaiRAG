from qinghai_rag.schemas import SourceRecord
from qinghai_rag.source_registry import SourceRegistry, canonical_source_url


def _source(source_id: str, url: str, title: str = "项目") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        title=title,
        publisher="中国非物质文化遗产网",
        source_type="national_official_database",
        url=url,
        domain="ihchina.cn",
        retrieved_at="2026-07-10",
        license_status="unclear",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        crawl_status="pending",
    )


def test_ihchina_detail_url_variants_have_one_canonical_identity():
    assert canonical_source_url(
        "https://www.ihchina.cn/project_details/14054/"
    ) == canonical_source_url("https://www.ihchina.cn/project_details/14054.html")


def test_registry_preserves_existing_reviewed_source_when_url_is_rediscovered(tmp_path):
    registry = SourceRegistry(tmp_path / "sources.jsonl")
    existing = _source(
        "src_real_000002", "https://www.ihchina.cn/project_details/14054/", "人工来源"
    )
    rediscovered = _source(
        "src_ihchina_14054",
        "https://www.ihchina.cn/project_details/14054.html",
        "批量候选",
    )
    registry.upsert([existing])
    registry.upsert([rediscovered])

    assert registry.records() == [existing]


def test_registry_still_updates_the_same_source_id(tmp_path):
    registry = SourceRegistry(tmp_path / "sources.jsonl")
    registry.upsert([_source("src_1", "https://www.ihchina.cn/project_details/1.html")])
    registry.upsert(
        [_source("src_1", "https://www.ihchina.cn/project_details/1.html", "更新标题")]
    )

    [record] = registry.records()
    assert record.title == "更新标题"


def test_seed_refresh_preserves_completed_collection_state():
    configured = _source(
        "src_1", "https://www.ihchina.cn/project_details/1.html", "配置标题"
    )
    existing_payload = configured.model_dump(mode="json")
    existing_payload.update(
        {
            "title": "抓取后的标题",
            "retrieved_at": "2026-07-09",
            "crawl_status": "parsed",
            "content_sha256": "abc123",
            "license_status": "restricted",
            "notes": "抓取后的保守策略",
        }
    )
    existing = SourceRecord.model_validate(existing_payload)

    refreshed = SourceRegistry.preserve_collection_state(configured, existing)

    assert refreshed.title == "抓取后的标题"
    assert refreshed.retrieved_at == "2026-07-09"
    assert refreshed.crawl_status.value == "parsed"
    assert refreshed.content_sha256 == "abc123"
    assert refreshed.license_status.value == "restricted"
    assert refreshed.notes == "抓取后的保守策略"
