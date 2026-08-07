"""Ortak dependency'ler — kaba (coarse) istek hızı sınırı.

DİKKAT — bu, `api/kota.py` ile AYNI ŞEY DEĞİLDİR:

  * `api/kota.py`  → iş kuralı. DB tabanlı, advisory-lock ile atomik, plan/kredi
                     bilir, worker'lar arası tutarlıdır. Kullanıcının "hakkı"nı
                     yönetir. Asıl kota mekanizması budur.
  * `api/deps.py`  → ucuz bir DoS emniyet supabı. Process-içi bellekte tutulur,
                     DB'ye hiç dokunmaz, bu yüzden DB henüz devreye girmeden
                     saniyede yüzlerce istek gönderen bir istemciyi keser.

Process-içi olduğu için gerçek limit = RATE_MAX_REQUESTS × worker sayısı.
Bu bilinçlidir: burada amaç adil paylaşım değil, tek bir istemcinin process'i
boğmasını engellemektir. Kesin/paylaşımlı limit gerekiyorsa kota.py kullanılır.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from api.net import client_ip

# IP → istek zaman damgaları
_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_WINDOW_SEC = 60
RATE_MAX_REQUESTS = 30  # dk başına IP başına (worker başına)

# Bellek sızıntısı önlemi: _rate_buckets eskiden hiç temizlenmiyordu, her
# görülen IP kalıcı bir dict anahtarı bırakıyordu. Uzun ömürlü process'te
# bu sınırsız büyür. Periyodik olarak boşalmış kovaları siliyoruz.
_GC_EVERY_SEC = 300
_last_gc = 0.0


def _gc(now: float) -> None:
    global _last_gc
    if now - _last_gc < _GC_EVERY_SEC:
        return
    _last_gc = now
    cutoff = now - RATE_WINDOW_SEC
    stale = [ip for ip, ts in _rate_buckets.items() if not ts or ts[-1] <= cutoff]
    for ip in stale:
        _rate_buckets.pop(ip, None)


def rate_limit(request: Request):
    """IP başına dakikada N istek (worker başına)."""
    # Eskiden request.client.host okunuyordu; LB arkasında bu TEK bir adres
    # (LB'nin kendisi) olduğundan tüm kullanıcılar aynı kovayı paylaşıp
    # birbirini 429'a düşürüyordu. client_ip() güvenilir proxy zincirini çözer.
    ip = client_ip(request)
    now = time.time()
    _gc(now)

    cutoff = now - RATE_WINDOW_SEC
    bucket = [t for t in _rate_buckets[ip] if t > cutoff]
    if len(bucket) >= RATE_MAX_REQUESTS:
        _rate_buckets[ip] = bucket
        raise HTTPException(429, detail="Çok sık istek. Lütfen 1 dakika bekleyin.")
    bucket.append(now)
    _rate_buckets[ip] = bucket
