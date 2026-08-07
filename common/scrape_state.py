"""Scraper koşu durumu — artımlı (incremental) tazeleme için.

NEDEN
-----
Scraper'lar her koşuda aynı anahtar kelime aramalarını BAŞTAN yapıyordu.
İndirilmiş kararlar `JobQueue` sayesinde tekrar indirilmiyordu, ama:

  * Kaynak siteler sonuçları çoğu zaman ALAKA düzeyine göre sıralar; yeni
    kararlar listenin başında çıkmayabilir → düzenli koşuda gözden kaçar.
  * Her koşu tüm arama sonuç sayfalarını yeniden gezer → gereksiz istek,
    gereksiz süre, anti-bot riskini artırır.

Bu modül "bu kaynağı en son ne zaman, hangi karar tarihine kadar taradım"
bilgisini kalıcı tutar. Scraper bir sonraki koşuda yalnızca o tarihten
sonrasını ister (destekleyen kaynaklarda sunucu tarafında, desteklemeyende
istemci tarafında süzerek).

DOSYA
-----
`data/scrape_state.json` — insan tarafından okunabilir, elle düzeltilebilir:

    {
      "yargitay": {
        "son_karar_tarihi": "2026-07-14",
        "son_kosu": "2026-08-06T20:11:03+00:00",
        "toplam_kayit": 48213
      }
    }

`son_karar_tarihi` kasıtlı olarak GÖRÜLEN EN YENİ KARARIN tarihidir, koşu
tarihi değil. Kaynak siteler kararları gecikmeli yayımladığı için koşu
tarihini imleç almak yeni kararları atlamaya yol açar.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

#: İmleci bu kadar gün geriye alarak sorgula. Kaynak siteler kararları
#: geriye dönük olarak da ekleyebildiği için (ör. 10 gün önce verilmiş bir
#: karar bugün yayımlanabilir) imleci olduğu gibi kullanmak boşluk bırakır.
GUVENLIK_PAYI_GUN = 30

_DOSYA_ADI = "scrape_state.json"


def _yol(root: str | Path) -> Path:
    return Path(root) / _DOSYA_ADI


def yukle(root: str | Path = "data") -> dict:
    p = _yol(root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def kaydet(root: str | Path, source: str, son_karar_tarihi: str | None,
           eklenen: int = 0) -> None:
    """Bir kaynağın durumunu güncelle.

    `son_karar_tarihi` yalnızca İLERİ yönde güncellenir — hatalı/eksik bir
    koşu imleci geri çekip sonraki koşuları bozmasın.
    """
    p = _yol(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    durum = yukle(root)
    mevcut = durum.get(source, {})

    onceki = mevcut.get("son_karar_tarihi")
    if son_karar_tarihi and (not onceki or son_karar_tarihi > onceki):
        mevcut["son_karar_tarihi"] = son_karar_tarihi

    mevcut["son_kosu"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mevcut["toplam_kayit"] = mevcut.get("toplam_kayit", 0) + int(eklenen)
    durum[source] = mevcut
    p.write_text(json.dumps(durum, ensure_ascii=False, indent=2), encoding="utf-8")


def since_hesapla(root: str | Path, source: str,
                  guvenlik_payi_gun: int = GUVENLIK_PAYI_GUN) -> str | None:
    """Bu kaynak için sorgulanacak başlangıç tarihi (YYYY-MM-DD) ya da None.

    None dönerse: hiç koşulmamış → tam tarama yapılmalı.
    """
    kayit = yukle(root).get(source) or {}
    son = kayit.get("son_karar_tarihi")
    if not son:
        return None
    try:
        d = date.fromisoformat(son)
    except ValueError:
        return None
    return (d - timedelta(days=guvenlik_payi_gun)).isoformat()


def tarih_normalize(deger) -> str | None:
    """Kaynaklardan gelen çeşitli tarih biçimlerini YYYY-MM-DD'ye indirger.

    Desteklenen: '2024-03-15', '15.03.2024', '15/03/2024',
    '2024-03-15T00:00:00', datetime/date nesneleri.
    Tanınmayan biçimde None döner (imleci bozmaktansa atlamak yeğdir).
    """
    if deger is None or deger == "":
        return None
    if isinstance(deger, datetime):
        return deger.date().isoformat()
    if isinstance(deger, date):
        return deger.isoformat()

    s = str(deger).strip()
    if not s:
        return None
    s = s.split("T")[0].split(" ")[0]

    # 2024-03-15
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            return date.fromisoformat(s).isoformat()
        except ValueError:
            return None
    # 15.03.2024 / 15/03/2024
    for ayrac in (".", "/"):
        if s.count(ayrac) == 2:
            try:
                g, a, y = (int(x) for x in s.split(ayrac))
            except ValueError:
                continue
            if y < 100:
                y += 2000
            try:
                return date(y, a, g).isoformat()
            except ValueError:
                return None
    return None


def yeni_mi(karar_tarihi, since: str | None) -> bool:
    """Bu karar `since` tarihinden sonra mı? Tarih çözülemezse DAHİL EDİLİR.

    Belirsizlikte karar ATLANMAZ — eksik metadata yüzünden gerçek bir kararı
    kaçırmak, birkaç fazla kayıt işlemekten daha kötüdür.
    """
    if not since:
        return True
    t = tarih_normalize(karar_tarihi)
    if t is None:
        return True
    return t >= since
