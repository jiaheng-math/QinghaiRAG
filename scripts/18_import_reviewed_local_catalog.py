from __future__ import annotations

import argparse
import json
from pathlib import Path

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.local_catalogs import (
    build_reviewed_catalog_facts,
    build_reviewed_catalog_source,
    load_reviewed_catalog,
    merge_reviewed_catalog_facts,
    verify_reviewed_attachment,
)
from qinghai_rag.schemas import FactRecord
from qinghai_rag.source_registry import SourceRegistry


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and import a manually reviewed local official catalog"
    )
    parser.add_argument(
        "--review",
        default=str(PATHS.root / "annotations" / "local_catalogs" / "huangzhong_4th_ich_2025.yaml"),
    )
    parser.add_argument(
        "--attachment",
        default=None,
        help="Override the local raw attachment path recorded in the review",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Upsert the reviewed source and facts; default is a dry run",
    )
    args = parser.parse_args()

    review = load_reviewed_catalog(args.review)
    attachment = Path(args.attachment or (PATHS.root / review.raw_path))
    verified_sha256 = verify_reviewed_attachment(review, attachment)
    source = build_reviewed_catalog_source(review)
    generated = build_reviewed_catalog_facts(review)
    facts_path = PATHS.release / "qinghai_facts.jsonl"
    existing = read_jsonl(facts_path, FactRecord)
    merged, report = merge_reviewed_catalog_facts(existing, generated)
    report.update(
        {
            "review_id": review.review_id,
            "reviewed_rows": len(review.rows),
            "attachment_sha256": verified_sha256,
            "source_id": source.source_id,
            "applied": args.apply,
        }
    )
    if args.apply:
        SourceRegistry().upsert([source])
        write_jsonl_atomic(facts_path, merged, sort_key="fact_id")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
