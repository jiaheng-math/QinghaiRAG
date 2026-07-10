from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from qinghai_rag.config import ProjectPaths
from qinghai_rag.io_utils import write_json_atomic, write_jsonl_atomic

RELEASE_VERSION = "1.0.0-rc1"

REPORT_FILES = {
    "validation_report.md": ("release", "validation_report.md"),
    "dataset_stats.json": ("interim", "dataset_stats.json"),
    "dataset_stats.md": ("interim", "dataset_stats.md"),
    "source_coverage_report.json": ("interim", "source_coverage_report.json"),
    "source_coverage_report.md": ("interim", "source_coverage_report.md"),
    "eval_report.json": ("interim", "eval_report.json"),
    "eval_report.md": ("interim", "eval_report.md"),
}

CONFIG_FILES = (
    "rag.yaml",
    "scale_targets.yaml",
    "coverage_targets.yaml",
    "release_policy.yaml",
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_release_package(
    output: str | Path,
    configs: dict[str, list[dict[str, Any]]],
    source_files: dict[str, str],
    paths: ProjectPaths,
    require_reports: bool = True,
) -> dict[str, Any]:
    output_path = Path(output)
    jsonl_dir = output_path / "jsonl"
    reports_dir = output_path / "reports"
    configs_dir = output_path / "pipeline_configs"
    for directory in (jsonl_dir, reports_dir, configs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    missing_reports = []
    copied_reports = {}
    for filename, (area, source_name) in REPORT_FILES.items():
        source = getattr(paths, area) / source_name
        if not source.exists():
            missing_reports.append(str(source))
            continue
        destination = reports_dir / filename
        shutil.copy2(source, destination)
        copied_reports[filename] = sha256_file(destination)
    if missing_reports and require_reports:
        raise FileNotFoundError(
            "Missing required release reports: " + ", ".join(missing_reports)
        )

    copied_configs = {}
    for filename in CONFIG_FILES:
        source = paths.configs / filename
        if not source.exists():
            raise FileNotFoundError(f"Missing release config: {source}")
        destination = configs_dir / filename
        shutil.copy2(source, destination)
        copied_configs[filename] = sha256_file(destination)

    jsonl_manifest = {}
    for config_name, records in configs.items():
        filename = source_files.get(config_name, f"{config_name}.jsonl")
        destination = jsonl_dir / filename
        if config_name in source_files:
            source = paths.release / filename
            if not source.exists():
                raise FileNotFoundError(f"Missing release table: {source}")
            shutil.copy2(source, destination)
        else:
            write_jsonl_atomic(destination, records, sort_key="audit_id")
        jsonl_manifest[config_name] = {
            "records": len(records),
            "path": str(destination.relative_to(output_path)),
            "sha256": sha256_file(destination),
        }

    manifest = {
        "dataset": "QinghaiRAG",
        "version": RELEASE_VERSION,
        "code_repository": "https://github.com/jiaheng-math/QinghaiRAG",
        "hub_repository": "https://huggingface.co/datasets/zhangjh123/QinghaiRAG",
        "hub_layout": "one full split per config/subset",
        "configs": jsonl_manifest,
        "reports": copied_reports,
        "pipeline_configs": copied_configs,
        "missing_optional_reports": missing_reports,
        "manual_review": {
            "facts": sum(bool(item.get("manual_checked")) for item in configs["facts"]),
            "qa": sum(bool(item.get("manual_checked")) for item in configs["qa_benchmark"]),
            "audit_samples": len(configs["audit_samples"]),
        },
    }
    write_json_atomic(output_path / "RELEASE_MANIFEST.json", manifest)
    return manifest


def upload_supporting_files(api: Any, repo_id: str, output: str | Path, token: str) -> None:
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(output),
        path_in_repo="",
        token=token,
        allow_patterns=[
            "README.md",
            "RELEASE_MANIFEST.json",
            "jsonl/**",
            "reports/**",
            "pipeline_configs/**",
        ],
        commit_message=f"Add QinghaiRAG {RELEASE_VERSION} audit package",
    )
