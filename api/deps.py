"""Ortak dependency'ler — auth, rate limit (sonradan), cache vs."""
from __future__ import annotations
import time
from collections import defaultdict
from fastapi import HTTPException, Request


# Basit in-memory rate limit (production'da Redis ile değişecek)
_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_WINDOW_SEC = 60
RATE_MAX_REQUESTS = 30  # dk başına IP başına


def rate_limit(request: Request):
    """IP başına dakikada N istek."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[ip]
    # Eski kayıtları temizle
    cutoff = now - RATE_WINDOW_SEC
    _rate_buckets[ip] = [t for t in bucket if t > cutoff]
    if len(_rate_buckets[ip]) >= RATE_MAX_REQUESTS:
        raise HTTPException(429, detail="Çok sık istek. Lütfen 1 dakika bekleyin.")
    _rate_buckets[ip].append(now)
