from __future__ import annotations

import argparse
import logging

from qinghai_rag.chunking import build_open_chunks, build_synthetic_fact_chunks
from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import EntityRecord, FactRecord, SourceRecord
from qinghai_rag.state import stage_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Build release-safe open and synthetic chunks")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=80)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    documents_path = PATHS.interim / "documents.jsonl"
    sources_path = PATHS.release / "qinghai_sources.jsonl"
    entities_path = PATHS.release / "qinghai_entities.jsonl"
    facts_path = PATHS.release / "qinghai_facts.jsonl"
    output = PATHS.release / "qinghai_chunks_open.jsonl"
    state = stage_state(
        "04_build_chunks",
        [documents_path, sources_path, entities_path, facts_path],
        [output],
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    if args.resume and state.is_current():
        print("Resume: chunk inputs are unchanged.")
        return
    sources = {item.source_id: item for item in read_jsonl(sources_path, SourceRecord)}
    entities = read_jsonl(entities_path, EntityRecord)
    facts = read_jsonl(facts_path, FactRecord)
    open_chunks = build_open_chunks(
        read_jsonl(documents_path), sources, entities, args.chunk_size, args.overlap
    )
    synthetic = build_synthetic_fact_chunks(facts, sources)
    merged = {item.chunk_id: item for item in [*open_chunks, *synthetic]}
    write_jsonl_atomic(output, merged.values(), sort_key="chunk_id")
    state.commit()
    print(f"Built {len(open_chunks)} open-text and {len(synthetic)} synthetic-fact chunks.")


if __name__ == "__main__":
    main()
