from __future__ import annotations

import logging
from pathlib import Path

from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.io_utils import (
    file_fingerprint,
    read_json,
    read_jsonl,
    write_json_atomic,
    write_jsonl_atomic,
)
from qinghai_rag.rag.embeddings import EmbeddingConfig, SentenceTransformerEncoder
from qinghai_rag.schemas import ChunkRecord

LOGGER = logging.getLogger(__name__)


def build_faiss_index(
    chunks_path: str | Path | None = None,
    index_path: str | Path | None = None,
    metadata_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    resume: bool = True,
    encoder: SentenceTransformerEncoder | None = None,
) -> dict:
    import faiss

    config = load_project_config("rag.yaml")
    chunks_path = Path(chunks_path or PATHS.release / "qinghai_chunks_open.jsonl")
    index_path = Path(index_path or PATHS.cache / "faiss.index")
    metadata_path = Path(metadata_path or PATHS.cache / "faiss_metadata.jsonl")
    manifest_path = Path(manifest_path or PATHS.cache / "faiss_manifest.json")
    embedding_config = (
        encoder.config
        if encoder is not None and isinstance(getattr(encoder, "config", None), EmbeddingConfig)
        else EmbeddingConfig(**config.get("embedding", {}))
    )
    fingerprint = file_fingerprint([chunks_path])
    expected = {
        "input_fingerprint": fingerprint,
        "model_name": embedding_config.model_name,
        "normalize_embeddings": embedding_config.normalize_embeddings,
    }
    previous = read_json(manifest_path, {})
    if (
        resume
        and previous
        and all(previous.get(key) == value for key, value in expected.items())
        and index_path.exists()
        and metadata_path.exists()
    ):
        LOGGER.info("Resume: FAISS index manifest matches; reusing %s", index_path)
        return previous

    chunks = read_jsonl(chunks_path, ChunkRecord)
    if not chunks:
        raise ValueError(f"No chunks found at {chunks_path}")
    encoder = encoder or SentenceTransformerEncoder(embedding_config)
    embeddings = encoder.encode([chunk.text for chunk in chunks], show_progress_bar=True)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = index_path.with_suffix(index_path.suffix + ".tmp")
    faiss.write_index(index, str(temporary))
    temporary.replace(index_path)
    write_jsonl_atomic(metadata_path, chunks)
    manifest = {
        **expected,
        "dimension": int(embeddings.shape[1]),
        "count": len(chunks),
        "index_path": str(index_path),
        "metadata_path": str(metadata_path),
    }
    write_json_atomic(manifest_path, manifest)
    return manifest
