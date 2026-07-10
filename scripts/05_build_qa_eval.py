from __future__ import annotations

import argparse
import logging
from collections import Counter

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.qa_generation import generate_qa
from qinghai_rag.schemas import FactRecord
from qinghai_rag.state import stage_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a fact-grounded QA evaluation set")
    parser.add_argument("--minimum", type=int, default=100)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    facts_path = PATHS.release / "qinghai_facts.jsonl"
    output = PATHS.release / "qinghai_qa_eval.jsonl"
    state = stage_state("05_build_qa", [facts_path], [output], minimum=args.minimum)
    if args.resume and state.is_current():
        print("Resume: QA inputs are unchanged.")
        return
    records = generate_qa(read_jsonl(facts_path, FactRecord), minimum=args.minimum)
    write_jsonl_atomic(output, records, sort_key="question_id")
    state.commit()
    print(f"Built {len(records)} QA records: {dict(Counter(item.answer_type for item in records))}")


if __name__ == "__main__":
    main()
