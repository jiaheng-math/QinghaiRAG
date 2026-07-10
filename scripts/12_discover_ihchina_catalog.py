from __future__ import annotations

import argparse
import json
from pathlib import Path

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import SourceCandidateRecord
from qinghai_rag.source_discovery import (
    candidate_to_source,
    candidates_from_ihchina_payload,
    discover_ihchina_catalog,
)
from qinghai_rag.source_registry import SourceRegistry


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover Qinghai project pages from the official national ICH catalog"
    )
    parser.add_argument("--province-code", default="630000")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--output", default=str(PATHS.interim / "source_candidates_ihchina.jsonl")
    )
    parser.add_argument(
        "--offline-json",
        help="Parse a saved API payload instead of making a network request",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register discovered pages with conservative metadata-and-facts-only policy",
    )
    args = parser.parse_args()

    if args.offline_json:
        payload = json.loads(Path(args.offline_json).read_text(encoding="utf-8"))
        discovered = candidates_from_ihchina_payload(payload)
    else:
        discovered = discover_ihchina_catalog(
            province_code=args.province_code,
            page_size=args.page_size,
            timeout=args.timeout,
        )

    output = Path(args.output)
    existing = {
        item.source_id: item
        for item in read_jsonl(output, SourceCandidateRecord)
    }
    existing.update({item.source_id: item for item in discovered})
    records = sorted(existing.values(), key=lambda item: item.source_id)
    write_jsonl_atomic(output, records, sort_key="source_id")

    if args.register:
        registry = SourceRegistry()
        registry_count_before = len(registry.records())
        registry.upsert([candidate_to_source(item) for item in discovered])
        registry_count_after = len(registry.records())
        registered = registry_count_after - registry_count_before
    else:
        registered = 0
        registry_count_after = None

    categories: dict[str, int] = {}
    for item in discovered:
        category = item.catalog_metadata.get("category", "")
        categories[category] = categories.get(category, 0) + 1
    print(
        json.dumps(
            {
                "discovered": len(discovered),
                "candidate_queue": len(records),
                "registered": registered,
                "skipped_existing": len(discovered) - registered if args.register else 0,
                "registry_total": registry_count_after,
                "categories": dict(sorted(categories.items())),
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
