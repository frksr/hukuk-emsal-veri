#!/usr/bin/env python3
"""Faiz oranlarını güncelle — TCMB EVDS API'den veya elle.

Kullanım:
  # TCMB EVDS'den çek (EVDS_API_KEY env gerekli; ücretsiz: evds2.tcmb.gov.tr)
  python3 scripts/update_faiz_oranlari.py --evds

  # Elle oran gir (mevzuat değişikliğinde; örn. yasal faiz 2026 → 24)
  python3 scripts/update_faiz_oranlari.py --set yasal 2026 24.0
  python3 scripts/update_faiz_oranlari.py --set ticari_avans 2026 48.0

  # Mevcut durumu göster
  python3 scripts/update_faiz_oranlari.py --show

Cron önerisi (günlük 03:00):
  0 3 * * * cd /app && python3 scripts/update_faiz_oranlari.py --evds

EVDS seri kodları env ile değiştirilebilir (TCMB seri adlarını
güncellerse): EVDS_SERIE_AVANS, EVDS_SERIE_REESKONT
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.faiz_oranlari import kaydet, oran_meta, oran_overrides, ORANLAR_JSON  # noqa: E402

# EVDS seri kodları — Reeskont ve Avans İşlemlerinde Uygulanan Faiz Oranları
EVDS_SERIE_AVANS = os.environ.get("EVDS_SERIE_AVANS", "TP.REESKONTILAN.B")
EVDS_SERIE_REESKONT = os.environ.get("EVDS_SERIE_REESKONT", "TP.REESKONTILAN.A")
EVDS_URL = "https://evds2.tcmb.gov.tr/service/evds/"


def evds_cek() -> dict[str, dict[int, float]]:
    """EVDS'den avans + reeskont oranlarını çek (yıl bazında son değer)."""
    import httpx

    api_key = os.environ.get("EVDS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "EVDS_API_KEY yok. https://evds2.tcmb.gov.tr adresinden ücretsiz "
            "key alın ve env'e ekleyin.")

    from datetime import date
    bugun = date.today()
    start = f"01-01-{bugun.year - 6}"
    end = bugun.strftime("%d-%m-%Y")

    series = f"{EVDS_SERIE_AVANS}-{EVDS_SERIE_REESKONT}"
    url = (f"{EVDS_URL}series={series}&startDate={start}&endDate={end}"
           f"&type=json&frequency=8")  # 8 = yıllık
    resp = httpx.get(url, headers={"key": api_key}, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise SystemExit(
            "EVDS boş yanıt döndü — seri kodlarını kontrol edin "
            f"(EVDS_SERIE_AVANS={EVDS_SERIE_AVANS}). TCMB zaman zaman seri "
            "adlarını değiştirir; evds2.tcmb.gov.tr'den doğrulayın.")

    avans_kod = EVDS_SERIE_AVANS.replace(".", "_")
    reeskont_kod = EVDS_SERIE_REESKONT.replace(".", "_")

    avans: dict[int, float] = {}
    reeskont: dict[int, float] = {}
    for it in items:
        tarih = str(it.get("Tarih", ""))
        yil = None
        for parca in tarih.replace(".", "-").split("-"):
            if len(parca) == 4 and parca.isdigit():
                yil = int(parca)
                break
        if yil is None:
            continue
        try:
            if it.get(avans_kod) not in (None, ""):
                avans[yil] = float(it[avans_kod])
            if it.get(reeskont_kod) not in (None, ""):
                reeskont[yil] = float(it[reeskont_kod])
        except (TypeError, ValueError):
            continue

    sonuc: dict[str, dict[int, float]] = {}
    if avans:
        sonuc["ticari_avans"] = avans
    if reeskont:
        sonuc["tcmb_reeskont"] = reeskont
    if not sonuc:
        raise SystemExit("EVDS yanıtından oran çıkarılamadı.")
    return sonuc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evds", action="store_true", help="TCMB EVDS'den çek")
    ap.add_argument("--set", nargs=3, metavar=("TUR", "YIL", "ORAN"),
                    help="Elle oran gir: yasal|ticari_avans|tcmb_reeskont YIL ORAN")
    ap.add_argument("--show", action="store_true", help="Mevcut durumu göster")
    args = ap.parse_args()

    if args.show or (not args.evds and not args.set):
        print("Dosya:", ORANLAR_JSON)
        print("Meta :", json.dumps(oran_meta(), ensure_ascii=False, indent=2))
        for tur in ("yasal", "ticari_avans", "tcmb_reeskont"):
            ov = oran_overrides(tur)
            print(f"{tur}: {json.dumps(ov, ensure_ascii=False) if ov else '(override yok — statik fallback)'}")
        return

    if args.evds:
        tablolar = evds_cek()
        kaydet(tablolar, kaynak="TCMB EVDS")
        print("EVDS'den güncellendi:",
              {k: f"{len(v)} yıl" for k, v in tablolar.items()})

    if args.set:
        tur, yil, oran = args.set
        kaydet({tur: {int(yil): float(oran)}}, kaynak="manuel")
        print(f"Kaydedildi: {tur} {yil} → %{oran}")


if __name__ == "__main__":
    main()
