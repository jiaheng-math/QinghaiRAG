from __future__ import annotations

import argparse
import json

from qinghai_rag.config import PATHS
from qinghai_rag.inheritor_facts import build_inheritor_facts, merge_inheritor_facts
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import FactRecord, SourceCandidateRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build cross-checked facts from the official inheritor catalog and pages"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write eligible facts to the release file; default is a dry run",
    )
    args = parser.parse_args()

    candidate_path = PATHS.interim / "source_candidates_ihchina_inheritors.jsonl"
    document_path = PATHS.interim / "documents.jsonl"
    fact_path = PATHS.release / "qinghai_facts.jsonl"
    candidates = read_jsonl(candidate_path, SourceCandidateRecord)
    documents = read_jsonl(document_path)
    existing = read_jsonl(fact_path, FactRecord)
    generated, report = build_inheritor_facts(candidates, documents)
    merged, retained_generated = merge_inheritor_facts(existing, generated)
    report.update(
        {
            "retained_generated_facts": retained_generated,
            "projected_release_total": len(merged),
            "updated": retained_generated if args.apply else 0,
            "manual_checked_before": sum(fact.manual_checked for fact in existing),
            "manual_checked_after": sum(fact.manual_checked for fact in merged),
        }
    )
    if args.apply:
        write_jsonl_atomic(fact_path, merged, sort_key="fact_id")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
