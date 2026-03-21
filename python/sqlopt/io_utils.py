from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Any


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, row: Any) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def merge_init_sql_units(path: Path, new_units: list[dict[str, Any]]) -> None:
    """Merge SQL units into init/sql_units.json (JSON array), keyed by sqlKey."""
    ensure_dir(path.parent)
    existing: list[dict[str, Any]] = []
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            existing = [x for x in raw if isinstance(x, dict)]
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for u in existing:
        k = str(u.get("sqlKey") or "")
        if k and k not in by_key:
            order.append(k)
        if k:
            by_key[k] = u
    for u in new_units:
        k = str(u.get("sqlKey") or "")
        if not k:
            continue
        if k not in by_key:
            order.append(k)
        by_key[k] = u
    merged = [by_key[k] for k in order if k in by_key]
    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class JsonlWriter:
    """批量 JSONL 写入器，减少文件打开次数。

    使用缓冲区批量写入，适合高频写入场景。
    需要显式调用 flush() 或 close() 确保数据落盘。

    Example:
        with JsonlWriter(path) as writer:
            for row in rows:
                writer.append(row)
            # 自动 flush 和 close
    """

    def __init__(self, path: Path, buffer_size: int = 100) -> None:
        """初始化写入器。

        Args:
            path: 目标文件路径
            buffer_size: 缓冲区大小，达到此数量时自动刷新
        """
        self.path = path
        self.buffer_size = buffer_size
        self._buffer: list[Any] = []
        self._file: Any = None
        self._opened = False

    def _ensure_open(self) -> None:
        if not self._opened:
            ensure_dir(self.path.parent)
            self._file = self.path.open("a", encoding="utf-8")
            self._opened = True

    def append(self, row: Any) -> None:
        """添加一行数据到缓冲区。"""
        self._buffer.append(row)
        if len(self._buffer) >= self.buffer_size:
            self.flush()

    def extend(self, rows: Iterable[Any]) -> None:
        """添加多行数据到缓冲区。"""
        for row in rows:
            self._buffer.append(row)
            if len(self._buffer) >= self.buffer_size:
                self.flush()

    def flush(self) -> None:
        """将缓冲区数据写入文件。"""
        if not self._buffer:
            return
        self._ensure_open()
        lines = [json.dumps(row, ensure_ascii=False) + "\n" for row in self._buffer]
        self._file.writelines(lines)
        self._buffer.clear()

    def close(self) -> None:
        """关闭写入器，刷新剩余数据。"""
        self.flush()
        if self._file:
            self._file.close()
            self._file = None
        self._opened = False

    def __enter__(self) -> JsonlWriter:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
