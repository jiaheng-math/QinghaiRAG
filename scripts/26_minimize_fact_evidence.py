from __future__ import annotations

import argparse
import json

from qinghai_rag.config import PATHS
from qinghai_rag.evidence_minimization import minimize_fact_evidence
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.schemas import FactRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove unrelated personal columns from released fact evidence excerpts"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write minimized excerpts back to qinghai_facts.jsonl; default is dry-run",
    )
    args = parser.parse_args()

    facts_path = PATHS.release / "qinghai_facts.jsonl"
    facts = read_jsonl(facts_path, FactRecord)
    updated, report = minimize_fact_evidence(facts)
    report["applied"] = args.apply

    if report["remaining_personal_field_excerpts"]:
        raise SystemExit("Refusing to write while personal-field excerpts remain")
    if args.apply:
        write_jsonl_atomic(facts_path, updated, sort_key="fact_id")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
