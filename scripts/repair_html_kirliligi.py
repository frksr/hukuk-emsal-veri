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

#: Kaç satır birlikte işlenip commit edilsin (metin temizliği).
_PARTI = 500

#: Tek embedding API isteğinde kaç chunk gönderilsin.
_EMBED_PARTI = 64

#: Üst üste bu kadar API hatası → durdur (hatalı anahtarla binlerce
#: başarısız istek atıp para/kota yakılmasın).
_MAX_ARDISIK_HATA = 3


#: Kirli satır filtresi — count ve sayfalama sorgularında ortak.
_KIRLI_KOSUL = """
       (document ILIKE '%%<html%%'
     OR document ILIKE '%%<font%%'
     OR document ILIKE '%%<br>%%'
     OR document ILIKE '%%<body%%'
     OR document ILIKE '%%http-equiv%%'
     OR document ILIKE '%%&lt;%%')
"""


def _kirli_sorgusu() -> str:
    """Kirli satırları TEK GEÇİŞTE akıtan sorgu (sayfalama YOK).

    NEDEN SAYFALAMA YOK
    -------------------
    İlk sürüm `LIMIT/OFFSET` kullanıyordu. OFFSET atlanan satırları her
    seferinde yeniden tarar; 71138 kirli satırda 143 tur × artan offset ≈
    5 milyon gereksiz satır taraması (O(n²)) demek — saatler sürüyordu.

    İkinci sürüm keyset (`chunk_id > son`) idi: sonlanma garantisi verdi ama
    yine tur başına bir tam tarama yapıyordu.

    Şimdi sunucu tarafı (named) imleç kullanılıyor: sorgu BİR KEZ planlanır,
    tablo BİR KEZ taranır, sonuçlar parça parça akar.
    """
    return "SELECT chunk_id, document FROM rag_chunks WHERE " + _KIRLI_KOSUL + " ORDER BY chunk_id"


def _satiri_isle(chunk_id, belge, sayac, atlanan_ornekler):
    """Tek satırı temizle. Döner: yeni metin ya da None (dokunma)."""
    sayac["incelenen"] += 1
    temiz = clean_html_to_text(belge or "")

    if not temiz or len(temiz) < len(belge or "") * _MIN_KORUNAN_ORAN:
        sayac["atlanan"] += 1
        if len(atlanan_ornekler) < 5:
            atlanan_ornekler.append(
                f"{chunk_id}: {len(belge or '')} → {len(temiz)} karakter")
        return None
    if temiz == belge:
        return None          # yanlış pozitif — zaten temiz
    sayac["temizlenen"] += 1
    return temiz


def onar_chunks(dry_run: bool) -> dict:
    from services import pg

    sayac = {"incelenen": 0, "temizlenen": 0, "atlanan": 0}
    atlanan_ornekler: list[str] = []

    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                ("SELECT count(*) FROM rag_chunks WHERE " + _KIRLI_KOSUL).replace("%%", "%")
            )
            toplam = cur.fetchone()[0]
        print(f"[REPAIR] HTML izi olan chunk: {toplam}", file=sys.stderr)
        if not toplam:
            return {"toplam": 0, "temizlenen": 0, "atlanan": 0, "incelenen": 0}

        # TEK GEÇİŞ — sunucu tarafı (named) imleç.
        #
        # İlk sürüm LIMIT/OFFSET ile sayfalıyordu. OFFSET atlanan satırları HER
        # SEFERİNDE yeniden tarar: 143 tur × artan offset ≈ 5 milyon gereksiz
        # satır taraması (O(n²)). 71138 kirli satırda bu saatler sürüyordu —
        # mantık hatası değil, ama kabul edilemez.
        #
        # Sunucu tarafı imleç sonucu akıtır: tablo BİR KEZ taranır.
        # Yazma ayrı bağlantıdan yapılır — imleç açıkken aynı bağlantıda
        # commit etmek imleci geçersiz kılar.
        with pg.connection() as yazma_conn:
            with conn.cursor(name="repair_html_kirliligi") as imlec:
                imlec.itersize = _PARTI
                imlec.execute(_kirli_sorgusu().replace("%%", "%"))

                tampon: list[tuple[str, str]] = []
                for chunk_id, belge in imlec:
                    yeni_metin = _satiri_isle(chunk_id, belge, sayac, atlanan_ornekler)
                    if yeni_metin is not None:
                        tampon.append((yeni_metin, chunk_id))

                    if len(tampon) >= _PARTI:
                        _yaz(yazma_conn, tampon, dry_run)
                        tampon.clear()
                        print(f"[REPAIR] {sayac['incelenen']}/{toplam} incelendi, "
                              f"{sayac['temizlenen']} temizlendi, "
                              f"{sayac['atlanan']} atlandı", file=sys.stderr)

                if tampon:
                    _yaz(yazma_conn, tampon, dry_run)

    print(f"[REPAIR] BİTTİ — {sayac['incelenen']}/{toplam} incelendi, "
          f"{sayac['temizlenen']} temizlendi, {sayac['atlanan']} atlandı",
          file=sys.stderr)

    if atlanan_ornekler:
        print("\n[REPAIR] ATLANAN (temizlik metni aşırı kısalttı — elle bakın):",
              file=sys.stderr)
        for o in atlanan_ornekler:
            print("   ", o, file=sys.stderr)

    return {"toplam": toplam, **sayac}


#: Metni temizlenmiş ama embedding'i henüz yenilenmemiş satırların işareti.
#: DB'de tutulur — böylece embed aşaması ayrı koşuda, yarıda kesilse bile
#: KALDIĞI YERDEN devam edebilir.
_BAYAT_ISARET = "stale:html-repair"


def _yaz(conn, tampon: list[tuple[str, str]], dry_run: bool) -> None:
    """Temizlenen metni yaz + embedding'i BAYAT olarak işaretle.

    NEDEN İŞARET: ilk sürüm yeniden-embed edilecek chunk_id'leri yalnızca
    BELLEKTE tutuyordu. Embed aşaması yarıda kesilirse (iptal, timeout, API
    hatası) script yeniden çalıştırıldığında ortada temizlenecek satır
    kalmadığı için liste BOŞ oluyor ve o satırlar sessizce temiz metin +
    ESKİ vektörle kalıyordu. Kurtarma yolu yoktu.
    """
    if dry_run or not tampon:
        return
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE rag_chunks SET document = %s, embedding_model = %s "
            "WHERE chunk_id = %s",
            [(metin, _BAYAT_ISARET, cid) for metin, cid in tampon],
        )
    conn.commit()


def _bayat_sayisi(conn) -> tuple[int, int]:
    """(satır sayısı, toplam karakter) — maliyet tahmini için."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), COALESCE(sum(length(document)), 0) "
            "FROM rag_chunks WHERE embedding_model = %s", (_BAYAT_ISARET,))
        return cur.fetchone()


def _maliyet_raporu(adet: int, karakter: int) -> None:
    """API çağrısı YAPMADAN önce ne harcanacağını yazdır."""
    istek = (adet + _EMBED_PARTI - 1) // _EMBED_PARTI
    print(
        "\n" + "=" * 62
        + f"\n  YENİDEN EMBED — MALİYET TAHMİNİ"
        + "\n" + "=" * 62
        + f"\n  Chunk sayısı     : {adet:,}"
        + f"\n  Toplam karakter  : {karakter:,}"
        + f"\n  Tahmini API isteği: {istek:,}  ({_EMBED_PARTI} chunk/istek)"
        + "\n"
        + "\n  Bu bir TAHMİNDİR. Gerçek ücret sağlayıcı fiyatlandırmasına"
        + "\n  bağlıdır; kontrol edin: cloud.google.com/vertex-ai/pricing"
        + "\n" + "=" * 62 + "\n",
        file=sys.stderr,
    )


def _yeniden_embed(onayla: bool, max_embed: int | None) -> dict:
    """BAYAT işaretli chunk'ların embedding'ini yeniden üretir.

    Metin değiştiği için eski vektör artık yanlış içeriği temsil ediyor.

    GÜVENLİKLER (hepsi para kaybını önlemek için):
      * `--onayla` olmadan HİÇBİR API çağrısı yapılmaz; yalnızca tahmin basılır.
      * `--max-embed N` ile bu koşuda işlenecek chunk sayısı sınırlanabilir.
      * Üst üste _MAX_ARDISIK_HATA kez API hatası → DURDUR. Hatalı anahtarla
        binlerce başarısız istek atılmasın.
      * Sağlayıcı beklenenden az vektör dönerse o parti ATLANIR (sessiz
        eşleşme kayması olmaz).
      * İşlenen satırın işareti kaldırılır → yarıda kesilse bile ikinci koşu
        KALDIĞI YERDEN devam eder, baştan başlamaz.
    """
    from services import embeddings, pg

    model_imzasi = (
        f"{embeddings.PROVIDER}:"
        f"{embeddings.API_MODEL if embeddings.PROVIDER == 'google' else embeddings.LOCAL_MODEL}:"
        f"{embeddings.EMBEDDING_DIM}"
    )

    with pg.connection() as conn:
        adet, karakter = _bayat_sayisi(conn)
        if not adet:
            print("[REPAIR] Yeniden embed edilecek chunk yok.", file=sys.stderr)
            return {"embed_edilen": 0, "kalan": 0}

        _maliyet_raporu(adet, karakter)

        if not onayla:
            print("[REPAIR] --onayla verilmedi → HİÇBİR API ÇAĞRISI YAPILMADI.\n"
                  "         Devam etmek için aynı komutu --onayla ile çalıştırın.",
                  file=sys.stderr)
            return {"embed_edilen": 0, "kalan": adet, "onay_bekliyor": True}

        hedef = min(adet, max_embed) if max_embed else adet
        print(f"[REPAIR] {hedef:,} chunk embed edilecek "
              f"(sınır: {max_embed or 'yok'})", file=sys.stderr)

        embed_edilen = 0
        ardisik_hata = 0

        while embed_edilen < hedef:
            kalan_parti = min(_EMBED_PARTI, hedef - embed_edilen)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT chunk_id, document FROM rag_chunks "
                    "WHERE embedding_model = %s ORDER BY chunk_id LIMIT %s",
                    (_BAYAT_ISARET, kalan_parti),
                )
                rows = cur.fetchall()
            if not rows:
                break

            try:
                vektorler = embeddings.embed_passages([r[1] for r in rows])
                ardisik_hata = 0
            except Exception as e:
                ardisik_hata += 1
                print(f"[REPAIR] embedding hatası ({ardisik_hata}/"
                      f"{_MAX_ARDISIK_HATA}): {e}", file=sys.stderr)
                if ardisik_hata >= _MAX_ARDISIK_HATA:
                    print("[REPAIR] DURDURULDU — üst üste API hatası. "
                          "İşaretli satırlar korundu, sorun giderilince "
                          "aynı komutla kaldığı yerden devam eder.",
                          file=sys.stderr)
                    break
                continue

            if len(vektorler) != len(rows):
                # Eşleşme kayması olursa yanlış chunk'a yanlış vektör yazılır.
                print(f"[REPAIR] UYARI: {len(rows)} metin gönderildi, "
                      f"{len(vektorler)} vektör döndü — parti atlandı.",
                      file=sys.stderr)
                break

            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE rag_chunks SET embedding = %s, embedding_model = %s "
                    "WHERE chunk_id = %s",
                    [(v, model_imzasi, r[0]) for r, v in zip(rows, vektorler)],
                )
            conn.commit()
            embed_edilen += len(rows)
            print(f"[REPAIR] embed {embed_edilen:,}/{hedef:,}", file=sys.stderr)

        kalan, _ = _bayat_sayisi(conn)

    print(f"[REPAIR] Embed bitti: {embed_edilen:,} yenilendi, "
          f"{kalan:,} bayat kaldı.", file=sys.stderr)
    if kalan:
        print("[REPAIR] Kalanlar için aynı komutu tekrar çalıştırın — "
              "kaldığı yerden devam eder.", file=sys.stderr)
    return {"embed_edilen": embed_edilen, "kalan": kalan}


def onar_parquet(dry_run: bool) -> dict:
    """Karar tam metni parquet'ini onarır (karar detay sayfası oradan okur)."""
    import duckdb

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
    ap = argparse.ArgumentParser(
        description="Karar metinlerindeki HTML kirliliğini onar",
        epilog="ÖNEMLİ: --reembed tek başına HİÇBİR API çağrısı yapmaz; "
               "önce maliyet tahminini basar. Gerçekten çalıştırmak için "
               "--onayla da vermelisiniz.",
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="sadece raporla, hiçbir şey yazma (API çağrısı da yok)")
    ap.add_argument("--reembed", action="store_true",
                    help="temizlenen chunk'ların embedding'ini yenile")
    ap.add_argument("--onayla", action="store_true",
                    help="--reembed ile birlikte: API çağrılarını GERÇEKTEN yap")
    ap.add_argument("--max-embed", type=int, default=None,
                    help="bu koşuda en fazla N chunk embed et (maliyet freni)")
    ap.add_argument("--parquet", action="store_true",
                    help="karar tam metni parquet'ini de onar")
    ap.add_argument("--skip-db", action="store_true", help="rag_chunks'a dokunma")
    args = ap.parse_args()

    if args.dry_run:
        print("[REPAIR] DRY-RUN — hiçbir şey değiştirilmeyecek, "
              "API çağrısı YAPILMAYACAK.\n", file=sys.stderr)

    sonuc: dict = {}
    if not args.skip_db:
        sonuc["rag_chunks"] = onar_chunks(args.dry_run)

    if args.reembed and not args.dry_run:
        sonuc["embed"] = _yeniden_embed(args.onayla, args.max_embed)
    elif args.reembed and args.dry_run:
        print("[REPAIR] --dry-run ile --reembed birlikte verildi → "
              "embed aşaması ATLANDI.", file=sys.stderr)

    if args.parquet:
        sonuc["parquet"] = onar_parquet(args.dry_run)

    print("\n[REPAIR] SONUÇ:", sonuc, file=sys.stderr)

    if not args.reembed and sonuc.get("rag_chunks", {}).get("temizlenen"):
        print(
            "\n[REPAIR] NOT: metinler temizlendi, embedding'ler BAYAT olarak "
            "işaretlendi.\n         Arama kalitesinin tam düzelmesi için:\n"
            "           python -m scripts.repair_html_kirliligi --reembed\n"
            "         (önce tahmini basar; onaylamak için --onayla ekleyin)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
