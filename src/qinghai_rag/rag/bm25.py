from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import ChunkRecord

_TOKEN_RE = re.compile(r"[\w一-鿿]+")


def tokenize(text: str) -> list[str]:
    """Chinese-aware search tokenization backed by jieba."""
    import jieba

    tokens = []
    for span in _TOKEN_RE.findall(text.lower()):
        tokens.extend(token for token in jieba.cut_for_search(span) if token.strip())
    return tokens


class BM25Index:
    """In-memory Okapi BM25 over pre-tokenized documents."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("Require k1 > 0 and 0 <= b <= 1")
        self.k1 = k1
        self.b = b
        self.doc_frequencies: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        self.idf: dict[str, float] = {}
        self.average_length = 0.0

    def build(self, documents: Sequence[Sequence[str]]) -> "BM25Index":
        self.doc_frequencies = [Counter(tokens) for tokens in documents]
        self.doc_lengths = [sum(freq.values()) for freq in self.doc_frequencies]
        total = len(self.doc_frequencies)
        self.average_length = (sum(self.doc_lengths) / total) if total else 0.0
        document_frequency: Counter[str] = Counter()
        for freq in self.doc_frequencies:
            document_frequency.update(freq.keys())
        self.idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }
        return self

    def search(self, query_tokens: Sequence[str], top_k: int = 5) -> list[tuple[int, float]]:
        if not query_tokens or not self.doc_frequencies:
            return []
        scores = [0.0] * len(self.doc_frequencies)
        for term in query_tokens:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for position, freq in enumerate(self.doc_frequencies):
                occurrences = freq.get(term, 0)
                if not occurrences:
                    continue
                length_norm = 1 - self.b + self.b * (
                    self.doc_lengths[position] / max(self.average_length, 1e-9)
                )
                scores[position] += (
                    idf * occurrences * (self.k1 + 1) / (occurrences + self.k1 * length_norm)
                )
        ranked = [(position, score) for position, score in enumerate(scores) if score > 0]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_k]


class BM25Retriever:
    """Sparse lexical baseline over the open chunk release."""

    def __init__(
        self,
        chunks_path: str | Path | None = None,
        chunks: list[ChunkRecord] | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.chunks = (
            chunks
            if chunks is not None
            else read_jsonl(chunks_path or PATHS.release / "qinghai_chunks_open.jsonl", ChunkRecord)
        )
        self.index = BM25Index(k1=k1, b=b).build([tokenize(chunk.text) for chunk in self.chunks])

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query.strip() or not self.chunks:
            return []
        results = []
        for position, score in self.index.search(tokenize(query), top_k=top_k):
            chunk = self.chunks[position]
            results.append(
                {
                    "evidence_id": chunk.chunk_id,
                    "chunk_id": chunk.chunk_id,
                    "fact_id": None,
                    "source_id": chunk.source_id,
                    "score": float(score),
                    "text": chunk.text,
                    "source_url": chunk.source_url,
                    "kind": "bm25",
                }
            )
        return results
