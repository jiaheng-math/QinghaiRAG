from __future__ import annotations

import argparse
import json

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import FactRecord, SourceCandidateRecord, SourceRecord
from qinghai_rag.tibetan_museum_facts import (
    build_tibetan_museum_facts,
    merge_tibetan_museum_facts,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build deterministically verified facts from official museum exhibit APIs"
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    candidates = read_jsonl(
        PATHS.interim / "source_candidates_tibetan_museum_exhibits.jsonl",
        SourceCandidateRecord,
    )
    sources = read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord)
    generated, report = build_tibetan_museum_facts(
        candidates,
        sources,
        PATHS.raw / "tibetan_museum",
    )
    facts_path = PATHS.release / "qinghai_facts.jsonl"
    existing = read_jsonl(facts_path, FactRecord)
    merged, merge_report = merge_tibetan_museum_facts(existing, generated)
    report.update(merge_report)
    report["applied"] = args.apply
    if args.apply:
        if report["issues"]:
            raise SystemExit("Refusing to apply museum facts while verification issues remain")
        write_jsonl_atomic(facts_path, merged, sort_key="fact_id")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
