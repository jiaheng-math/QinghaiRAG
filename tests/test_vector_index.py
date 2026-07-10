from __future__ import annotations

import numpy as np

from qinghai_rag.io_utils import write_jsonl_atomic
from qinghai_rag.rag.embeddings import EmbeddingConfig
from qinghai_rag.rag.vector_index import build_faiss_index
from qinghai_rag.schemas import ChunkRecord


class FakeEncoder:
    def __init__(self):
        self.calls = 0
        self.config = EmbeddingConfig(model_name="fake/test-encoder")

    def encode(self, texts, show_progress_bar=False):
        self.calls += 1
        vectors = []
        for index, _ in enumerate(texts):
            vector = np.zeros(4, dtype="float32")
            vector[index % 4] = 1.0
            vectors.append(vector)
        return np.asarray(vectors, dtype="float32")


def test_faiss_index_is_atomically_written_and_resumed(tmp_path):
    chunks = [
        ChunkRecord(
            chunk_id=f"chk_{index}",
            doc_id="doc_test",
            source_id="src_test",
            text=f"测试文本{index}",
            char_start=index,
            char_end=index + 5,
            license_status="open",
            release_policy="full_text_allowed",
            source_url="https://example.org/test",
            retrieved_at="2026-07-10",
            notes="test only",
        )
        for index in range(2)
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    index_path = tmp_path / "faiss.index"
    metadata_path = tmp_path / "metadata.jsonl"
    manifest_path = tmp_path / "manifest.json"
    write_jsonl_atomic(chunks_path, chunks)
    encoder = FakeEncoder()

    first = build_faiss_index(
        chunks_path,
        index_path,
        metadata_path,
        manifest_path,
        encoder=encoder,
    )
    second = build_faiss_index(
        chunks_path,
        index_path,
        metadata_path,
        manifest_path,
        encoder=encoder,
    )

    assert first == second
    assert first["count"] == 2
    assert first["model_name"] == "fake/test-encoder"
    assert index_path.exists() and metadata_path.exists()
    assert encoder.calls == 1
