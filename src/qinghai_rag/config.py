from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    data: Path
    raw: Path
    cache: Path
    interim: Path
    release: Path
    checkpoints: Path
    configs: Path

    @classmethod
    def from_env(cls) -> "ProjectPaths":
        default_root = Path(__file__).resolve().parents[2]
        root = Path(os.getenv("QINGHAI_RAG_HOME", default_root)).expanduser().resolve()
        data = Path(os.getenv("QINGHAI_RAG_DATA_DIR", root / "data")).expanduser().resolve()
        cache = Path(os.getenv("QINGHAI_RAG_CACHE_DIR", data / "cache")).expanduser().resolve()
        checkpoints = (
            Path(os.getenv("QINGHAI_RAG_CHECKPOINT_DIR", cache / "checkpoints"))
            .expanduser()
            .resolve()
        )
        return cls(
            root=root,
            data=data,
            raw=data / "raw",
            cache=cache,
            interim=data / "interim",
            release=data / "release",
            checkpoints=checkpoints,
            configs=root / "configs",
        )

    def ensure(self) -> None:
        for path in (
            self.data,
            self.raw,
            self.cache,
            self.interim,
            self.release,
            self.checkpoints,
        ):
            path.mkdir(parents=True, exist_ok=True)


PATHS = ProjectPaths.from_env()


def configure_external_caches(paths: ProjectPaths = PATHS) -> dict[str, str]:
    """Point model/dataset caches at one reusable, user-overridable directory.

    Call this before importing transformers/datasets/sentence_transformers. On AutoDL,
    set QINGHAI_RAG_CACHE_DIR to a persistent data-disk path once and every stage will
    reuse downloads after process or instance restarts.
    """

    root = paths.cache / "huggingface"
    defaults = {
        "HF_HOME": root,
        "HF_DATASETS_CACHE": root / "datasets",
        "HUGGINGFACE_HUB_CACHE": root / "hub",
        "SENTENCE_TRANSFORMERS_HOME": root / "sentence_transformers",
        "TRANSFORMERS_CACHE": root / "transformers",
    }
    resolved: dict[str, str] = {}
    for key, value in defaults.items():
        resolved[key] = os.environ.setdefault(key, str(value))
        Path(resolved[key]).expanduser().mkdir(parents=True, exist_ok=True)
    return resolved


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_project_config(name: str, paths: ProjectPaths = PATHS) -> dict[str, Any]:
    return load_yaml(paths.configs / name)
