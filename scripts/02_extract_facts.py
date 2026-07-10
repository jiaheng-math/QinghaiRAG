from __future__ import annotations

import argparse
import logging
from pathlib import Path

from qinghai_rag.config import PATHS
from qinghai_rag.fact_extraction import (
    deduplicate_facts,
    extract_semistructured_facts,
    extract_table_facts,
    merge_extracted_facts,
)
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import FactRecord, SourceRecord
from qinghai_rag.state import stage_state


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract evidence-backed facts from locally collected documents"
    )
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace rather than merge with existing release facts",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    documents_path = PATHS.interim / "documents.jsonl"
    sources_path = PATHS.release / "qinghai_sources.jsonl"
    release_path = PATHS.release / "qinghai_facts.jsonl"
    interim_path = PATHS.interim / "facts_extracted.jsonl"
    state = stage_state(
        "02_extract_facts", [documents_path, sources_path], [interim_path], replace=args.replace
    )
    if args.resume and state.is_current():
        print("Resume: fact extraction inputs are unchanged.")
        return
    sources = {item.source_id: item for item in read_jsonl(sources_path, SourceRecord)}
    documents = read_jsonl(documents_path)
    extracted = []
    for document in documents:
        source = sources.get(document["source_id"])
        if not source:
            logging.warning("Unknown source_id in document: %s", document["source_id"])
            continue
        raw_path = Path(document.get("raw_path", ""))
        if raw_path.exists():
            extracted.extend(
                extract_table_facts(raw_path.read_text(encoding="utf-8", errors="replace"), source)
            )
        extracted.extend(extract_semistructured_facts(document.get("text", ""), source))
    extracted = deduplicate_facts(extracted)
    write_jsonl_atomic(interim_path, extracted, sort_key="fact_id")
    releasable = [fact for fact in extracted if fact.confidence in {"high", "medium"}]
    existing = [] if args.replace else read_jsonl(release_path, FactRecord)
    merged = merge_extracted_facts(existing, releasable)
    write_jsonl_atomic(release_path, merged, sort_key="fact_id")
    state.commit()
    print(
        f"Extracted {len(extracted)} facts; released/retained {len(merged)}. Auto-extracted facts remain verified=false."
    )


if __name__ == "__main__":
    main()
