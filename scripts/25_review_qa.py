from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_jsonl_atomic
from qinghai_rag.qa_manual_review import (
    QAManualReviewDecision,
    apply_qa_manual_review,
    build_batch_decisions,
    prepare_review_batch,
    render_review_batch,
)
from qinghai_rag.schemas import FactRecord, QARecord, SourceRecord


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactively review a deterministic, stratified QA sample"
    )
    parser.add_argument("--review-id", default="review_v1_qa_2026")
    parser.add_argument("--target", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--reviewer", default=os.getenv("QINGHAI_RAG_CONTACT", "maintainer"))
    parser.add_argument(
        "--decisions",
        type=Path,
        default=PATHS.root / "annotations" / "qa_reviews" / "v1_qa_2026.jsonl",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    qa_path = PATHS.release / "qinghai_qa_eval.jsonl"
    qa = read_jsonl(qa_path, QARecord)
    decisions = read_jsonl(args.decisions, QAManualReviewDecision)

    if args.apply:
        updated, report = apply_qa_manual_review(
            qa, decisions, args.review_id, minimum_accepted=args.target
        )
        report["applied"] = not report["issues"]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["issues"]:
            raise SystemExit("Refusing to apply QA manual review while issues remain")
        write_jsonl_atomic(qa_path, updated, sort_key="question_id")
        return

    facts = read_jsonl(PATHS.release / "qinghai_facts.jsonl", FactRecord)
    sources = read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord)
    batch, status = prepare_review_batch(
        qa, decisions, args.review_id, args.target, args.batch_size
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if not batch:
        print("审核样本已全部确认。运行同一命令并添加 --apply 写入 QA 数据。")
        return

    print("\n" + render_review_batch(batch, facts, sources))
    batch_id = status["batch_id"]
    expected = f"ACCEPT {batch_id}"
    response = input(f"\n逐条核验无误后输入 `{expected}`，其他输入不保存：\n> ").strip()
    if response != expected:
        print("本批未写入审核记录。")
        return

    new_decisions = build_batch_decisions(
        batch, args.review_id, str(batch_id), args.reviewer
    )
    merged = {(decision.review_id, decision.question_id): decision for decision in decisions}
    merged.update(
        {(decision.review_id, decision.question_id): decision for decision in new_decisions}
    )
    write_jsonl_atomic(args.decisions, merged.values(), sort_key="question_id")
    accepted = status["accepted"] + len(new_decisions)
    print(
        json.dumps(
            {
                "review_id": args.review_id,
                "accepted_batch": batch_id,
                "new_decisions": len(new_decisions),
                "accepted_total": accepted,
                "target": args.target,
                "remaining": args.target - accepted,
                "decisions_path": str(args.decisions),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
