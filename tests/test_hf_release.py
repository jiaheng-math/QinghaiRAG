import json
from pathlib import Path

from qinghai_rag.config import ProjectPaths
from qinghai_rag.hf_release import CONFIG_FILES, REPORT_FILES, prepare_release_package


def _paths(tmp_path: Path) -> ProjectPaths:
    data = tmp_path / "data"
    paths = ProjectPaths(
        root=tmp_path,
        data=data,
        raw=data / "raw",
        cache=data / "cache",
        interim=data / "interim",
        release=data / "release",
        checkpoints=data / "cache" / "checkpoints",
        configs=tmp_path / "configs",
    )
    paths.ensure()
    paths.configs.mkdir(parents=True, exist_ok=True)
    return paths


def test_prepare_release_package_copies_auditable_artifacts(tmp_path: Path):
    paths = _paths(tmp_path)
    for filename, (area, source_name) in REPORT_FILES.items():
        source = getattr(paths, area) / source_name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"report {filename}", encoding="utf-8")
    for filename in CONFIG_FILES:
        (paths.configs / filename).write_text("enabled: true\n", encoding="utf-8")

    source_files = {
        "source_registry": "qinghai_sources.jsonl",
        "entities": "qinghai_entities.jsonl",
        "facts": "qinghai_facts.jsonl",
        "open_chunks": "qinghai_chunks_open.jsonl",
        "qa_benchmark": "qinghai_qa_eval.jsonl",
    }
    configs = {
        "source_registry": [{"source_id": "src_1"}],
        "entities": [{"entity_id": "ent_1"}],
        "facts": [{"fact_id": "fact_1", "manual_checked": True}],
        "open_chunks": [{"chunk_id": "chunk_1"}],
        "qa_benchmark": [{"question_id": "q_1", "manual_checked": True}],
        "audit_samples": [{"audit_id": "audit_1"}],
    }
    for config_name, filename in source_files.items():
        record = configs[config_name][0]
        (paths.release / filename).write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    output = tmp_path / "export"
    manifest = prepare_release_package(output, configs, source_files, paths)

    assert manifest["manual_review"] == {"facts": 1, "qa": 1, "audit_samples": 1}
    assert set(manifest["configs"]) == set(configs)
    assert (output / "jsonl" / "audit_samples.jsonl").exists()
    assert (output / "reports" / "eval_report.json").exists()
    assert (output / "reports" / "TECHNICAL_REPORT.md").exists()
    assert (output / "reports" / "QinghaiRAG_Technical_Report_1.0.0-rc1.pdf").exists()
    assert (output / "pipeline_configs" / "rag.yaml").exists()
    assert (output / "RELEASE_MANIFEST.json").exists()


def test_prepare_release_package_requires_reports(tmp_path: Path):
    paths = _paths(tmp_path)
    for filename in CONFIG_FILES:
        (paths.configs / filename).write_text("enabled: true\n", encoding="utf-8")

    try:
        prepare_release_package(
            tmp_path / "export",
            {"facts": [], "qa_benchmark": [], "audit_samples": []},
            {},
            paths,
        )
    except FileNotFoundError as exc:
        assert "Missing required release reports" in str(exc)
    else:
        raise AssertionError("missing reports must block a release export")
