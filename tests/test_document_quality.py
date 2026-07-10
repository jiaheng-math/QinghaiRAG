from qinghai_rag.document_quality import audit_document_quality
from qinghai_rag.schemas import SourceRecord


def _source(source_id: str, status: str = "parsed") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        title=source_id,
        publisher="贵德县人民政府",
        source_type="municipal_or_county_government",
        url=f"https://www.guide.gov.cn/{source_id}",
        domain="guide.gov.cn",
        retrieved_at="2026-07-10",
        release_policy="metadata_and_facts_only",
        crawl_status=status,
    )


def test_document_quality_dry_run_does_not_change_status():
    sources = [_source("src_guide_content_short"), _source("src_other")]
    documents = [
        {"source_id": "src_guide_content_short", "text": "短标题", "retrieved_at": "2026-07-10"},
        {"source_id": "src_other", "text": "外部" * 100, "retrieved_at": "2026-07-10"},
    ]

    updated, report = audit_document_quality(sources, documents, source_prefix="src_guide_content_")

    assert [source.crawl_status.value for source in updated] == ["parsed", "parsed"]
    assert report["selected_sources"] == 1
    assert report["shallow_sources"] == 1
    assert report["status_changes"] == 0
    assert report["applied"] is False


def test_document_quality_apply_marks_only_shallow_parsed_sources_as_fetched():
    sources = [
        _source("src_guide_content_short"),
        _source("src_guide_content_long"),
        _source("src_other"),
    ]
    documents = [
        {"source_id": "src_guide_content_short", "text": "短标题", "retrieved_at": "2026-07-10"},
        {"source_id": "src_guide_content_long", "text": "正文" * 100, "retrieved_at": "2026-07-10"},
        {"source_id": "src_other", "text": "短", "retrieved_at": "2026-07-10"},
    ]

    updated, report = audit_document_quality(
        sources,
        documents,
        source_prefix="src_guide_content_",
        minimum_chars=100,
        apply=True,
    )
    by_id = {source.source_id: source for source in updated}

    assert by_id["src_guide_content_short"].crawl_status.value == "fetched"
    assert by_id["src_guide_content_long"].crawl_status.value == "parsed"
    assert by_id["src_other"].crawl_status.value == "parsed"
    assert "cleaned_text_chars=3 below minimum=100" in by_id["src_guide_content_short"].notes
    assert report["qualified_sources"] == 1
    assert report["status_changes"] == 1
    assert report["applied"] is True


def test_document_quality_prefers_latest_document_per_source():
    source = _source("src_guide_content_1")
    documents = [
        {"source_id": source.source_id, "text": "旧" * 200, "retrieved_at": "2026-07-09"},
        {"source_id": source.source_id, "text": "新", "retrieved_at": "2026-07-10"},
    ]

    _, report = audit_document_quality([source], documents, minimum_chars=100)

    assert report["shallow_sources"] == 1
