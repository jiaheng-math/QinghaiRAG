from __future__ import annotations

import argparse
import json

from qinghai_rag.config import PATHS
from qinghai_rag.document_quality import audit_document_quality
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import SourceRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit cleaned document length without inflating parsed-source coverage"
    )
    parser.add_argument("--minimum-chars", type=int, default=100)
    parser.add_argument("--source-prefix", default="")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mark parsed sources below the threshold as fetched; default is a dry run",
    )
    args = parser.parse_args()

    sources = read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord)
    documents = read_jsonl(PATHS.interim / "documents.jsonl")
    updated, report = audit_document_quality(
        sources,
        documents,
        minimum_chars=args.minimum_chars,
        source_prefix=args.source_prefix,
        apply=args.apply,
    )
    if args.apply:
        write_jsonl_atomic(PATHS.release / "qinghai_sources.jsonl", updated, sort_key="source_id")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
