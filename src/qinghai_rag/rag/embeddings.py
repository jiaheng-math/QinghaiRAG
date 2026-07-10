from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from qinghai_rag.config import PATHS, configure_external_caches


@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-small-zh-v1.5"
    device: str = "cpu"
    batch_size: int = 32
    normalize_embeddings: bool = True


class SentenceTransformerEncoder:
    def __init__(self, config: EmbeddingConfig | None = None):
        self.config = config or EmbeddingConfig()
        configure_external_caches(PATHS)
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            self.config.model_name,
            device=self.config.device,
            cache_folder=str(PATHS.cache / "huggingface" / "sentence_transformers"),
        )

    def encode(self, texts: Sequence[str], show_progress_bar: bool = False) -> np.ndarray:
        return np.asarray(
            self.model.encode(
                list(texts),
                batch_size=self.config.batch_size,
                normalize_embeddings=self.config.normalize_embeddings,
                show_progress_bar=show_progress_bar,
                convert_to_numpy=True,
            ),
            dtype="float32",
        )
