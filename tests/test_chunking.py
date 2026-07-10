from qinghai_rag.chunking import build_open_chunks, split_text
from qinghai_rag.schemas import SourceRecord


def test_chinese_chunking_preserves_offsets_and_overlap():
    text = "第一句内容。第二句内容较长。第三句内容。第四句内容。"
    chunks = split_text(text, chunk_size_chars=15, overlap_chars=4)
    assert len(chunks) >= 2
    for start, end, value in chunks:
        assert text[start:end] == value
        assert len(value) <= 15
    assert chunks[1][0] < chunks[0][1]


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
