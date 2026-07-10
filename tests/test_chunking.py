from qinghai_rag.chunking import build_open_chunks, build_synthetic_fact_chunks, split_text
from qinghai_rag.schemas import FactRecord, SourceRecord


def test_chinese_chunking_preserves_offsets_and_overlap():
    text = "第一句内容。第二句内容较长。第三句内容。第四句内容。"
    chunks = split_text(text, chunk_size_chars=15, overlap_chars=4)
    assert len(chunks) >= 2
    for start, end, value in chunks:
        assert text[start:end] == value
        assert len(value) <= 15
    assert chunks[1][0] < chunks[0][1]


def test_chunking_finishes_at_text_end_without_repeating_last_punctuation():
    text = "前段内容。" * 80 + "这是没有句号的正文尾部" * 20
    chunks = split_text(text, chunk_size_chars=120, overlap_chars=20)

    assert chunks[-1][1] == len(text)
    assert all(left[0] < right[0] for left, right in zip(chunks, chunks[1:]))
    assert len(chunks) <= 12


def test_restricted_source_never_builds_open_text_chunk():
    source = SourceRecord(
        source_id="src_restricted",
        title="限制来源",
        url="https://restricted.example/a",
        domain="restricted.example",
        retrieved_at="2026-07-10",
        license_status="restricted",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        crawl_status="parsed",
    )
    document = {"doc_id": "doc_1", "source_id": source.source_id, "text": "不应发布。"}
    assert build_open_chunks([document], {source.source_id: source}, []) == []


def test_synthetic_fact_chunk_uses_readable_chinese_relations():
    source = SourceRecord(
        source_id="src_official",
        title="官方名录",
        url="https://gov.example/a",
        domain="gov.example",
        retrieved_at="2026-07-10",
        release_policy="metadata_and_facts_only",
        raw_text_release=False,
        crawl_status="parsed",
    )
    facts = [
        FactRecord(
            fact_id="fact_1",
            subject="热贡艺术",
            subject_type="ICH_PROJECT",
            predicate="belongs_to_category",
            object="传统美术",
            object_type="CATEGORY",
            evidence_source_id=source.source_id,
            evidence_url=source.url,
            extraction_method="table_parse",
            verified=True,
            confidence="high",
        ),
        FactRecord(
            fact_id="fact_2",
            subject="热贡艺术",
            subject_type="ICH_PROJECT",
            predicate="declared_by",
            object="青海省同仁县",
            object_type="REGION",
            evidence_source_id=source.source_id,
            evidence_url=source.url,
            extraction_method="table_parse",
            verified=True,
            confidence="medium",
        ),
    ]
    [chunk] = build_synthetic_fact_chunks(facts, {source.source_id: source})
    assert "所属类别为“传统美术”" in chunk.text
    assert "申报地区或单位为“青海省同仁县”" in chunk.text
    assert "belongs_to_category" not in chunk.text
    assert "declared_by" not in chunk.text
