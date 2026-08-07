"""RAG retrieval kalitesi ölçümü — altın standart set üzerinde.

NEDEN
-----
Emsal aramanın doğruluğunu ölçen hiçbir mekanizma yoktu. Embedding modeli,
chunk boyutu, benzerlik eşiği veya arama SQL'i değiştiğinde sonuçların
kötüleşip kötüleşmediği ölçülemiyordu — bir hukuk ürününde bu, sessizce
yanlış emsal sunmaya devam etmek demektir.

KULLANIM
--------
    python -m scripts.rag_eval                     # varsayılan (k=5)
    python -m scripts.rag_eval --k 10 --esik 0.3
    python -m scripts.rag_eval --esik-tara         # en iyi eşiği bul
    python -m scripts.rag_eval --min-recall 0.70   # regresyon kapısı (exit 1)
    python -m scripts.rag_eval --json rapor.json   # makine okunur çıktı

GEREKSİNİM: canlı DB (DATABASE_URL) + embed edilmiş rag_chunks verisi.

Altın set formatı ve küratörleme rehberi: evals/README.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VARSAYILAN_SET = ROOT / "evals" / "altin_set.jsonl"


# ---------------------------------------------------------------------------
# Set yükleme
# ---------------------------------------------------------------------------

def altin_set_yukle(yol: Path) -> list[dict[str, Any]]:
    if not yol.exists():
        raise SystemExit(f"Altın set bulunamadı: {yol}\nBkz. evals/README.md")
    kayitlar = []
    for i, satir in enumerate(yol.read_text(encoding="utf-8").splitlines(), 1):
        satir = satir.strip()
        if not satir or satir.startswith("//"):
            continue
        try:
            kayitlar.append(json.loads(satir))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{yol}:{i} — JSON hatası: {e}")
    return kayitlar


# ---------------------------------------------------------------------------
# Tek soru değerlendirmesi
# ---------------------------------------------------------------------------

def _eslesme(sonuclar: list[dict], ornek: dict) -> tuple[bool, int | None, int]:
    """(isabet_var_mi, ilk_dogru_sira, dogru_sonuc_sayisi).

    Öncelik decision_id eşleşmesinde; kimlik verilmemişse anahtar kelime
    kontrolüne düşer (küratörlemesi daha kolay ama daha gevşek bir ölçü).
    """
    beklenen_ids = set(ornek.get("beklenen_decision_ids") or [])
    anahtarlar = [a.lower() for a in (ornek.get("beklenen_anahtar_kelimeler") or [])]

    ilk_sira: int | None = None
    dogru_sayisi = 0
    for sira, r in enumerate(sonuclar, start=1):
        did = (r.get("meta") or {}).get("decision_id")
        metin = (r.get("text") or "").lower()
        if beklenen_ids:
            uyar = did in beklenen_ids
        elif anahtarlar:
            uyar = any(a in metin for a in anahtarlar)
        else:
            uyar = False
        if uyar:
            dogru_sayisi += 1
            if ilk_sira is None:
                ilk_sira = sira
    return (ilk_sira is not None), ilk_sira, dogru_sayisi


def degerlendir(ornekler: list[dict], k: int, esik: float | None) -> dict[str, Any]:
    from services.rag import search

    satirlar: list[dict] = []
    for ornek in ornekler:
        try:
            sonuclar = search(ornek["soru"], k=k, min_similarity=esik)
            hata = None
        except Exception as e:                      # DB/ağ hatası testi bozmasın
            sonuclar, hata = [], str(e)

        negatif = ornek.get("kategori") == "negatif"
        isabet, ilk_sira, dogru = _eslesme(sonuclar, ornek)

        satirlar.append({
            "id": ornek.get("id"),
            "kategori": ornek.get("kategori", "?"),
            "soru": ornek["soru"],
            "negatif": negatif,
            "donen": len(sonuclar),
            "isabet": isabet,
            "ilk_sira": ilk_sira,
            "dogru_sayisi": dogru,
            "en_yuksek_benzerlik": round(sonuclar[0]["similarity"], 3) if sonuclar else None,
            # Negatif örnekte "başarı" = hiç sonuç dönmemesi
            "basarili": (len(sonuclar) == 0) if negatif else isabet,
            "hata": hata,
        })

    pozitifler = [s for s in satirlar if not s["negatif"]]
    negatifler = [s for s in satirlar if s["negatif"]]
    olculebilir = [s for s in pozitifler if s["hata"] is None]

    def _oran(xs: list, kosul) -> float:
        return (sum(1 for x in xs if kosul(x)) / len(xs)) if xs else 0.0

    ozet = {
        "k": k,
        "esik": esik,
        "soru_sayisi": len(satirlar),
        f"recall@{k}": round(_oran(olculebilir, lambda s: s["isabet"]), 4),
        f"precision@{k}": round(
            sum(s["dogru_sayisi"] / k for s in olculebilir) / len(olculebilir), 4
        ) if olculebilir else 0.0,
        "mrr": round(
            sum(1 / s["ilk_sira"] for s in olculebilir if s["ilk_sira"]) / len(olculebilir), 4
        ) if olculebilir else 0.0,
        "bos_yanit_orani": round(_oran(olculebilir, lambda s: s["donen"] == 0), 4),
        "negatif_dogruluk": round(_oran(negatifler, lambda s: s["basarili"]), 4),
        "hata_sayisi": sum(1 for s in satirlar if s["hata"]),
    }

    # Kategori kırılımı — kapsam boşluklarını gösterir.
    kategoriler: dict[str, dict] = {}
    for s in pozitifler:
        d = kategoriler.setdefault(s["kategori"], {"n": 0, "isabet": 0})
        d["n"] += 1
        d["isabet"] += int(s["isabet"])
    for kat, d in kategoriler.items():
        d["recall"] = round(d["isabet"] / d["n"], 4) if d["n"] else 0.0
    ozet["kategoriler"] = kategoriler

    return {"ozet": ozet, "satirlar": satirlar}


# ---------------------------------------------------------------------------
# Raporlama
# ---------------------------------------------------------------------------

def yazdir(rapor: dict, ayrintili: bool) -> None:
    o = rapor["ozet"]
    k = o["k"]
    print("\n" + "=" * 62)
    print(f"  RAG KALİTE RAPORU   (k={k}, eşik={o['esik']})")
    print("=" * 62)
    print(f"  Soru sayısı        : {o['soru_sayisi']}")
    print(f"  recall@{k}          : {o[f'recall@{k}']:.1%}   ← asıl metrik")
    print(f"  precision@{k}       : {o[f'precision@{k}']:.1%}")
    print(f"  MRR                : {o['mrr']:.3f}   (1.0 = hep ilk sırada)")
    print(f"  Boş yanıt oranı    : {o['bos_yanit_orani']:.1%}   (yüksekse eşik katı)")
    print(f"  Negatif doğruluk   : {o['negatif_dogruluk']:.1%}   (alakasız sorgu boş dönüyor mu)")
    if o["hata_sayisi"]:
        print(f"  ⚠ Hata veren sorgu : {o['hata_sayisi']}")

    if o["kategoriler"]:
        print("\n  Kategori bazında recall (kapsam boşluğu göstergesi):")
        for kat, d in sorted(o["kategoriler"].items(), key=lambda x: x[1]["recall"]):
            bar = "█" * int(d["recall"] * 20)
            uyari = "  ← KAPSAM BOŞLUĞU" if d["recall"] < 0.3 else ""
            print(f"    {kat:<14} {d['recall']:>6.1%} {bar:<20} (n={d['n']}){uyari}")

    if ayrintili:
        print("\n  Soru bazında:")
        for s in rapor["satirlar"]:
            im = "✓" if s["basarili"] else "✗"
            sira = f"sıra={s['ilk_sira']}" if s["ilk_sira"] else "bulunamadı"
            print(f"    {im} [{s['kategori']}] {s['soru'][:52]:<52} "
                  f"{s['donen']} sonuç, {sira}")
            if s["hata"]:
                print(f"        HATA: {s['hata'][:100]}")
    print()


def esik_tara(ornekler: list[dict], k: int) -> None:
    """Eşik değerini tarayıp recall/boş-yanıt dengesini gösterir."""
    print("\n  Eşik taraması (recall ↔ boş yanıt dengesi)\n")
    print(f"  {'eşik':>6} | {'recall':>7} | {'precision':>9} | {'boş yanıt':>9} | {'negatif':>7}")
    print("  " + "-" * 52)
    for esik in [0.0, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        o = degerlendir(ornekler, k=k, esik=esik)["ozet"]
        print(f"  {esik:>6.2f} | {o[f'recall@{k}']:>6.1%} | {o[f'precision@{k}']:>8.1%} | "
              f"{o['bos_yanit_orani']:>8.1%} | {o['negatif_dogruluk']:>6.1%}")
    print("\n  Seçim kuralı: negatif doğruluğu yüksek tutan EN DÜŞÜK eşik.")
    print("  Seçtiğiniz değeri .env içindeki RAG_MIN_SIMILARITY'ye yazın.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="RAG retrieval kalite ölçümü")
    ap.add_argument("--set", type=Path, default=VARSAYILAN_SET, help="altın set (jsonl)")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--esik", type=float, default=None,
                    help="benzerlik eşiği (varsayılan: RAG_MIN_SIMILARITY)")
    ap.add_argument("--esik-tara", action="store_true")
    ap.add_argument("--ayrintili", action="store_true", help="soru bazında döküm")
    ap.add_argument("--json", type=Path, help="raporu JSON olarak kaydet")
    ap.add_argument("--min-recall", type=float, default=None,
                    help="bu recall'ın altındaysa çıkış kodu 1 (CI kapısı)")
    args = ap.parse_args()

    ornekler = altin_set_yukle(args.set)
    if not ornekler:
        raise SystemExit("Altın set boş.")

    sablon = [o for o in ornekler if str(o.get("id", "")).startswith("sablon-")]
    if sablon:
        print(f"\n  ⚠ {len(sablon)} ŞABLON kayıt var — gerçek karar kimlikleriyle "
              f"doldurulmadan bu ölçüm güvenilir DEĞİLDİR (bkz. evals/README.md).")

    if args.esik_tara:
        esik_tara(ornekler, args.k)
        return 0

    rapor = degerlendir(ornekler, k=args.k, esik=args.esik)
    yazdir(rapor, args.ayrintili)

    if args.json:
        args.json.write_text(json.dumps(rapor, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"  Rapor kaydedildi: {args.json}\n")

    if args.min_recall is not None:
        gercek = rapor["ozet"][f"recall@{args.k}"]
        if gercek < args.min_recall:
            print(f"  ✗ KAPI: recall@{args.k} = {gercek:.1%} < "
                  f"eşik {args.min_recall:.1%}\n")
            return 1
        print(f"  ✓ KAPI: recall@{args.k} = {gercek:.1%} ≥ {args.min_recall:.1%}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
