from __future__ import annotations

import argparse
from pathlib import Path

from qinghai_rag.config import PATHS, load_project_config
from qinghai_rag.coverage import compute_source_coverage, render_coverage_markdown
from qinghai_rag.io_utils import read_jsonl, write_json_atomic
from qinghai_rag.schemas import SourceRecord


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit V1 source coverage by level/topic/region")
    parser.add_argument("--json-output", default=str(PATHS.interim / "source_coverage_report.json"))
    parser.add_argument(
        "--markdown-output", default=str(PATHS.interim / "source_coverage_report.md")
    )
    args = parser.parse_args()

    report = compute_source_coverage(
        read_jsonl(PATHS.release / "qinghai_sources.jsonl", SourceRecord),
        load_project_config("coverage_targets.yaml"),
    )
    write_json_atomic(args.json_output, report)
    markdown_output = Path(args.markdown_output)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_coverage_markdown(report), encoding="utf-8")
    print(
        f"Audited {report['registered_sources']} registered sources "
        f"({report['coverage_sources']} parsed); publishers={report['unique_publishers']}, "
        f"domains={report['unique_domains']}, coverage_gaps={len(report['gaps'])}"
    )


if __name__ == "__main__":
    main()
