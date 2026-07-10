from __future__ import annotations

import argparse
import logging
from pathlib import Path

from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.io_utils import read_jsonl, write_json_atomic
from qinghai_rag.schemas import ChunkRecord, EntityRecord, FactRecord, QARecord, SourceRecord
from qinghai_rag.stats import compute_dataset_stats, render_stats_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute QinghaiRAG dataset statistics")
    parser.add_argument("--json-output", default=str(PATHS.interim / "dataset_stats.json"))
    parser.add_argument("--markdown-output", default=str(PATHS.interim / "dataset_stats.md"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    stats = compute_dataset_stats(
        read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord),
        read_jsonl(PATHS.release / "qinghai_entities.jsonl", EntityRecord),
        read_jsonl(PATHS.release / "qinghai_facts.jsonl", FactRecord),
        read_jsonl(PATHS.release / "qinghai_chunks_open.jsonl", ChunkRecord),
        read_jsonl(PATHS.release / "qinghai_qa_eval.jsonl", QARecord),
        load_project_config("scale_targets.yaml"),
        load_project_config("release_policy.yaml").get("restricted_domains", []),
    )
    json_output, markdown_output = Path(args.json_output), Path(args.markdown_output)
    write_json_atomic(json_output, stats)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_stats_markdown(stats), encoding="utf-8")
    audit = stats["restricted_source_chunk_audit"]
    print(
        f"Wrote stats for {stats['counts']}; restricted open-text violations="
        f"{audit['open_text_violations']}"
    )
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
