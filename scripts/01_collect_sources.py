from __future__ import annotations

import argparse
import logging

from qinghai_rag.config import PATHS
from qinghai_rag.crawler import FriendlyCrawler
from qinghai_rag.source_registry import SourceRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect registered QinghaiRAG sources")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force", action="store_true", help="Refetch even when raw HTML is cached")
    parser.add_argument(
        "--source-id", action="append", default=[], help="Limit to selected source IDs"
    )
    parser.add_argument("--interval", type=float, default=None)
    parser.add_argument("--contact", default=None)
    parser.add_argument(
        "--no-env-proxy",
        action="store_true",
        help="Ignore HTTP(S)_PROXY environment variables for direct-only official sites",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sources = SourceRegistry().records()
    if args.source_id:
        selected = set(args.source_id)
        sources = [source for source in sources if source.source_id in selected]
    elif args.resume:
        sources = [
            source for source in sources if source.crawl_status.value in {"pending", "failed"}
        ]
    if not sources:
        print("Nothing to collect; all selected sources are complete or skipped.")
        return
    crawler = FriendlyCrawler(
        PATHS,
        interval_seconds=args.interval,
        contact=args.contact,
        trust_env=not args.no_env_proxy,
    )
    updated, documents = crawler.collect(sources, force=args.force)
    failures = sum(source.crawl_status == "failed" for source in updated)
    print(
        f"Processed {len(updated)} sources, wrote {len(documents)} documents, failures={failures}"
    )


if __name__ == "__main__":
    main()
