from __future__ import annotations

import argparse
import logging

from qinghai_rag.config import PATHS
from qinghai_rag.source_registry import SourceRegistry
from qinghai_rag.tibetan_museum_collection import TibetanMuseumCollector


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect and validate official Tibetan Culture Museum exhibit details"
    )
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--contact", default=None)
    parser.add_argument("--no-env-proxy", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sources = [
        source
        for source in SourceRegistry().records()
        if source.source_id.startswith("src_tibetan_museum_exhibit_")
    ]
    if args.source_id:
        selected = set(args.source_id)
        sources = [source for source in sources if source.source_id in selected]
    elif args.resume:
        sources = [
            source for source in sources if source.crawl_status.value in {"pending", "failed"}
        ]
    if not sources:
        print("Nothing to collect; all selected museum exhibits are complete.")
        return

    collector = TibetanMuseumCollector(
        PATHS,
        interval_seconds=args.interval,
        timeout=args.timeout,
        contact=args.contact,
        trust_env=not args.no_env_proxy,
    )
    updated, documents = collector.collect(sources, force=args.force)
    failures = sum(source.crawl_status.value == "failed" for source in updated)
    print(
        f"Processed {len(updated)} museum exhibits, wrote {len(documents)} documents, "
        f"failures={failures}"
    )


if __name__ == "__main__":
    main()
