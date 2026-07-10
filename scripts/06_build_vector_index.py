from __future__ import annotations

import argparse
import json
import logging

from qinghai_rag.config import load_project_config
from qinghai_rag.rag.embeddings import EmbeddingConfig, SentenceTransformerEncoder
from qinghai_rag.rag.vector_index import build_faiss_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or resume the FAISS vector index")
    parser.add_argument("--model", default=None)
    parser.add_argument("--device", default=None, help="cpu, cuda, or cuda:0")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = load_project_config("rag.yaml").get("embedding", {})
    if args.model:
        config["model_name"] = args.model
    if args.device:
        config["device"] = args.device
    if args.batch_size:
        config["batch_size"] = args.batch_size
    encoder = SentenceTransformerEncoder(EmbeddingConfig(**config))
    manifest = build_faiss_index(resume=args.resume, encoder=encoder)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
