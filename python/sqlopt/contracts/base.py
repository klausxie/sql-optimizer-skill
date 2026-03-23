from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Type, TypeVar

T = TypeVar("T")


def dataclass_to_json(obj: Any) -> str:
    if is_dataclass(obj):
        return json.dumps(asdict(obj), indent=2, ensure_ascii=False)
    raise TypeError(f"Expected dataclass instance, got {type(obj)}")


def json_to_dataclass(cls: Type[T], data: dict | str) -> T:
    if isinstance(data, str):
        data = json.loads(data)
    return cls(**data)


def load_json_file(file_path: str | Path) -> dict[str, Any]:
    with Path(file_path).open(encoding="utf-8") as f:
        return dict(json.load(f))


def save_json_file(data: Any, file_path: str | Path) -> None:
    if is_dataclass(data):
        data = asdict(data)
    with Path(file_path).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
