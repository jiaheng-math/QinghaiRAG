from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qinghai_rag.config import PATHS, configure_external_caches


@dataclass
class RerankerConfig:
    model_name: str = "BAAI/bge-reranker-base"
    device: str = "cpu"
    batch_size: int = 32
    max_length: int = 512
    enabled: bool = False


class CrossEncoderReranker:
    """Cross-encoder reranking over retrieved candidates.

    Scores are sigmoid probabilities in [0, 1], so they stay compatible with
    the EvidenceAnswerer minimum-score threshold. Original retrieval scores
    are preserved under ``retrieval_score``.
    """

    def __init__(self, config: RerankerConfig | None = None):
        self.config = config or RerankerConfig()
        configure_external_caches(PATHS)
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(
            self.config.model_name,
            device=self.config.device,
            max_length=self.config.max_length,
        )

    def rerank(
        self, query: str, candidates: list[dict[str, Any]], top_k: int | None = None
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        scores = self.model.predict(
            [(query, item.get("text", "")) for item in candidates],
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        reranked = []
        for item, score in zip(candidates, scores):
            updated = dict(item)
            updated["retrieval_score"] = float(item.get("score", 0.0))
            updated["score"] = float(score)
            reranked.append(updated)
        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked[:top_k] if top_k else reranked
