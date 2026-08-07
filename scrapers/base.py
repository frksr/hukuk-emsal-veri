"""Tüm scraper'ların ortak temeli."""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import orjson


class BaseScraper(ABC):
    source_name: str = "base"
    output_root: Path = Path("data")
    scraper_version: str = "1.0.0"

    def __init__(self, root: str | Path = "data", since: str | None = None):
        # `since` (YYYY-MM-DD): yalnızca bu tarihten sonraki kararlar işlenir.
        # None → tam tarama. Bkz. common/scrape_state.py
        self.since = since
        # Bu koşuda görülen EN YENİ karar tarihi — koşu sonunda imleç olarak
        # kaydedilir (koşu tarihi değil; kaynaklar geriye dönük yayın yapıyor).
        self.en_yeni_tarih: str | None = None
        self.eklenen_kayit = 0
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
        self.eklenen_kayit += 1
        self._imleci_ilerlet(record.get("decision_date"))

    # -- artımlı tazeleme yardımcıları -------------------------------------

    def _imleci_ilerlet(self, karar_tarihi) -> None:
        """Bu koşuda görülen en yeni karar tarihini takip et."""
        from common.scrape_state import tarih_normalize

        t = tarih_normalize(karar_tarihi)
        if t and (self.en_yeni_tarih is None or t > self.en_yeni_tarih):
            self.en_yeni_tarih = t

    def atlanmali_mi(self, karar_tarihi) -> bool:
        """`since` filtresine göre bu karar atlanmalı mı?

        Kaynak API tarih filtresini SUNUCU TARAFINDA desteklemiyorsa (Danıştay)
        liste aşamasında bunu çağırarak pahalı detay isteğinden kaçınırız.
        Tarih çözülemezse ATLANMAZ — eksik metadata yüzünden gerçek bir kararı
        kaçırmaktansa fazladan işlemek yeğdir.
        """
        from common.scrape_state import yeni_mi

        return not yeni_mi(karar_tarihi, self.since)

    def durumu_kaydet(self) -> None:
        """Koşu sonunda imleci kalıcı hale getir."""
        from common.scrape_state import kaydet

        kaydet(self.output_root, self.source_name,
               self.en_yeni_tarih, self.eklenen_kayit)
