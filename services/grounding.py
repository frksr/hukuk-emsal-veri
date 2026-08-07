"""LLM çıktısındaki emsal atıflarının doğrulanması (grounding).

PROBLEM
-------
`dilekce_emsalli.py` ve `karsi_argument.py` prompt'larında LLM'e "uydurma esas/
karar numarası üretme" TALİMATI veriliyordu, ama çıktı hiçbir programatik
kontrolden geçmiyordu. Bir dil modelinin talimatı ihlal etmesi nadir değildir;
burada ihlalin bedeli, avukatın mahkemeye var olmayan bir emsal sunmasıdır.

ÇÖZÜM
-----
Üretilen metindeki tüm "2023/1234" biçimli numaraları çıkar, LLM'e bağlam
olarak VERİLEN emsallerin numaralarıyla karşılaştır. Eşleşmeyen her numara bir
"doğrulanmamış atıf"tır.

Politikalar:
    "isaretle" (varsayılan) → metin korunur, uyarı listesi döner; arayüz
                              kullanıcıya "şu atıflar doğrulanamadı" der.
    "temizle"               → doğrulanmamış numaralar metinden çıkarılıp
                              "[atıf doğrulanamadı]" ile değiştirilir.

Bilinçli olarak kapsam dışı: kanun madde numaraları (İİK 67, TBK 117). Onlar
mevzuattan gelir, emsal listesinde bulunmaları beklenmez; ayrı bir mevzuat
doğrulaması gerektirir.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable

log = logging.getLogger("services.grounding")

#: "2023/1234", "2023 / 1234", "E. 2023/1234" → yakalanan kısım: 2023/1234
#: Yıl 1900-2099 aralığında; sıra numarası 1-6 hane.
_ATIF_DESENI = re.compile(r"\b((?:19|20)\d{2})\s*/\s*(\d{1,6})\b")

#: Kanun/madde atıfları — atıf sayılmaz, filtrelenir (ör. "5271/250" gibi
#: kanun numarası/madde biçimleri yanlış pozitif üretmesin).
_KANUN_ONEKI = re.compile(
    r"(?:madde|md\.?|m\.|İİK|IIK|TBK|TTK|HMK|CMK|TCK|İYUK|IYUK|AYM|AİHS|AIHS)\s*$",
    re.IGNORECASE,
)


def _normalize(no: str | None) -> str | None:
    """'2023 / 01234' → '2023/1234'. Karşılaştırma için tekilleştirir."""
    if not no:
        return None
    m = _ATIF_DESENI.search(str(no))
    if not m:
        return None
    return f"{m.group(1)}/{int(m.group(2))}"


def izinli_atiflar(emsaller: Iterable[dict[str, Any]]) -> set[str]:
    """Bağlama verilen emsallerin esas + karar numaraları kümesi.

    `emsaller` hem `services.rag.search()` çıktısını (meta içinde) hem düz
    sözlükleri kabul eder.
    """
    izinli: set[str] = set()
    for e in emsaller or []:
        meta = e.get("meta") if isinstance(e, dict) else None
        kaynak = meta if isinstance(meta, dict) else e
        if not isinstance(kaynak, dict):
            continue
        for alan in ("case_no", "decision_no", "esas_no", "karar_no"):
            n = _normalize(kaynak.get(alan))
            if n:
                izinli.add(n)
    return izinli


def metindeki_atiflar(metin: str) -> list[tuple[str, int, int]]:
    """Metindeki (normalize_no, baslangic, bitis) üçlüleri."""
    bulunan: list[tuple[str, int, int]] = []
    for m in _ATIF_DESENI.finditer(metin or ""):
        # Hemen öncesinde kanun kısaltması varsa madde atfıdır, emsal değil.
        onceki = metin[max(0, m.start() - 12):m.start()]
        if _KANUN_ONEKI.search(onceki):
            continue
        bulunan.append((f"{m.group(1)}/{int(m.group(2))}", m.start(), m.end()))
    return bulunan


def dogrula(
    metin: str,
    emsaller: Iterable[dict[str, Any]],
    politika: str = "isaretle",
) -> dict[str, Any]:
    """LLM çıktısındaki emsal atıflarını bağlamla karşılaştır.

    Returns:
        {
          "metin": str,                  # politikaya göre işlenmiş metin
          "dogrulanmamis": [str],        # bağlamda bulunmayan numaralar
          "dogrulanan": [str],           # bağlamda bulunan numaralar
          "temiz": bool,                 # hiç doğrulanmamış atıf yok mu
          "uyari": str | None,           # kullanıcıya gösterilecek mesaj
        }
    """
    izinli = izinli_atiflar(emsaller)
    bulunan = metindeki_atiflar(metin)

    dogrulanmamis: list[str] = []
    dogrulanan: list[str] = []
    for no, _, _ in bulunan:
        (dogrulanan if no in izinli else dogrulanmamis).append(no)

    # Sırayı koruyarak tekilleştir
    dogrulanmamis = list(dict.fromkeys(dogrulanmamis))
    dogrulanan = list(dict.fromkeys(dogrulanan))

    yeni_metin = metin
    if dogrulanmamis and politika == "temizle":
        # Sondan başa doğru değiştir ki indeksler kaymasın.
        for no, bas, bit in reversed(bulunan):
            if no in dogrulanmamis:
                yeni_metin = (yeni_metin[:bas] + "[atıf doğrulanamadı]"
                              + yeni_metin[bit:])

    uyari = None
    if dogrulanmamis:
        uyari = (
            "Aşağıdaki esas/karar numaraları size sunulan emsal listesinde "
            f"BULUNAMADI, lütfen kullanmadan önce doğrulayın: "
            f"{', '.join(dogrulanmamis)}"
        )
        log.warning(
            "Grounding: %d doğrulanmamış atıf (%s)",
            len(dogrulanmamis), ", ".join(dogrulanmamis[:5]),
        )

    return {
        "metin": yeni_metin,
        "dogrulanmamis": dogrulanmamis,
        "dogrulanan": dogrulanan,
        "temiz": not dogrulanmamis,
        "uyari": uyari,
    }
