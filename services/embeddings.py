"""Provider-agnostic embedding katmanı + sorgu embedding cache'i.

Amaç:
- Embedding üretimini tek bir arayüzün arkasına almak (Google API / lokal e5).
  Böylece sağlayıcı değiştirmek bir config + yeniden indeksleme meselesi olur,
  kodu baştan yazmaya gerek kalmaz (bkz. PGVECTOR_GOC_PLANI.md, Faz 2).
- Sorgu (query) embedding'lerini process içi LRU + TTL cache'te tutmak.
  Hukuk aramaları çok tekrar eder; cache hit'te API çağrısı yapılmaz.

Kullanım:
    from services import embeddings
    v   = embeddings.embed_query("kira tespit davası zamanaşımı")   # list[float]
    vs  = embeddings.embed_passages(["...", "..."])                 # list[list[float]]

Env:
    EMBEDDING_PROVIDER   google | local            (vars. google)
    EMBEDDING_API_MODEL  text-embedding-004         (Google modeli)
    EMBEDDING_DIM        768                        (pgvector kolon boyutu ile aynı)
    EMBEDDING_LOCAL_MODEL intfloat/multilingual-e5-base  (provider=local için)
    GOOGLE_API_KEY       <secret>                   (provider=google için)
    EMBED_CACHE_SIZE     2048                       (sorgu cache kapasitesi)
    EMBED_CACHE_TTL      3600                       (saniye)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from typing import List

log = logging.getLogger("services.embeddings")

PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "google").lower()
API_MODEL = os.environ.get("EMBEDDING_API_MODEL", "gemini-embedding-001")
LOCAL_MODEL = os.environ.get("EMBEDDING_LOCAL_MODEL", "intfloat/multilingual-e5-base")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "768"))

_CACHE_SIZE = int(os.environ.get("EMBED_CACHE_SIZE", "2048"))
_CACHE_TTL = float(os.environ.get("EMBED_CACHE_TTL", "3600"))


# ---------------------------------------------------------------------------
# Sorgu embedding cache'i — thread-safe LRU + TTL
# ---------------------------------------------------------------------------
class _TTLCache:
    """Basit thread-safe LRU + TTL cache (process içi)."""

    def __init__(self, maxsize: int, ttl: float):
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: "OrderedDict[str, tuple[float, list[float]]]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            ts, value = item
            if self.ttl > 0 and (time.time() - ts) > self.ttl:
                # Süresi dolmuş
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: list[float]):
        with self._lock:
            self._data[key] = (time.time(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._data),
                "maxsize": self.maxsize,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
            }


_query_cache = _TTLCache(_CACHE_SIZE, _CACHE_TTL)


def cache_stats() -> dict:
    return _query_cache.stats()


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


# ---------------------------------------------------------------------------
# Google provider (varsayılan) — REST (httpx) ile; deprecated google.generativeai
# kütüphanesine bağlı DEĞİL. Model + outputDimensionality tam kontrol; 429 retry.
# ---------------------------------------------------------------------------
_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_MAX_RETRIES = int(os.environ.get("EMBED_MAX_RETRIES", "6"))


def _model_path() -> str:
    return API_MODEL if API_MODEL.startswith("models/") else f"models/{API_MODEL}"


def _api_key() -> str:
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("GOOGLE_API_KEY yok — embedding üretilemiyor.")
    return key


def _l2_normalize(vec: List[float]) -> List[float]:
    import math
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def _post_with_retry(url: str, payload: dict):
    """429/5xx için üstel backoff'lu POST."""
    import time as _t
    import httpx
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            r = httpx.post(url, json=payload, timeout=60.0)
            if r.status_code in (429, 500, 503):
                wait = min(2 ** attempt, 30)
                log.warning("Embedding API %s — %ss bekleniyor (deneme %d/%d)",
                            r.status_code, wait, attempt + 1, _MAX_RETRIES)
                _t.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError:
            raise
        except Exception as e:  # ağ hatası vb.
            last_exc = e
            wait = min(2 ** attempt, 30)
            log.warning("Embedding API ağ hatası (%s) — %ss (deneme %d/%d)",
                        e, wait, attempt + 1, _MAX_RETRIES)
            _t.sleep(wait)
    raise RuntimeError(f"Embedding API {_MAX_RETRIES} denemede başarısız: {last_exc}")


def _google_embed(texts: List[str], task_type: str) -> List[List[float]]:
    """task_type: 'retrieval_query' | 'retrieval_document'. REST batchEmbedContents."""
    if not texts:
        return []
    key = _api_key()
    model = _model_path()
    tt = task_type.upper()  # RETRIEVAL_QUERY / RETRIEVAL_DOCUMENT

    def _one_request(t: str) -> dict:
        req = {
            "model": model,
            "content": {"parts": [{"text": t}]},
            "taskType": tt,
        }
        if EMBEDDING_DIM:
            req["outputDimensionality"] = EMBEDDING_DIM
        return req

    url = f"{_API_BASE}/{model}:batchEmbedContents?key={key}"
    payload = {"requests": [_one_request(t) for t in texts]}
    data = _post_with_retry(url, payload)
    embs = data.get("embeddings", [])
    out = [e.get("values", []) for e in embs]
    # MRL ile kısaltılmış (768) embedding'lerde normalize önerilir → cosine tutarlı.
    return [_l2_normalize(v) for v in out]


# ---------------------------------------------------------------------------
# Lokal provider (Faz 2 kaçış kapısı) — sentence-transformers kuruluysa çalışır
# ---------------------------------------------------------------------------
_local_model = None


def _ensure_local():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer  # lazy
        _local_model = SentenceTransformer(LOCAL_MODEL, device="cpu")
    return _local_model


def _local_embed(texts: List[str], is_query: bool) -> List[List[float]]:
    model = _ensure_local()
    # e5 prefix gereksinimi
    prefix = "query: " if is_query else "passage: "
    payload = [f"{prefix}{t}" for t in texts]
    return model.encode(payload, normalize_embeddings=True,
                        show_progress_bar=False).tolist()


# ---------------------------------------------------------------------------
# Genel API
# ---------------------------------------------------------------------------
def embed_query(text: str) -> List[float]:
    """Tek bir arama sorgusunu embed et (cache'li)."""
    key = f"{PROVIDER}:{API_MODEL if PROVIDER=='google' else LOCAL_MODEL}:{EMBEDDING_DIM}:q:{_norm(text)}"
    cached = _query_cache.get(key)
    if cached is not None:
        return cached

    if PROVIDER == "local":
        vec = _local_embed([text], is_query=True)[0]
    else:
        vec = _google_embed([text], task_type="retrieval_query")[0]

    _query_cache.set(key, vec)
    return vec


def embed_passages(texts: List[str]) -> List[List[float]]:
    """Doküman/chunk listesini embed et (indeksleme için; cache'siz)."""
    if not texts:
        return []
    if PROVIDER == "local":
        return _local_embed(texts, is_query=False)
    return _google_embed(texts, task_type="retrieval_document")


def embed_passage(text: str) -> List[float]:
    return embed_passages([text])[0]
