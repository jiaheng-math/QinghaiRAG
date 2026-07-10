from __future__ import annotations

import argparse
import json
from pathlib import Path

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import SourceCandidateRecord
from qinghai_rag.source_discovery import candidate_to_source
from qinghai_rag.source_registry import SourceRegistry
from qinghai_rag.whlyt_discovery import discover_whlyt_articles


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover high-relevance ICH article metadata from Qinghai culture-tourism search"
    )
    parser.add_argument("--keyword", default="非遗")
    parser.add_argument("--category", default="wldt")
    parser.add_argument("--scope", default="title")
    parser.add_argument("--time", default="all")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--output", default=str(PATHS.interim / "source_candidates_whlyt_articles.jsonl")
    )
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    discovered, search_metadata = discover_whlyt_articles(
        keyword=args.keyword,
        category=args.category,
        scope=args.scope,
        time_filter=args.time,
        timeout=args.timeout,
        interval_seconds=args.interval,
        max_pages=args.max_pages,
    )
    output = Path(args.output)
    existing = {
        item.source_id: item for item in read_jsonl(output, SourceCandidateRecord)
    }
    existing.update({item.source_id: item for item in discovered})
    records = sorted(existing.values(), key=lambda item: item.source_id)
    write_jsonl_atomic(output, records, sort_key="source_id")

    registered = 0
    registry_total = None
    if args.register:
        registry = SourceRegistry()
        before = len(registry.records())
        registry.upsert([candidate_to_source(item) for item in discovered])
        registry_total = len(registry.records())
        registered = registry_total - before

    print(
        json.dumps(
            {
                **search_metadata,
                "discovered": len(discovered),
                "candidate_queue": len(records),
                "registered": registered,
                "skipped_existing": len(discovered) - registered if args.register else 0,
                "registry_total": registry_total,
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
