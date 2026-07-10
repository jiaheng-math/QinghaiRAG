from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from qinghai_rag.config import ProjectPaths
from qinghai_rag.evidence_minimization import contains_adjacent_personal_field
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
    "TECHNICAL_REPORT.md": ("root", "docs/TECHNICAL_REPORT.md"),
    "QinghaiRAG_Technical_Report_1.0.0-rc1.pdf": (
        "root",
        "output/pdf/QinghaiRAG_Technical_Report_1.0.0-rc1.pdf",
    ),
}

CONFIG_FILES = (
    "rag.yaml",
    "scale_targets.yaml",
    "coverage_targets.yaml",
    "release_policy.yaml",
)

PRIVATE_PATH_PATTERN = re.compile(
    r"(?:/root/|/Users/|[A-Za-z]:\\\\Users\\\\|autodl-container-|autodl-tmp/)"
)
REVIEWER_EMAIL_PATTERN = re.compile(r"reviewer\s*[:=][^;\n]*@[\w.-]+", re.IGNORECASE)


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


def validate_release_package(output: str | Path) -> dict[str, Any]:
    output_path = Path(output)
    manifest_path = output_path / "RELEASE_MANIFEST.json"
    errors: list[str] = []
    checked_files = 0

    if not manifest_path.exists():
        return {"status": "FAIL", "errors": ["Missing RELEASE_MANIFEST.json"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected_files: list[tuple[Path, str, int | None]] = []
    for config_name, metadata in manifest.get("configs", {}).items():
        expected_files.append(
            (
                output_path / metadata["path"],
                metadata["sha256"],
                int(metadata["records"]),
            )
        )
        if not config_name:
            errors.append("Manifest contains an empty config name")
    for filename, checksum in manifest.get("reports", {}).items():
        expected_files.append((output_path / "reports" / filename, checksum, None))
    for filename, checksum in manifest.get("pipeline_configs", {}).items():
        expected_files.append((output_path / "pipeline_configs" / filename, checksum, None))

    for path, expected_sha256, expected_rows in expected_files:
        if not path.exists():
            errors.append(f"Missing packaged file: {path.relative_to(output_path)}")
            continue
        checked_files += 1
        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected_sha256:
            errors.append(f"Checksum mismatch: {path.relative_to(output_path)}")
        if expected_rows is not None:
            actual_rows = sum(1 for line in path.open(encoding="utf-8") if line.strip())
            if actual_rows != expected_rows:
                errors.append(
                    f"Row-count mismatch: {path.relative_to(output_path)} "
                    f"expected={expected_rows} actual={actual_rows}"
                )

    for path in (output_path / "jsonl").glob("*.jsonl"):
        text = path.read_text(encoding="utf-8")
        if PRIVATE_PATH_PATTERN.search(text):
            errors.append(f"Private/local path found in {path.relative_to(output_path)}")
        if REVIEWER_EMAIL_PATTERN.search(text):
            errors.append(f"Reviewer email found in {path.relative_to(output_path)}")

    facts_path = output_path / "jsonl" / "qinghai_facts.jsonl"
    if facts_path.exists():
        for line_number, line in enumerate(facts_path.open(encoding="utf-8"), start=1):
            if not line.strip():
                continue
            try:
                fact = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"Invalid packaged fact JSON at line {line_number}")
                continue
            if contains_adjacent_personal_field(fact.get("evidence_text")):
                errors.append(
                    f"Unrelated personal field in packaged fact at line {line_number}"
                )

    required_support = {
        output_path / "README.md",
        output_path / "reports" / "TECHNICAL_REPORT.md",
        output_path / "reports" / "QinghaiRAG_Technical_Report_1.0.0-rc1.pdf",
    }
    for path in required_support:
        if not path.exists():
            errors.append(f"Missing required supporting file: {path.relative_to(output_path)}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "version": manifest.get("version"),
        "configs": {
            name: metadata.get("records")
            for name, metadata in manifest.get("configs", {}).items()
        },
        "checked_manifest_files": checked_files,
        "errors": errors,
    }
