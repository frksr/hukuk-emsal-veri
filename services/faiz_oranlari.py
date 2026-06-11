"""Faiz oranı deposu — statik tablo yerine güncellenebilir JSON kaynağı.

SORUN: faiz_hesaplayici.py'daki oranlar elle yazılmış sözlüklerdi; TCMB oran
değiştirdiğinde hesap sessizce yanlışlanıyordu (hukuk ürününde güven riski).

ÇÖZÜM:
- Oranlar `data/faiz_oranlari.json`'dan okunur (varsa) → statik sözlükler
  yalnızca fallback.
- `scripts/update_faiz_oranlari.py` TCMB EVDS API'den (EVDS_API_KEY ile)
  veya elle (--set) oranları günceller. Cron/gece job'ına bağlanabilir.
- `oran_meta()` son güncelleme bilgisini döner → UI'da "oranlar TCMB'den
  güncellenir, son güncelleme: X" gösterilebilir.

JSON şeması:
{
  "son_guncelleme": "2026-06-09T03:00:00+03:00",
  "kaynak": "TCMB EVDS",
  "tablolar": {
    "yasal":         {"2024": 9.0,  "2025": 9.0, ...},
    "ticari_avans":  {"2024": 45.0, ...},
    "tcmb_reeskont": {"2024": 48.0, ...}
  }
}
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ORANLAR_JSON = Path(os.environ.get(
    "FAIZ_ORANLARI_JSON", str(ROOT / "data" / "faiz_oranlari.json")))

_lock = threading.Lock()
_cache: dict[str, Any] | None = None
_cache_mtime: float | None = None

GECERLI_TABLOLAR = {"yasal", "ticari_avans", "tcmb_reeskont"}


def _load() -> dict[str, Any] | None:
    """JSON dosyasını oku — mtime değişmediyse cache'ten dön."""
    global _cache, _cache_mtime
    try:
        mtime = ORANLAR_JSON.stat().st_mtime
    except OSError:
        return None
    with _lock:
        if _cache is not None and _cache_mtime == mtime:
            return _cache
        try:
            data = json.loads(ORANLAR_JSON.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(data, dict) or "tablolar" not in data:
            return None
        _cache, _cache_mtime = data, mtime
        return data


def oran_overrides(faiz_turu: str) -> dict[int, float]:
    """JSON'daki yıl→oran sözlüğü (yoksa boş)."""
    data = _load()
    if not data:
        return {}
    tablo = (data.get("tablolar") or {}).get(faiz_turu) or {}
    sonuc: dict[int, float] = {}
    for yil, oran in tablo.items():
        try:
            sonuc[int(yil)] = float(oran)
        except (TypeError, ValueError):
            continue
    return sonuc


def oran_meta() -> dict[str, Any]:
    """UI için kaynak/son güncelleme bilgisi."""
    data = _load()
    if not data:
        return {
            "kaynak": "statik tablo (fallback)",
            "son_guncelleme": None,
            "otomatik": False,
        }
    return {
        "kaynak": data.get("kaynak", "JSON"),
        "son_guncelleme": data.get("son_guncelleme"),
        "otomatik": True,
    }


def kaydet(tablolar: dict[str, dict[int | str, float]], kaynak: str) -> None:
    """Oranları JSON'a yaz (update script'i kullanır)."""
    from datetime import datetime, timezone

    mevcut = _load() or {"tablolar": {}}
    for tur, yillar in tablolar.items():
        if tur not in GECERLI_TABLOLAR:
            raise ValueError(f"Bilinmeyen tablo: {tur!r}")
        hedef = mevcut["tablolar"].setdefault(tur, {})
        for yil, oran in yillar.items():
            hedef[str(int(yil))] = float(oran)

    mevcut["kaynak"] = kaynak
    mevcut["son_guncelleme"] = datetime.now(timezone.utc).isoformat()

    ORANLAR_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = ORANLAR_JSON.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(mevcut, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ORANLAR_JSON)

    # cache'i düşür
    global _cache, _cache_mtime
    with _lock:
        _cache = None
        _cache_mtime = None


__all__ = ["oran_overrides", "oran_meta", "kaydet", "ORANLAR_JSON"]
