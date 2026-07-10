from __future__ import annotations

import argparse
import json
import logging
from statistics import mean
from typing import Any

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import read_jsonl, write_json_atomic
from qinghai_rag.rag.answer import EvidenceAnswerer
from qinghai_rag.rag.retriever import HybridRetriever, build_hybrid_retriever
from qinghai_rag.schemas import QARecord

LOGGER = logging.getLogger(__name__)


def evaluate_mode(
    qa_records: list[QARecord],
    retriever: HybridRetriever,
    mode: str,
    top_k: int,
) -> dict[str, Any]:
    recalls, hits, diversities, reciprocal_ranks = [], [], [], []
    refusal_flags, citation_flags = [], []
    answerer = EvidenceAnswerer()
    examples = []
    for qa in qa_records:
        evidence = retriever.retrieve(qa.question, mode=mode, top_k=top_k, budget=top_k)
        source_ids = {item.get("source_id") for item in evidence}
        fact_ids = {item.get("fact_id") for item in evidence if item.get("fact_id")}
        if not qa.unanswerable:
            gold_sources = set(qa.evidence_source_ids)
            recalls.append(float(bool(gold_sources & source_ids)))
            hits.append(
                float(bool(set(qa.evidence_fact_ids) & fact_ids) or bool(gold_sources & source_ids))
            )
            reciprocal_ranks.append(
                next(
                    (
                        1.0 / rank
                        for rank, item in enumerate(evidence, start=1)
                        if item.get("source_id") in gold_sources
                    ),
                    0.0,
                )
            )
        diversities.append(len(source_ids - {None}))
        answer = answerer.answer(qa.question, evidence)
        if qa.unanswerable:
            refusal_flags.append(float(answer["refused"]))
        citation_flags.append(
            float(
                answer["refused"]
                or all(
                    item.get("source_id") and item.get("source_url") for item in answer["evidence"]
                )
            )
        )
        if len(examples) < 10:
            examples.append(
                {
                    "question_id": qa.question_id,
                    "question": qa.question,
                    "refused": answer["refused"],
                    "retrieved_source_ids": sorted(source_ids - {None}),
                }
            )
    return {
        f"recall@{top_k}": mean(recalls) if recalls else None,
        "mrr": mean(reciprocal_ranks) if reciprocal_ranks else None,
        "evidence_hit_rate": mean(hits) if hits else None,
        "mean_source_diversity": mean(diversities) if diversities else 0.0,
        "unanswerable_refusal_rate": mean(refusal_flags) if refusal_flags else None,
        "citation_presence_rate": mean(citation_flags) if citation_flags else None,
        "evaluated_questions": len(qa_records),
        "examples": examples,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# QinghaiRAG evaluation report", "", f"Top-k: {report['top_k']}", ""]
    for mode, metrics in report["modes"].items():
        lines.extend([f"## {mode}", "", "| Metric | Value |", "|---|---:|"])
        for key, value in metrics.items():
            if key == "examples":
                continue
            rendered = f"{value:.4f}" if isinstance(value, float) else str(value)
            lines.append(f"| {key} | {rendered} |")
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "This baseline measures evidence retrieval and refusal behavior; it does not claim semantic answer correctness without an answer model and human review.",
            "",
        ]
    )
    return "\n".join(lines)


def run_evaluation(
    top_k: int = 5,
    device: str | None = None,
    rerank: bool | None = None,
    retriever: HybridRetriever | None = None,
) -> dict[str, Any]:
    qa = read_jsonl(PATHS.release / "qinghai_qa_eval.jsonl", QARecord)
    hybrid = retriever or build_hybrid_retriever(device=device, rerank=rerank)
    modes = hybrid.available_modes()
    if not modes:
        raise FileNotFoundError("Build at least one vector, BM25, or graph index before evaluation")
    report = {
        "top_k": top_k,
        "modes": {mode: evaluate_mode(qa, hybrid, mode, top_k) for mode in modes},
    }
    PATHS.interim.mkdir(parents=True, exist_ok=True)
    write_json_atomic(PATHS.interim / "eval_report.json", report)
    (PATHS.interim / "eval_report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate QinghaiRAG retrieval baselines")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--device", default=None, help="Override embedding/reranker device")
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Also evaluate cross-encoder reranked variants (defaults to configs/rag.yaml)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(
        json.dumps(
            run_evaluation(args.top_k, device=args.device, rerank=args.rerank),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
