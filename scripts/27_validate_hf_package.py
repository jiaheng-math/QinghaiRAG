from __future__ import annotations

import argparse
import json
from pathlib import Path

from qinghai_rag.hf_release import validate_release_package


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a local QinghaiRAG Hugging Face release package"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/release/hf_publish_v1_rc1"),
    )
    args = parser.parse_args()

    report = validate_release_package(args.input)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
