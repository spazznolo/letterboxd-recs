from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time


@dataclass(frozen=True)
class CacheEntry:
    path: Path

    def exists(self) -> bool:
        return self.path.exists()

    def is_fresh(self, ttl_days: int) -> bool:
        if not self.exists():
            return False
        age_seconds = time.time() - self.path.stat().st_mtime
        return age_seconds <= ttl_days * 86400

    def read_text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def write_text(self, content: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")


class FileCache:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def entry(self, *parts: str) -> CacheEntry:
        return CacheEntry(self.base_dir.joinpath(*parts))
