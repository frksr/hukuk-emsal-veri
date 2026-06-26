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
API_MODEL = os.environ.get("EMBEDDING_API_MODEL", "text-embedding-004")
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
# Google provider (varsayılan) — container'da torch/model YOK
# ---------------------------------------------------------------------------
_google_ready = False


def _ensure_google():
    global _google_ready
    if _google_ready:
        return
    import google.generativeai as genai  # noqa
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY yok — embedding üretilemiyor.")
    genai.configure(api_key=api_key)
    _google_ready = True


def _google_embed(texts: List[str], task_type: str) -> List[List[float]]:
    """task_type: 'retrieval_query' | 'retrieval_document'."""
    import google.generativeai as genai
    _ensure_google()
    model_id = API_MODEL if API_MODEL.startswith("models/") else f"models/{API_MODEL}"
    kwargs = {"model": model_id, "task_type": task_type}
    # 768 dışı bir dim isteniyorsa ve model destekliyorsa kısalt (Matryoshka).
    if EMBEDDING_DIM and EMBEDDING_DIM != 768:
        kwargs["output_dimensionality"] = EMBEDDING_DIM

    # google-generativeai batch destekler (content=list). Hata olursa tek tek dene.
    try:
        resp = genai.embed_content(content=texts, **kwargs)
        emb = resp["embedding"]
        # Tek string verilirse düz liste döner; list verince list-of-list.
        if texts and isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
            return [emb]
        return emb
    except Exception as e:
        log.warning("Batch embed başarısız (%s) — tek tek deneniyor.", e)
        out = []
        for t in texts:
            r = genai.embed_content(content=t, **kwargs)
            out.append(r["embedding"])
        return out


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
