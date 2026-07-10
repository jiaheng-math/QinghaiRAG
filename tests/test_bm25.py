import pytest

from qinghai_rag.rag.bm25 import BM25Index, BM25Retriever, tokenize
from qinghai_rag.schemas import ChunkRecord


def make_chunk(chunk_id: str, text: str, source_id: str = "s1") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        doc_id="doc1",
        source_id=source_id,
        text=text,
        char_start=0,
        char_end=len(text),
        license_status="open",
        release_policy="full_text_allowed",
        source_url="https://example.org/page",
        retrieved_at="2026-01-01",
    )


CHUNKS = [
    make_chunk("c1", "塔尔寺酥油花是青海省著名的传统美术类非遗项目。"),
    make_chunk("c2", "土族盘绣流传于海东市互助土族自治县。", source_id="s2"),
    make_chunk("c3", "青海湖是中国最大的内陆咸水湖。", source_id="s3"),
]


def test_bm25_index_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        BM25Index(k1=0)
    with pytest.raises(ValueError):
        BM25Index(b=1.5)


def test_tokenize_splits_chinese_terms():
    tokens = tokenize("塔尔寺酥油花属于传统美术")
    assert "酥油花" in tokens or "酥油" in tokens


def test_bm25_retriever_ranks_matching_chunk_first():
    retriever = BM25Retriever(chunks=CHUNKS)
    results = retriever.retrieve("酥油花属于哪一类别", top_k=3)
    assert results
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["kind"] == "bm25"
    assert results[0]["score"] > 0
    assert results[0]["source_url"] == "https://example.org/page"


def test_bm25_retriever_empty_query_and_no_match():
    retriever = BM25Retriever(chunks=CHUNKS)
    assert retriever.retrieve("  ") == []
    assert retriever.retrieve("firefox浏览器下载安装") == []


def test_bm25_scores_descend():
    retriever = BM25Retriever(chunks=CHUNKS)
    results = retriever.retrieve("青海省的非遗项目盘绣", top_k=3)
    scores = [item["score"] for item in results]
    assert scores == sorted(scores, reverse=True)
