from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from qinghai_rag.config import PATHS
from qinghai_rag.io_utils import file_fingerprint, read_json, write_json_atomic


@dataclass
class StageState:
    name: str
    inputs: list[Path]
    outputs: list[Path]
    parameters: dict[str, Any]

    @property
    def manifest_path(self) -> Path:
        return PATHS.checkpoints / f"{self.name}.json"

    def signature(self) -> dict[str, Any]:
        return {
            "input_fingerprint": file_fingerprint(self.inputs),
            "parameters": self.parameters,
            "outputs": [str(path) for path in self.outputs],
        }

    def is_current(self) -> bool:
        previous = read_json(self.manifest_path, {})
        return all(path.exists() for path in self.outputs) and previous == self.signature()

    def commit(self) -> None:
        write_json_atomic(self.manifest_path, self.signature())


def stage_state(
    name: str,
    inputs: Iterable[str | Path],
    outputs: Iterable[str | Path],
    **parameters: Any,
) -> StageState:
    PATHS.ensure()
    return StageState(
        name, [Path(item) for item in inputs], [Path(item) for item in outputs], parameters
    )
