from __future__ import annotations

import argparse
import json
from pathlib import Path

from qinghai_rag.catalog_verification import crosscheck_catalog_facts
from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import FactRecord, SourceCandidateRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-check page-table facts against official catalog metadata"
    )
    parser.add_argument(
        "--candidates",
        default=str(PATHS.interim / "source_candidates_ihchina.jsonl"),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mark exactly matching facts verified; manual_checked remains false",
    )
    args = parser.parse_args()

    facts_path = PATHS.release / "qinghai_facts.jsonl"
    facts = read_jsonl(facts_path, FactRecord)
    candidates = read_jsonl(Path(args.candidates), SourceCandidateRecord)
    updated, report = crosscheck_catalog_facts(facts, candidates, apply=args.apply)
    if args.apply:
        write_jsonl_atomic(facts_path, updated, sort_key="fact_id")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
