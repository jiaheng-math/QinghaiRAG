from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Iterable, Iterator, TypeVar

from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def read_jsonl(path: str | Path, model: type[T] | None = None) -> list[T] | list[dict[str, Any]]:
    records: list[Any] = []
    path = Path(path)
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                records.append(model.model_validate(value) if model else value)
            except Exception as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return records


def iter_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    for item in read_jsonl(path):
        yield item  # type: ignore[misc]


def _to_dict(record: BaseModel | dict[str, Any]) -> dict[str, Any]:
    return record.model_dump(mode="json") if isinstance(record, BaseModel) else record


def write_jsonl_atomic(
    path: str | Path, records: Iterable[BaseModel | dict[str, Any]], sort_key: str | None = None
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = [_to_dict(record) for record in records]
    if sort_key:
        values.sort(key=lambda value: str(value.get(sort_key, "")))
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def upsert_jsonl(
    path: str | Path,
    new_records: Iterable[BaseModel | dict[str, Any]],
    key: str,
    sort: bool = True,
) -> int:
    existing = {_to_dict(item)[key]: _to_dict(item) for item in read_jsonl(path)}
    count_before = len(existing)
    for item in new_records:
        value = _to_dict(item)
        existing[value[key]] = value
    write_jsonl_atomic(path, existing.values(), sort_key=key if sort else None)
    return len(existing) - count_before


def write_json_atomic(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def read_json(path: str | Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(content: str) -> str:
    return sha256_bytes(content.encode("utf-8"))


def file_fingerprint(paths: Iterable[str | Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(item) for item in paths):
        digest.update(str(path).encode())
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()
