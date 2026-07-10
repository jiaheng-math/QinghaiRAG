from __future__ import annotations

import argparse
import json
from pathlib import Path

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import SourceCandidateRecord
from qinghai_rag.source_discovery import candidate_to_source
from qinghai_rag.source_registry import SourceRegistry
from qinghai_rag.tibetan_museum_discovery import (
    candidates_from_tibetan_museum_payload,
    discover_tibetan_museum_exhibits,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover collection objects from the official Tibetan Culture Museum API"
    )
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--no-env-proxy", action="store_true")
    parser.add_argument(
        "--offline-json",
        help="Parse a saved official API response instead of downloading it again",
    )
    parser.add_argument(
        "--output",
        default=str(PATHS.interim / "source_candidates_tibetan_museum_exhibits.jsonl"),
    )
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    if args.offline_json:
        payload = json.loads(Path(args.offline_json).read_text(encoding="utf-8"))
        discovered, metadata = candidates_from_tibetan_museum_payload(payload)
        metadata["fetched_pages"] = 0
    else:
        discovered, metadata = discover_tibetan_museum_exhibits(
            page_size=args.page_size,
            timeout=args.timeout,
            no_env_proxy=args.no_env_proxy,
        )

    output = Path(args.output)
    existing = {item.source_id: item for item in read_jsonl(output, SourceCandidateRecord)}
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
                **metadata,
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
