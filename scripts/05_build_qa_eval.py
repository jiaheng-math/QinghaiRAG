from __future__ import annotations

import argparse
import logging
from collections import Counter

from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.qa_generation import generate_qa, resolve_qa_minimum
from qinghai_rag.schemas import FactRecord
from qinghai_rag.state import stage_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a fact-grounded QA evaluation set")
    parser.add_argument(
        "--minimum",
        type=int,
        default=None,
        help="QA target; defaults to the v0.1 minimum in configs/scale_targets.yaml",
    )
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    minimum = resolve_qa_minimum(
        args.minimum,
        load_project_config("scale_targets.yaml"),
    )
    facts_path = PATHS.release / "qinghai_facts.jsonl"
    output = PATHS.release / "qinghai_qa_eval.jsonl"
    state = stage_state("05_build_qa", [facts_path], [output], minimum=minimum)
    if args.resume and state.is_current():
        print("Resume: QA inputs are unchanged.")
        return
    records = generate_qa(read_jsonl(facts_path, FactRecord), minimum=minimum)
    write_jsonl_atomic(output, records, sort_key="question_id")
    state.commit()
    print(f"Built {len(records)} QA records: {dict(Counter(item.answer_type for item in records))}")


if __name__ == "__main__":
    main()
