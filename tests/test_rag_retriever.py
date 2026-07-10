import networkx as nx

from qinghai_rag.rag.retriever import (
    EvidenceAllocator,
    GraphRetriever,
    HybridRetriever,
    _predicate_query_bonus,
    _select_graph_results,
    fuse_dense_sparse,
)


class FakeRetriever:
    def __init__(self, results):
        self.results = results

    def retrieve(self, query, top_k=5, **kwargs):
        return self.results[:top_k]


class FakeReranker:
    """Scores candidates by text length so the order is deterministic and observable."""

    def rerank(self, query, candidates, top_k=None):
        reranked = []
        for item in candidates:
            updated = dict(item)
            updated["retrieval_score"] = float(item.get("score", 0.0))
            updated["score"] = len(item.get("text", "")) / 100.0
            reranked.append(updated)
        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked[:top_k] if top_k else reranked


def test_hybrid_allocator_returns_traceable_evidence_and_diverse_sources():
    vector = FakeRetriever(
        [
            {
                "evidence_id": "c1",
                "source_id": "s1",
                "score": 0.9,
                "text": "土族盘绣与海东相关",
                "source_url": "https://a",
            },
            {
                "evidence_id": "c2",
                "source_id": "s1",
                "score": 0.8,
                "text": "盘绣项目",
                "source_url": "https://a",
            },
        ]
    )
    graph = FakeRetriever(
        [
            {
                "evidence_id": "f1",
                "source_id": "s2",
                "score": 0.7,
                "text": "土族盘绣 — located_in — 海东市",
                "source_url": "https://b",
                "confidence": "high",
            }
        ]
    )
    retriever = HybridRetriever(vector, graph, EvidenceAllocator())
    results = retriever.retrieve("土族盘绣在哪里", mode="hybrid", top_k=2, budget=2)
    assert len(results) == 2
    assert {item["source_id"] for item in results} == {"s1", "s2"}
    assert all(item["source_url"] for item in results)


def _chunk_result(evidence_id, score, text, source_id="s1"):
    return {
        "evidence_id": evidence_id,
        "chunk_id": evidence_id,
        "source_id": source_id,
        "score": score,
        "text": text,
        "source_url": "https://a",
        "kind": "vector",
    }


def test_fuse_dense_sparse_boosts_overlapping_candidates():
    dense = [
        _chunk_result("c1", 0.9, "土族盘绣与海东相关"),
        _chunk_result("c2", 0.6, "酥油花简介"),
    ]
    sparse = [
        {**_chunk_result("c1", 7.5, "土族盘绣与海东相关"), "kind": "bm25"},
        {**_chunk_result("c3", 3.0, "青海湖简介", source_id="s2"), "kind": "bm25"},
    ]
    fused = fuse_dense_sparse(dense, sparse, dense_weight=0.6, sparse_weight=0.4)
    by_id = {item["evidence_id"]: item for item in fused}
    assert by_id["c1"]["kind"] == "vector+bm25"
    assert by_id["c1"]["score"] == fused[0]["score"]  # overlap wins
    assert by_id["c1"]["score"] > by_id["c2"]["score"]
    assert by_id["c1"]["score"] > by_id["c3"]["score"]
    assert 0 <= by_id["c3"]["score"] <= 1


def test_bm25_only_mode_and_available_modes():
    bm25 = FakeRetriever([{**_chunk_result("c9", 4.2, "盘绣项目"), "kind": "bm25"}])
    retriever = HybridRetriever(None, None, bm25=bm25, reranker=FakeReranker())
    assert retriever.available_modes() == ["bm25-only", "bm25-only+rerank"]
    results = retriever.retrieve("盘绣", mode="bm25-only", top_k=3, budget=3)
    assert results and results[0]["kind"] == "bm25"


def test_rerank_suffix_reorders_and_preserves_retrieval_score():
    vector = FakeRetriever(
        [
            _chunk_result("c1", 0.9, "短文本"),
            _chunk_result("c2", 0.5, "这是一段明显更长的证据文本，应当被伪重排器排到最前面"),
        ]
    )
    retriever = HybridRetriever(vector, None, reranker=FakeReranker())
    results = retriever.retrieve("问题", mode="vector-only+rerank", top_k=2, budget=2)
    assert results[0]["evidence_id"] == "c2"
    assert results[0]["retrieval_score"] == 0.5
    plain = retriever.retrieve("问题", mode="vector-only", top_k=2, budget=2)
    assert plain[0]["evidence_id"] == "c1"


def test_hybrid_rerank_keeps_traceable_evidence():
    vector = FakeRetriever([_chunk_result("c1", 0.9, "土族盘绣与海东相关")])
    graph = FakeRetriever(
        [
            {
                "evidence_id": "f1",
                "source_id": "s2",
                "score": 0.7,
                "text": "土族盘绣 — located_in — 海东市，这条边来自事实图谱",
                "source_url": "https://b",
                "confidence": "high",
                "kind": "graph",
            }
        ]
    )
    retriever = HybridRetriever(vector, graph, reranker=FakeReranker())
    results = retriever.retrieve("土族盘绣在哪里", mode="hybrid+rerank", top_k=2, budget=2)
    assert len(results) == 2
    assert {item["source_id"] for item in results} == {"s1", "s2"}
    assert all(item["source_url"] for item in results)


def test_hybrid_rerank_reserves_graph_evidence_when_open_text_fills_budget():
    vector = FakeRetriever(
        [
            _chunk_result("c1", 0.9, "第一篇很长的正文证据" * 8, source_id="s1"),
            _chunk_result("c2", 0.8, "第二篇同样很长的正文证据" * 8, source_id="s2"),
            _chunk_result("c3", 0.7, "第三篇正文证据" * 8, source_id="s3"),
        ]
    )
    graph = FakeRetriever(
        [
            {
                "evidence_id": "f1",
                "source_id": "s4",
                "score": 0.9,
                "text": "海南州 — declared_by — 项目甲",
                "source_url": "https://b",
                "confidence": "high",
                "kind": "graph",
            },
            {
                "evidence_id": "f2",
                "source_id": "s5",
                "score": 0.4,
                "text": "项目甲 — inherited_by — 这是一条更长但不能回答申报地区问题的传承人事实",
                "source_url": "https://c",
                "confidence": "high",
                "kind": "graph",
            },
        ]
    )
    retriever = HybridRetriever(vector, graph, reranker=FakeReranker())

    results = retriever.retrieve("海南州申报了哪些项目", mode="hybrid+rerank", top_k=3, budget=2)

    assert len(results) == 2
    assert results[-1]["evidence_id"] == "f1"
    assert any(item["kind"] == "graph" for item in results)


def test_graph_matching_prefers_longest_overlapping_entity_mention():
    graph = nx.MultiDiGraph()
    graph.add_node("province", kind="entity", name="青海省", aliases=[])
    graph.add_node(
        "prefecture",
        kind="entity",
        name="青海省海南藏族自治州",
        aliases=["海南藏族自治州"],
    )
    graph.add_node("project", kind="entity", name="藏族拉伊", aliases=[])
    retriever = GraphRetriever.__new__(GraphRetriever)
    retriever.graph = graph

    matched = retriever._matched_nodes("青海省海南藏族自治州的藏族拉伊有哪些记录？")

    assert matched == ["prefecture", "project"]


def test_graph_predicate_bonus_tracks_explicit_query_intent():
    query = "青海省海北藏族自治州申报了哪些非遗项目？"

    assert _predicate_query_bonus(query, "declared_by") == 0.2
    assert _predicate_query_bonus(query, "inherited_by") == 0.0


def test_graph_selection_reserves_each_relation_requested_by_multi_hop_query():
    ranked = [
        {
            "evidence_id": "f1",
            "predicate": "inherited_by",
            "score": 1.0,
        },
        {
            "evidence_id": "f2",
            "predicate": "inherited_by",
            "score": 0.99,
        },
        {
            "evidence_id": "f3",
            "predicate": "declared_by",
            "score": 0.7,
        },
    ]

    selected = _select_graph_results(
        "热贡艺术的申报地区或单位和代表性传承人分别是什么？",
        ranked,
        top_k=2,
    )

    assert [item["evidence_id"] for item in selected] == ["f3", "f1"]
