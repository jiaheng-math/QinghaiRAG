from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from qinghai_rag.config import PATHS, ProjectPaths
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import RELEASE_MODELS


class DatasetBuilder:
    """Small orchestration/inspection facade used by scripts and notebooks."""

    def __init__(self, paths: ProjectPaths = PATHS):
        self.paths = paths
        self.paths.ensure()

    def release_path(self, name: str) -> Path:
        return self.paths.release / name

    def load_release(self, name: str) -> list[Any]:
        model = RELEASE_MODELS[name]
        return read_jsonl(self.release_path(name), model)

    def statistics(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for filename in RELEASE_MODELS:
            records = self.load_release(filename)
            result[filename] = {"count": len(records)}
            if filename == "qinghai_qa_eval.jsonl":
                result[filename]["by_type"] = dict(Counter(item.answer_type for item in records))
            if filename == "qinghai_facts.jsonl":
                result[filename]["by_predicate"] = dict(Counter(item.predicate for item in records))
        return result
