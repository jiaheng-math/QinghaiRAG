from __future__ import annotations

import argparse
import logging

from qinghai_rag.config import PATHS, load_project_config, load_yaml
from qinghai_rag.source_registry import SourceRegistry


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize or update the source registry from YAML seeds"
    )
    parser.add_argument("--config", default=str(PATHS.configs / "sources_seed.yaml"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    PATHS.ensure()
    config = (
        load_project_config("sources_seed.yaml")
        if args.config == str(PATHS.configs / "sources_seed.yaml")
        else load_yaml(args.config)
    )
    registry = SourceRegistry()
    records = [SourceRegistry.from_seed(seed) for seed in config.get("sources", [])]
    registry.upsert(records)
    print(f"Source registry contains {len(registry.records())} records: {registry.path}")


if __name__ == "__main__":
    main()
