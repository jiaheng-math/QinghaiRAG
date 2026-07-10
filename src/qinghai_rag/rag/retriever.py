from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.graph_builder import load_graph
from qinghai_rag.io_utils import read_json, read_jsonl
from qinghai_rag.rag.embeddings import EmbeddingConfig, SentenceTransformerEncoder
from qinghai_rag.schemas import ChunkRecord, FactRecord, SourceRecord


def _query_overlap(query: str, text: str) -> float:
    chars = {char for char in query if re.match(r"[\w\u4e00-\u9fff]", char)}
    return len(chars & set(text)) / max(len(chars), 1)


_PREDICATE_QUERY_CUES = {
    "declared_by": ("申报", "申报方", "申报地区", "申报单位"),
    "belongs_to_category": ("类别", "分类", "哪一类", "属于"),
    "inherited_by": ("传承人", "传承者", "谁传承"),
    "associated_with_ethnic_group": ("民族", "族群"),
    "has_level": ("级别", "等级", "国家级"),
    "held_by": ("馆藏", "收藏", "哪个馆", "博物馆"),
    "created_in_period": ("年代", "时期", "朝代"),
    "made_of": ("质地", "材质", "材料", "制成"),
    "located_in": ("位于", "所在地", "哪里"),
}


def _predicate_query_bonus(query: str, predicate: str) -> float:
    return 0.2 if any(cue in query for cue in _PREDICATE_QUERY_CUES.get(predicate, ())) else 0.0


def _requested_predicates(query: str) -> list[str]:
    matches = []
    for order, (predicate, cues) in enumerate(_PREDICATE_QUERY_CUES.items()):
        positions = [query.find(cue) for cue in cues if cue in query]
        if positions:
            matches.append((min(positions), order, predicate))
    return [predicate for _, _, predicate in sorted(matches)]


def _select_graph_results(
    query: str, ranked: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    """Reserve one graph fact for each relation explicitly requested by the query."""
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for predicate in _requested_predicates(query):
        candidate = next(
            (item for item in ranked if item.get("predicate") == predicate),
            None,
        )
        if candidate and candidate["evidence_id"] not in selected_ids:
            selected.append(candidate)
            selected_ids.add(candidate["evidence_id"])
    for item in ranked:
        if len(selected) >= top_k:
            break
        if item["evidence_id"] not in selected_ids:
            selected.append(item)
            selected_ids.add(item["evidence_id"])
    return selected[:top_k]


class VectorRetriever:
    def __init__(
        self,
        index_path: str | Path | None = None,
        metadata_path: str | Path | None = None,
        manifest_path: str | Path | None = None,
        encoder: SentenceTransformerEncoder | None = None,
        device: str | None = None,
    ):
        import faiss

        self.index_path = Path(index_path or PATHS.cache / "faiss.index")
        self.metadata_path = Path(metadata_path or PATHS.cache / "faiss_metadata.jsonl")
        self.manifest = read_json(manifest_path or PATHS.cache / "faiss_manifest.json", {})
        self.metadata = read_jsonl(self.metadata_path, ChunkRecord)
        self.index = faiss.read_index(str(self.index_path))
        config = load_project_config("rag.yaml")
        embedding = EmbeddingConfig(**config.get("embedding", {}))
        if self.manifest.get("model_name"):
            embedding.model_name = self.manifest["model_name"]
        if device:
            embedding.device = device
        self.encoder = encoder or SentenceTransformerEncoder(embedding)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query.strip() or not self.metadata:
            return []
        vector = self.encoder.encode([query])
        scores, indices = self.index.search(vector, min(top_k, len(self.metadata)))
        results = []
        for score, index in zip(scores[0], indices[0]):
            if index < 0:
                continue
            chunk = self.metadata[int(index)]
            results.append(
                {
                    "evidence_id": chunk.chunk_id,
                    "chunk_id": chunk.chunk_id,
                    "fact_id": None,
                    "source_id": chunk.source_id,
                    "score": float(score),
                    "text": chunk.text,
                    "source_url": chunk.source_url,
                    "kind": "vector",
                }
            )
        return results


class GraphRetriever:
    def __init__(
        self,
        graph_path: str | Path | None = None,
        facts_path: str | Path | None = None,
        sources_path: str | Path | None = None,
    ):
        self.graph = load_graph(graph_path or PATHS.cache / "qinghai_graph.json")
        self.facts = {
            fact.fact_id: fact
            for fact in read_jsonl(facts_path or PATHS.release / "qinghai_facts.jsonl", FactRecord)
        }
        self.sources = {
            source.source_id: source
            for source in read_jsonl(
                sources_path or PATHS.release / "qinghai_sources.jsonl", SourceRecord
            )
        }

    def _matched_nodes(self, query: str) -> list[str]:
        matches: list[tuple[str, str]] = []
        for node, data in self.graph.nodes(data=True):
            if data.get("kind") != "entity":
                continue
            names = [data.get("name", ""), *data.get("aliases", [])]
            matched_names = [name for name in names if name and name in query]
            if matched_names:
                matches.append((node, max(matched_names, key=len)))
        # Prefer the most specific overlapping mention. For example, a query
        # containing “青海省海南藏族自治州” also contains “青海省”; expanding from
        # both nodes floods the graph results with province-wide facts. Keep
        # disjoint mentions so comparison and multi-entity queries still work.
        maximal = [
            (node, mention)
            for node, mention in matches
            if not any(
                mention != other_mention and mention in other_mention
                for _, other_mention in matches
            )
        ]
        return [node for node, _ in maximal]

    def retrieve(self, query: str, top_k: int = 10, hops: int = 2) -> list[dict[str, Any]]:
        matched = self._matched_nodes(query)
        if not matched:
            return []
        distances: dict[str, int] = {}
        frontier = set(matched)
        visited = set(matched)
        for distance in range(hops + 1):
            for node in frontier:
                distances[node] = min(distance, distances.get(node, distance))
            next_frontier = set()
            for node in frontier:
                next_frontier.update(self.graph.successors(node))
                next_frontier.update(self.graph.predecessors(node))
            frontier = next_frontier - visited
            visited |= frontier
        results: dict[str, dict[str, Any]] = {}
        for left, right, data in self.graph.edges(data=True):
            fact_id = data.get("fact_id")
            fact = self.facts.get(fact_id)
            if not fact or (left not in visited and right not in visited):
                continue
            proximity = 1.0 / (
                1 + min(distances.get(left, hops + 1), distances.get(right, hops + 1))
            )
            confidence = {"high": 1.0, "medium": 0.75, "low": 0.4}.get(fact.confidence, 0.5)
            text = f"{fact.subject} — {fact.predicate} — {fact.object}"
            score = min(
                1.0,
                0.5 * proximity
                + 0.3 * confidence
                + 0.2 * _query_overlap(query, text)
                + _predicate_query_bonus(query, fact.predicate),
            )
            source = self.sources.get(fact.evidence_source_id)
            results[fact.fact_id] = {
                "evidence_id": fact.fact_id,
                "chunk_id": None,
                "fact_id": fact.fact_id,
                "source_id": fact.evidence_source_id,
                "score": score,
                "text": text,
                "source_url": fact.evidence_url,
                "source_title": source.title if source else fact.evidence_source_id,
                "kind": "graph",
                "predicate": fact.predicate,
                "confidence": fact.confidence,
            }
        ranked = sorted(results.values(), key=lambda item: item["score"], reverse=True)
        return _select_graph_results(query, ranked, top_k)


class EvidenceAllocator:
    def allocate(
        self,
        query: str,
        vector_results: list[dict[str, Any]],
        graph_results: list[dict[str, Any]],
        budget: int,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        graph_evidence_ids = {
            item.get("evidence_id") or f"{item['source_id']}:{item['text']}"
            for item in graph_results
        }
        for item in [*vector_results, *graph_results]:
            key = item.get("evidence_id") or f"{item['source_id']}:{item['text']}"
            candidate = dict(item)
            candidate["allocation_score"] = (
                float(item.get("score", 0))
                + 0.2 * _query_overlap(query, item.get("text", ""))
                + ({"high": 0.15, "medium": 0.08}.get(item.get("confidence"), 0))
            )
            if key not in merged or candidate["allocation_score"] > merged[key]["allocation_score"]:
                merged[key] = candidate
        ranked = sorted(merged.values(), key=lambda item: item["allocation_score"], reverse=True)
        selected, per_source = [], defaultdict(int)
        while ranked and len(selected) < budget:
            ranked.sort(key=lambda item: (per_source[item["source_id"]], -item["allocation_score"]))
            chosen = ranked.pop(0)
            selected.append(chosen)
            per_source[chosen["source_id"]] += 1
        # A hybrid result should retain at least one traceable graph fact when
        # entity matching produced graph candidates. Long open-text passages
        # can otherwise occupy the entire evidence budget after cross-encoder
        # reranking, which breaks structured regional and aggregation queries.
        # Preserve the existing order and replace only the final result.
        if budget > 1 and graph_evidence_ids:
            selected_ids = {
                item.get("evidence_id") or f"{item['source_id']}:{item['text']}"
                for item in selected
            }
            if not selected_ids & graph_evidence_ids:
                best_graph = max(
                    (item for key, item in merged.items() if key in graph_evidence_ids),
                    key=lambda item: (
                        float(item.get("retrieval_score", item["allocation_score"])),
                        item["allocation_score"],
                    ),
                )
                if len(selected) < budget:
                    selected.append(best_graph)
                elif selected:
                    selected[-1] = best_graph
        return selected


def _max_normalized(results: list[dict[str, Any]]) -> dict[str, float]:
    """Map each result list into (0, 1] by its top positive score, keeping ratios."""
    positive = [max(float(item.get("score", 0.0)), 0.0) for item in results]
    top = max(positive, default=0.0)
    if top <= 0:
        return {item["evidence_id"]: 1.0 for item in results}
    return {item["evidence_id"]: value / top for item, value in zip(results, positive) if value > 0}


def fuse_dense_sparse(
    dense: list[dict[str, Any]],
    sparse: list[dict[str, Any]],
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> list[dict[str, Any]]:
    """Weighted fusion of dense and BM25 chunk candidates on normalized scores."""
    dense_norm = _max_normalized(dense)
    sparse_norm = _max_normalized(sparse)
    fused: dict[str, dict[str, Any]] = {}
    for item in [*dense, *sparse]:
        key = item["evidence_id"]
        if key not in fused:
            fused[key] = dict(item)
    for key, item in fused.items():
        in_dense, in_sparse = key in dense_norm, key in sparse_norm
        item["dense_score"] = dense_norm.get(key, 0.0)
        item["sparse_score"] = sparse_norm.get(key, 0.0)
        item["score"] = dense_weight * item["dense_score"] + sparse_weight * item["sparse_score"]
        if in_dense and in_sparse:
            item["kind"] = "vector+bm25"
    return sorted(fused.values(), key=lambda item: item["score"], reverse=True)


class HybridRetriever:
    BASE_MODES = ("vector-only", "bm25-only", "graph-only", "hybrid")

    def __init__(
        self,
        vector: VectorRetriever | None,
        graph: GraphRetriever | None,
        allocator: EvidenceAllocator | None = None,
        bm25: Any | None = None,
        reranker: Any | None = None,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
    ):
        self.vector = vector
        self.graph = graph
        self.bm25 = bm25
        self.reranker = reranker
        self.allocator = allocator or EvidenceAllocator()
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

    def available_modes(self, include_rerank: bool | None = None) -> list[str]:
        modes = []
        if self.vector:
            modes.append("vector-only")
        if self.bm25:
            modes.append("bm25-only")
        if self.graph:
            modes.append("graph-only")
        if len(modes) >= 2:
            modes.append("hybrid")
        if include_rerank if include_rerank is not None else bool(self.reranker):
            modes.extend(f"{mode}+rerank" for mode in list(modes))
        return modes

    def retrieve(
        self, query: str, mode: str = "hybrid", top_k: int = 5, budget: int = 10
    ) -> list[dict[str, Any]]:
        base_mode, _, suffix = mode.partition("+")
        rerank = suffix == "rerank" and self.reranker is not None
        vector_results = (
            self.vector.retrieve(query, top_k=top_k)
            if self.vector and base_mode in {"vector-only", "hybrid"}
            else []
        )
        bm25_results = (
            self.bm25.retrieve(query, top_k=top_k)
            if self.bm25 and base_mode in {"bm25-only", "hybrid"}
            else []
        )
        graph_results = (
            self.graph.retrieve(query, top_k=max(top_k, 10))
            if self.graph and base_mode in {"graph-only", "hybrid"}
            else []
        )
        if base_mode == "vector-only":
            results = vector_results
        elif base_mode == "bm25-only":
            results = bm25_results
        elif base_mode == "graph-only":
            results = graph_results[:budget]
        else:
            chunk_results = fuse_dense_sparse(
                vector_results, bm25_results, self.dense_weight, self.sparse_weight
            )
            if rerank:
                candidates = self.reranker.rerank(query, [*chunk_results, *graph_results])
                graph_evidence_ids = {item["evidence_id"] for item in graph_results}
                reranked_graph = [
                    item for item in candidates if item["evidence_id"] in graph_evidence_ids
                ]
                reranked_chunks = [
                    item for item in candidates if item["evidence_id"] not in graph_evidence_ids
                ]
                return self.allocator.allocate(query, reranked_chunks, reranked_graph, budget)
            return self.allocator.allocate(query, chunk_results, graph_results, budget)
        if rerank:
            results = self.reranker.rerank(query, results, top_k=budget)
        return results


def build_hybrid_retriever(
    device: str | None = None, rerank: bool | None = None
) -> HybridRetriever:
    """Assemble every retriever whose artifacts exist on disk, per configs/rag.yaml."""
    config = load_project_config("rag.yaml")
    retrieval = config.get("retrieval", {})
    sparse_config = config.get("sparse", {})
    vector = VectorRetriever(device=device) if (PATHS.cache / "faiss.index").exists() else None
    graph = GraphRetriever() if (PATHS.cache / "qinghai_graph.json").exists() else None
    bm25 = None
    chunks_path = PATHS.release / "qinghai_chunks_open.jsonl"
    if sparse_config.get("enabled", True) and chunks_path.exists():
        from qinghai_rag.rag.bm25 import BM25Retriever

        bm25 = BM25Retriever(
            chunks_path,
            k1=float(sparse_config.get("k1", 1.5)),
            b=float(sparse_config.get("b", 0.75)),
        )
    reranker = None
    reranker_config = config.get("reranker", {})
    if rerank if rerank is not None else reranker_config.get("enabled", False):
        from qinghai_rag.rag.reranker import CrossEncoderReranker, RerankerConfig

        options = {
            key: reranker_config[key]
            for key in ("model_name", "device", "batch_size", "max_length")
            if key in reranker_config
        }
        if device:
            options["device"] = device
        reranker = CrossEncoderReranker(RerankerConfig(**options))
    return HybridRetriever(
        vector,
        graph,
        bm25=bm25,
        reranker=reranker,
        dense_weight=float(retrieval.get("dense_weight", 0.6)),
        sparse_weight=float(retrieval.get("sparse_weight", 0.4)),
    )
