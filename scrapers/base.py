"""Tüm scraper'ların ortak temeli."""
from __future__ import annotations
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import orjson


class BaseScraper(ABC):
    source_name: str = "base"
    output_root: Path = Path("data")
    scraper_version: str = "1.0.0"

    def __init__(self, root: str | Path = "data"):
        self.output_root = Path(root)
        self.raw_dir = self.output_root / "raw" / self.source_name
        self.cleaned_dir = self.output_root / "cleaned"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def discover(self) -> Iterable[dict]:
        """Sorgu sonuçlarından karar ID/metadata listesini yield et."""
        ...

    @abstractmethod
    async def fetch_detail(self, item: dict) -> dict | None:
        """Tek karar detayını çek + normalize et."""
        ...

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def write_raw(self, item_id: str, content: bytes | str, ext: str = "html"):
        path = self.raw_dir / f"{item_id}.{ext}"
        if isinstance(content, str):
            content = content.encode("utf-8")
        path.write_bytes(content)
        return path

    def append_cleaned(self, record: dict):
        path = self.cleaned_dir / f"{self.source_name}.jsonl"
        with path.open("ab") as f:
            f.write(orjson.dumps(record))
            f.write(b"\n")
