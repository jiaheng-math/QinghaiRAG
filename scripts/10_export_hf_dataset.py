from __future__ import annotations

import argparse
import os
from pathlib import Path

from qinghai_rag.config import PATHS, configure_external_caches
from qinghai_rag.io_utils import read_jsonl

FILES = {
    "sources": "qinghai_sources.jsonl",
    "entities": "qinghai_entities.jsonl",
    "facts": "qinghai_facts.jsonl",
    "chunks_open": "qinghai_chunks_open.jsonl",
    "qa_eval": "qinghai_qa_eval.jsonl",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export QinghaiRAG as a Hugging Face DatasetDict")
    parser.add_argument("--output", default=str(PATHS.release / "hf_dataset"))
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--repo-id", default=None)
    args = parser.parse_args()
    configure_external_caches()
    from datasets import Dataset, DatasetDict

    dataset = DatasetDict(
        {
            split: Dataset.from_list(read_jsonl(PATHS.release / filename))
            for split, filename in FILES.items()
        }
    )
    output = Path(args.output)
    dataset.save_to_disk(str(output))
    card = PATHS.root / "docs" / "DATASET_CARD.md"
    (output / "README.md").write_text(card.read_text(encoding="utf-8"), encoding="utf-8")
    if args.push:
        token = os.getenv("HF_TOKEN")
        if not token or not args.repo_id:
            raise ValueError("--push requires both HF_TOKEN and --repo-id")
        dataset.push_to_hub(args.repo_id, token=token)
    print(f"Exported DatasetDict to {output}; push={args.push}")


if __name__ == "__main__":
    main()
