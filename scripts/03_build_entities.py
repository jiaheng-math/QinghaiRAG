from __future__ import annotations

import argparse
import logging

from qinghai_rag.config import PATHS
from qinghai_rag.entity_linking import build_entities
from qinghai_rag.io_utils import read_jsonl, write_json_atomic, write_jsonl_atomic
from qinghai_rag.schemas import FactRecord
from qinghai_rag.state import stage_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized entities from facts")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    facts_path = PATHS.release / "qinghai_facts.jsonl"
    output = PATHS.release / "qinghai_entities.jsonl"
    aliases = PATHS.interim / "alias_mapping.json"
    state = stage_state("03_build_entities", [facts_path], [output, aliases])
    if args.resume and state.is_current():
        print("Resume: entity inputs are unchanged.")
        return
    records, alias_mapping = build_entities(read_jsonl(facts_path, FactRecord))
    write_jsonl_atomic(output, records, sort_key="entity_id")
    write_json_atomic(aliases, alias_mapping)
    state.commit()
    print(f"Built {len(records)} entities and {len(alias_mapping)} alias mappings.")


if __name__ == "__main__":
    main()
