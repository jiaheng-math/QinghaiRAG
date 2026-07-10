from __future__ import annotations

import argparse
import os
from pathlib import Path

from qinghai_rag.audit_export import build_audit_samples
from qinghai_rag.config import PATHS, configure_external_caches
from qinghai_rag.hf_release import prepare_release_package, upload_supporting_files
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import FactRecord, QARecord

FILES = {
    "source_registry": "qinghai_sources.jsonl",
    "entities": "qinghai_entities.jsonl",
    "facts": "qinghai_facts.jsonl",
    "open_chunks": "qinghai_chunks_open.jsonl",
    "qa_benchmark": "qinghai_qa_eval.jsonl",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export QinghaiRAG as Hugging Face configs with an audit package"
    )
    parser.add_argument("--output", default=str(PATHS.release / "hf_dataset"))
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--repo-id", default=None)
    parser.add_argument(
        "--allow-missing-reports",
        action="store_true",
        help="Development-only: export even when validation/statistics/evaluation reports are absent",
    )
    args = parser.parse_args()
    configure_external_caches()
    from datasets import Dataset

    records = {
        config_name: read_jsonl(PATHS.release / filename)
        for config_name, filename in FILES.items()
    }
    facts = read_jsonl(PATHS.release / FILES["facts"], FactRecord)
    qa = read_jsonl(PATHS.release / FILES["qa_benchmark"], QARecord)
    records["audit_samples"] = build_audit_samples(
        facts,
        qa,
        PATHS.root / "annotations" / "audit_corrections.yaml",
    )
    output = Path(args.output)
    datasets = {name: Dataset.from_list(rows) for name, rows in records.items()}
    for config_name, dataset in datasets.items():
        dataset.save_to_disk(str(output / "configs" / config_name))
    card = PATHS.root / "docs" / "DATASET_CARD.md"
    output.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(card.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = prepare_release_package(
        output,
        records,
        FILES,
        PATHS,
        require_reports=not args.allow_missing_reports,
    )
    if args.push:
        token = os.getenv("HF_TOKEN")
        if not token or not args.repo_id:
            raise ValueError("--push requires both HF_TOKEN and --repo-id")
        for config_name, dataset in datasets.items():
            dataset.push_to_hub(
                args.repo_id,
                config_name=config_name,
                split="full",
                token=token,
            )
        from huggingface_hub import HfApi

        upload_supporting_files(HfApi(), args.repo_id, output, token)
    counts = {name: len(rows) for name, rows in records.items()}
    print(
        f"Exported Hugging Face configs to {output}; counts={counts}; "
        f"audit_samples={manifest['manual_review']['audit_samples']}; push={args.push}"
    )


if __name__ == "__main__":
    main()
