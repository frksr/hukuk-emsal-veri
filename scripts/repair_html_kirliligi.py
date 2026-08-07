"""Halihazırda kaydedilmiş kararlardaki HTML kirliliğini onarır.

SORUN
-----
`scrapers/danistay.py` ve `scrapers/yargitay.py` karar metnini "içinde '<'
var mı" diye kontrol ediyordu. Kaynak API'ler HTML'i JSON içinde KAÇIŞLI
(`&lt;font face=...&gt;`) gönderdiğinde bu kontrol False dönüyor, kaçışlı
metin "düz metin" sanılıyor ve normalize sırasında entity'ler çözülünce
ham HTML olduğu gibi kaydediliyordu.

Sonuç: kararların metninde `<html><head><meta ...><font face="Verdana">`
gibi çöp kaldı. Bu yalnızca görüntüyü bozmuyor —

  * embedding vektörleri HTML gürültüsüyle üretildi  → benzerlik skorları bozuk
  * tam metin indeksinde "font", "verdana", "http-equiv" token'ları var
  * LLM'e bağlam olarak gidince hem token israfı hem kalite kaybı

Kaynak `common/normalize.py :: clean_html_to_text` içinde düzeltildi, ama
bu ESKİ KAYITLARI temizlemez. Bu script onları onarır.

NE YAPAR
--------
1. `rag_chunks.document` içinde HTML izi olan satırları bulur, temizler,
   yerine yazar (parti parti, transaction'lı).
2. `--reembed` verilirse temizlenen chunk'ların embedding'ini yeniden üretir
   — asıl kalite kazancı buradadır, ama API maliyeti vardır.
3. `--parquet` verilirse karar tam metni parquet'ini de onarır (karar detay
   sayfası oradan okunur).

KULLANIM
--------
    # Önce ölç — hiçbir şey değiştirmez
    python -m scripts.repair_html_kirliligi --dry-run

    # Metni temizle (hızlı, ucuz, güvenli)
    python -m scripts.repair_html_kirliligi

    # Metni temizle + embedding'leri yenile (yavaş, API maliyeti var)
    python -m scripts.repair_html_kirliligi --reembed

    # Parquet'i de onar (karar detay sayfası için)
    python -m scripts.repair_html_kirliligi --parquet

GÜVENLİK
--------
Temizlik yalnızca metni KISALTIR, asla bilgi eklemez. Temizlenmiş metin
şüpheli derecede kısalırsa (< %20'sine düşerse) o satır ATLANIR ve raporlanır —
parse hatasıyla karar metnini yok etmemek için.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.normalize import clean_html_to_text, html_izi_var_mi  # noqa: E402

#: Temizlik sonrası metin bunun altına düşerse veri kaybı riski var → atla.
_MIN_KORUNAN_ORAN = 0.20

#: Kaç satır birlikte işlenip commit edilsin.
_PARTI = 500


def _kirli_sorgusu() -> str:
    return """
        SELECT chunk_id, document
        FROM rag_chunks
        WHERE document ILIKE '%%<html%%'
           OR document ILIKE '%%<font%%'
           OR document ILIKE '%%<br>%%'
           OR document ILIKE '%%<body%%'
           OR document ILIKE '%%http-equiv%%'
           OR document ILIKE '%%&lt;%%'
        ORDER BY chunk_id
        LIMIT %(lim)s OFFSET %(off)s
    """


def onar_chunks(dry_run: bool, reembed: bool) -> dict:
    from services import pg

    temizlenen = atlanan = incelenen = 0
    atlanan_ornekler: list[str] = []
    temizlenen_idler: list[str] = []

    with pg.connection() as conn:
        # Toplam ölçek
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM rag_chunks WHERE "
                "document ILIKE '%<html%' OR document ILIKE '%<font%' "
                "OR document ILIKE '%<br>%' OR document ILIKE '%<body%' "
                "OR document ILIKE '%http-equiv%' OR document ILIKE '%&lt;%'"
            )
            toplam = cur.fetchone()[0]
        print(f"[REPAIR] HTML izi olan chunk: {toplam}", file=sys.stderr)
        if not toplam:
            return {"toplam": 0, "temizlenen": 0, "atlanan": 0}

        offset = 0
        while True:
            with conn.cursor() as cur:
                cur.execute(_kirli_sorgusu(), {"lim": _PARTI, "off": offset})
                rows = cur.fetchall()
            if not rows:
                break

            guncellemeler: list[tuple[str, str]] = []
            for chunk_id, belge in rows:
                incelenen += 1
                temiz = clean_html_to_text(belge or "")

                if not temiz or len(temiz) < len(belge or "") * _MIN_KORUNAN_ORAN:
                    atlanan += 1
                    if len(atlanan_ornekler) < 5:
                        atlanan_ornekler.append(
                            f"{chunk_id}: {len(belge or '')} → {len(temiz)} karakter"
                        )
                    continue
                if temiz == belge:
                    continue  # zaten temiz (yanlış pozitif eşleşme)
                guncellemeler.append((temiz, chunk_id))

            if guncellemeler and not dry_run:
                with conn.cursor() as cur:
                    cur.executemany(
                        "UPDATE rag_chunks SET document = %s WHERE chunk_id = %s",
                        guncellemeler,
                    )
                conn.commit()
            temizlenen += len(guncellemeler)
            temizlenen_idler.extend(g[1] for g in guncellemeler)

            print(f"[REPAIR] {incelenen}/{toplam} incelendi, "
                  f"{temizlenen} temizlendi, {atlanan} atlandı", file=sys.stderr)

            # dry-run'da ilerlemek için offset artır; gerçek koşuda satırlar
            # artık desene uymayacağı için offset'i SABİT tutuyoruz.
            if dry_run:
                offset += _PARTI
            if len(rows) < _PARTI:
                break

    if atlanan_ornekler:
        print("\n[REPAIR] ATLANAN (temizlik metni aşırı kısalttı — elle bakın):",
              file=sys.stderr)
        for o in atlanan_ornekler:
            print("   ", o, file=sys.stderr)

    if reembed and temizlenen_idler and not dry_run:
        _yeniden_embed(temizlenen_idler)

    return {"toplam": toplam, "temizlenen": temizlenen, "atlanan": atlanan}


def _yeniden_embed(chunk_idler: list[str]) -> None:
    """Temizlenen chunk'ların embedding'ini yeniden üretir.

    Metin değiştiği için eski vektör artık yanlış içeriği temsil ediyor.
    Bu adım API maliyeti doğurur; o yüzden ayrı bir bayrağa bağlı.
    """
    from services import embeddings, pg

    print(f"[REPAIR] {len(chunk_idler)} chunk yeniden embed ediliyor...",
          file=sys.stderr)
    parti = 64
    with pg.connection() as conn:
        for i in range(0, len(chunk_idler), parti):
            dilim = chunk_idler[i:i + parti]
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT chunk_id, document FROM rag_chunks "
                    "WHERE chunk_id = ANY(%s)", (dilim,),
                )
                rows = cur.fetchall()
            if not rows:
                continue
            try:
                vektorler = embeddings.embed_passages([r[1] for r in rows])
            except Exception as e:
                print(f"[REPAIR] embedding hatası ({i}): {e}", file=sys.stderr)
                continue
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE rag_chunks SET embedding = %s WHERE chunk_id = %s",
                    [(v, r[0]) for r, v in zip(rows, vektorler)],
                )
            conn.commit()
            print(f"[REPAIR] embed {min(i + parti, len(chunk_idler))}/"
                  f"{len(chunk_idler)}", file=sys.stderr)


def onar_parquet(dry_run: bool) -> dict:
    """Karar tam metni parquet'ini onarır (karar detay sayfası oradan okur)."""
    import duckdb
    import pandas as pd

    yol = Path(os.environ.get(
        "DECISIONS_PARQUET", str(ROOT / "data" / "final" / "all_decisions.parquet")))
    if not yol.exists():
        print(f"[REPAIR] parquet yok, atlanıyor: {yol}", file=sys.stderr)
        return {"parquet": "yok"}

    df = duckdb.sql(f"SELECT * FROM '{yol}'").df()
    print(f"[REPAIR] parquet: {len(df)} karar", file=sys.stderr)

    sayac = {"temizlenen": 0, "atlanan": 0}
    for kolon in ("cleaned_text", "raw_text"):
        if kolon not in df.columns:
            continue

        def _temizle(v):
            if not isinstance(v, str) or not html_izi_var_mi(v):
                return v
            t = clean_html_to_text(v)
            if not t or len(t) < len(v) * _MIN_KORUNAN_ORAN:
                sayac["atlanan"] += 1
                return v
            sayac["temizlenen"] += 1
            return t

        df[kolon] = df[kolon].map(_temizle)

    if "char_count" in df.columns and "cleaned_text" in df.columns:
        df["char_count"] = df["cleaned_text"].map(
            lambda v: len(v) if isinstance(v, str) else 0)

    print(f"[REPAIR] parquet: {sayac['temizlenen']} alan temizlendi, "
          f"{sayac['atlanan']} atlandı", file=sys.stderr)

    if not dry_run and sayac["temizlenen"]:
        yedek = yol.with_suffix(".parquet.html-kirli-yedek")
        if not yedek.exists():
            yol.rename(yedek)
            print(f"[REPAIR] yedek: {yedek}", file=sys.stderr)
        df.to_parquet(yol, index=False)
        print(f"[REPAIR] parquet yazıldı: {yol}", file=sys.stderr)

    return sayac


def main() -> int:
    ap = argparse.ArgumentParser(description="Karar metinlerindeki HTML kirliliğini onar")
    ap.add_argument("--dry-run", action="store_true", help="sadece raporla, yazma")
    ap.add_argument("--reembed", action="store_true",
                    help="temizlenen chunk'ların embedding'ini yenile (API maliyeti)")
    ap.add_argument("--parquet", action="store_true",
                    help="karar tam metni parquet'ini de onar")
    ap.add_argument("--skip-db", action="store_true", help="rag_chunks'a dokunma")
    args = ap.parse_args()

    if args.dry_run:
        print("[REPAIR] DRY-RUN — hiçbir şey değiştirilmeyecek.\n", file=sys.stderr)

    sonuc = {}
    if not args.skip_db:
        sonuc["rag_chunks"] = onar_chunks(args.dry_run, args.reembed)
    if args.parquet:
        sonuc["parquet"] = onar_parquet(args.dry_run)

    print("\n[REPAIR] SONUÇ:", sonuc, file=sys.stderr)
    if not args.reembed and sonuc.get("rag_chunks", {}).get("temizlenen"):
        print(
            "\n[REPAIR] NOT: metinler temizlendi ama embedding'ler HÂLÂ eski "
            "(HTML'li) metinden üretilmiş durumda. Arama kalitesinin tam "
            "düzelmesi için --reembed ile tekrar çalıştırın.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
