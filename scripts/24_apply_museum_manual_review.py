from __future__ import annotations

import argparse
import json

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.museum_manual_review import (
    load_museum_manual_review,
    mark_museum_manual_review,
)
from qinghai_rag.schemas import FactRecord, SourceRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and apply a fixed museum-object manual review sample"
    )
    parser.add_argument(
        "--review",
        default=str(
            PATHS.root / "annotations" / "museum_reviews" / "tibetan_museum_sample_2026.yaml"
        ),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    facts_path = PATHS.release / "qinghai_facts.jsonl"
    facts = read_jsonl(facts_path, FactRecord)
    sources = read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord)
    review = load_museum_manual_review(args.review)
    updated, report = mark_museum_manual_review(facts, sources, review)
    report["applied"] = args.apply
    if args.apply and report["issues"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit("Refusing to apply museum manual review while issues remain")
    if args.apply:
        write_jsonl_atomic(facts_path, updated, sort_key="fact_id")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
