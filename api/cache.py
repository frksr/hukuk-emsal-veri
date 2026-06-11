"""Süreç içi TTL cache — dış bağımlılık yok (Redis gerektiğinde değiştirilebilir).

Kullanım:
    from api.cache import TTLCache

    arama_cache = TTLCache(maxsize=2048, ttl=3600)
    key = arama_cache.make_key(query, k, where)
    hit = arama_cache.get(key)
    if hit is None:
        hit = pahali_islem()
        arama_cache.set(key, hit)

Notlar:
- Thread-safe (run_blocking thread'lerinden de çağrılabilir).
- LRU tahliye: maxsize aşılınca en eski erişilen düşer.
- Multi-worker'da her worker'ın kendi cache'i olur — beta ölçeği için yeterli;
  ölçek büyüyünce Redis'e geçilir (arayüz aynı kalacak şekilde tasarlandı).
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, maxsize: int = 1024, ttl: float = 3600.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Deterministik cache anahtarı (JSON-serileştirilebilir parçalardan)."""
        raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            expires_at, value = item
            if now >= expires_at:
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        now = time.monotonic()
        with self._lock:
            self._data[key] = (now + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._data),
                "maxsize": self.maxsize,
                "ttl": self.ttl,
                "hits": self.hits,
                "misses": self.misses,
            }


# Paylaşılan cache instance'ları
arama_cache = TTLCache(maxsize=2048, ttl=3600)        # RAG arama sonuçları — 1 saat
stats_cache = TTLCache(maxsize=8, ttl=21600)          # /stats — 6 saat
trend_cache = TTLCache(maxsize=256, ttl=21600)        # trend panelleri — 6 saat
faiz_oran_cache = TTLCache(maxsize=8, ttl=86400)      # TCMB oranları — 24 saat
