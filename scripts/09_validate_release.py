from __future__ import annotations

import argparse
import subprocess
from collections import Counter
from pathlib import Path

from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.io_utils import read_jsonl
from qinghai_rag.schemas import (
    RELEASE_MODELS,
    ChunkRecord,
    EntityRecord,
    FactRecord,
    QARecord,
    SourceRecord,
)
from qinghai_rag.source_registry import domain_matches


def validate() -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    loaded = {}
    for filename, model in RELEASE_MODELS.items():
        path = PATHS.release / filename
        if not path.exists():
            errors.append(f"Missing release file: {filename}")
            continue
        try:
            loaded[filename] = read_jsonl(path, model)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        return errors, warnings
    sources: list[SourceRecord] = loaded["qinghai_sources.jsonl"]
    entities: list[EntityRecord] = loaded["qinghai_entities.jsonl"]
    facts: list[FactRecord] = loaded["qinghai_facts.jsonl"]
    chunks: list[ChunkRecord] = loaded["qinghai_chunks_open.jsonl"]
    qa: list[QARecord] = loaded["qinghai_qa_eval.jsonl"]
    source_by_id = {item.source_id: item for item in sources}
    if len(source_by_id) != len(sources):
        errors.append("Duplicate source_id detected")
    duplicate_urls = [
        url for url, count in Counter(item.url for item in sources).items() if count > 1
    ]
    if duplicate_urls:
        errors.append(f"Duplicate source_url values: {duplicate_urls}")
    for entity in entities:
        if entity.canonical_source_id not in source_by_id:
            errors.append(
                f"Entity {entity.entity_id} references unknown source {entity.canonical_source_id}"
            )
    fact_ids = {item.fact_id for item in facts}
    for fact in facts:
        if not fact.evidence_source_id or fact.evidence_source_id not in source_by_id:
            errors.append(f"Fact {fact.fact_id} has missing/unknown evidence source")
    restricted = load_project_config("release_policy.yaml").get("restricted_domains", [])
    seen_chunk_text = set()
    for chunk in chunks:
        source = source_by_id.get(chunk.source_id)
        if not source:
            errors.append(f"Chunk {chunk.chunk_id} references unknown source {chunk.source_id}")
            continue
        if chunk.text in seen_chunk_text:
            errors.append(f"Duplicate chunk text: {chunk.chunk_id}")
        seen_chunk_text.add(chunk.text)
        if chunk.chunk_kind == "open_text":
            if not source.raw_text_release or source.release_policy.value not in {
                "full_text_allowed",
                "government_public",
            }:
                errors.append(f"Open-text chunk {chunk.chunk_id} violates source policy")
            if domain_matches(source.domain, restricted):
                errors.append(f"Restricted-domain raw text found in chunk {chunk.chunk_id}")
    for item in qa:
        if not item.unanswerable:
            if not item.evidence_source_ids:
                errors.append(f"QA {item.question_id} has no evidence sources")
            for source_id in item.evidence_source_ids:
                if source_id not in source_by_id:
                    errors.append(f"QA {item.question_id} references unknown source {source_id}")
            for fact_id in item.evidence_fact_ids:
                if fact_id not in fact_ids:
                    errors.append(f"QA {item.question_id} references unknown fact {fact_id}")
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "data/raw"],
            cwd=PATHS.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        leaked = [path for path in tracked if not path.endswith(".gitkeep")]
        if leaked:
            errors.append(f"Raw data is tracked by git: {leaked}")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        warnings.append(f"Could not inspect git-tracked raw files: {exc}")
    return errors, warnings


def write_report(errors: list[str], warnings: list[str], path: Path) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = ["# QinghaiRAG release validation", "", f"**Status: {status}**", "", "## Errors", ""]
    lines.extend([f"- {item}" for item in errors] or ["- None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in warnings] or ["- None"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate all QinghaiRAG release artifacts")
    parser.add_argument("--report", default=str(PATHS.release / "validation_report.md"))
    args = parser.parse_args()
    errors, warnings = validate()
    write_report(errors, warnings, Path(args.report))
    print(
        f"Validation {'passed' if not errors else 'failed'}: errors={len(errors)}, warnings={len(warnings)}"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
