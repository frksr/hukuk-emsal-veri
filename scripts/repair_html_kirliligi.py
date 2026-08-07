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
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.normalize import (  # noqa: E402
    HTML_IZI_DESENI,
    clean_html_to_text,
    html_izi_var_mi,
)

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
    """Anahtar-tabanlı (keyset) sayfalama.

    NEDEN OFFSET DEĞİL
    ------------------
    İlk sürüm `LIMIT/OFFSET` kullanıyordu. OFFSET atlanan satırları HER
    SEFERİNDE yeniden tarar; 71138 kirli satırda ~5 milyon gereksiz satır
    taraması (O(n²)) demekti — saatler sürüyordu.

    NEDEN SUNUCU TARAFI İMLEÇ DE DEĞİL
    ----------------------------------
    Sunucu tarafı (named) imleç `DECLARE ... CURSOR` yapar ve bu bir
    TRANSACTION gerektirir. `services/pg.py` havuzu `autocommit=True` ile
    açılıyor; autocommit'te DECLARE anında commit'lenir, imleç yok olur ve
    ilk FETCH "cursor does not exist" ile patlar. (Cloud Run job'u tam olarak
    bu yüzden anında düştü.)

    KEYSET NEDEN HIZLI
    ------------------
    `ORDER BY chunk_id LIMIT N` sayesinde Postgres birincil anahtar indeksi
    üzerinde ilerler, filtreyi giderken uygular ve N eşleşme bulunca DURUR.
    Kirli satırlar toplamın ~%43'ü olduğundan 500 eşleşme birkaç yüz satır
    içinde bulunur — tur başına tam tarama YOKTUR.

    `chunk_id` birincil anahtar ve kesin artan olduğundan imleç her turda
    ilerlemeyi GARANTİ eder — satır güncellensin ya da güncellenmesin.
    """
    return f"""
        SELECT chunk_id, document
        FROM rag_chunks
        WHERE chunk_id > %(son)s
          AND {_KIRLI_KOSUL}
        ORDER BY chunk_id
        LIMIT %(lim)s
    """


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


def onar_chunks(dry_run: bool, max_rows: int | None = None) -> dict:
    from services import pg

    sayac = {"incelenen": 0, "temizlenen": 0, "atlanan": 0}
    atlanan_ornekler: list[str] = []

    t_baslangic = time.perf_counter()
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                ("SELECT count(*) FROM rag_chunks WHERE " + _KIRLI_KOSUL).replace("%%", "%")
            )
            toplam = cur.fetchone()[0]
        print(f"[REPAIR] HTML izi olan chunk: {toplam}  "
              f"(sayım {time.perf_counter() - t_baslangic:.1f} sn sürdü)",
              file=sys.stderr)
        if max_rows:
            print(f"[REPAIR] ÖLÇÜM MODU — yalnızca ilk {max_rows} satır işlenecek.",
                  file=sys.stderr)
        if not toplam:
            return {"toplam": 0, "temizlenen": 0, "atlanan": 0, "incelenen": 0}

        # TEK BAĞLANTI — havuz max_size=2, ikinci bağlantı almak riskli.
        son_id = ""
        tur = 0
        max_tur = max(20, (toplam // _PARTI) * 3 + 20)   # emniyet freni

        tampon: list[tuple[str, str]] = []
        while True:
            tur += 1
            if tur > max_tur:
                print(f"[REPAIR] DURDURULDU — {max_tur} tur aşıldı "
                      f"(son chunk_id: {son_id})", file=sys.stderr)
                break

            with conn.cursor() as cur:
                cur.execute(_kirli_sorgusu(), {"lim": _PARTI, "son": son_id})
                rows = cur.fetchall()
            if not rows:
                break
            son_id = rows[-1][0]          # imleç: güncelleme olmasa da ilerler

            for chunk_id, belge in rows:
                yeni_metin = _satiri_isle(chunk_id, belge, sayac, atlanan_ornekler)
                if yeni_metin is not None:
                    tampon.append((yeni_metin, chunk_id))

            if tampon:
                _yaz(conn, tampon, dry_run)
                tampon.clear()

            gecen = time.perf_counter() - t_baslangic
            hiz = sayac["incelenen"] / max(gecen, 0.001)
            kalan_sn = (toplam - sayac["incelenen"]) / max(hiz, 0.001)
            print(f"[REPAIR] {sayac['incelenen']}/{toplam} incelendi, "
                  f"{sayac['temizlenen']} temizlendi, {sayac['atlanan']} atlandı | "
                  f"{hiz:.0f} satır/sn, tahmini kalan {kalan_sn/60:.1f} dk",
                  file=sys.stderr)

            if max_rows and sayac["incelenen"] >= max_rows:
                print("[REPAIR] ÖLÇÜM SINIRINA ULAŞILDI — duruluyor.", file=sys.stderr)
                break
            if len(rows) < _PARTI:
                break

    gecen = time.perf_counter() - t_baslangic
    print(f"[REPAIR] BİTTİ — {sayac['incelenen']}/{toplam} incelendi, "
          f"{sayac['temizlenen']} temizlendi, {sayac['atlanan']} atlandı "
          f"({gecen:.1f} sn)", file=sys.stderr)
    if max_rows and sayac["incelenen"]:
        tam_tahmin = gecen * toplam / sayac["incelenen"]
        print(f"[REPAIR] ÖLÇÜM: bu hızla {toplam:,} satırın tamamı "
              f"~{tam_tahmin/60:.0f} DAKİKA sürer.", file=sys.stderr)

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


#: `bayat_isaretle_parquetten` tek UPDATE'te kaç decision_id gönderilsin.
_ISARET_PARTI = 2000


def _parquet_yolu() -> Path:
    return Path(os.environ.get(
        "DECISIONS_PARQUET", str(ROOT / "data" / "final" / "all_decisions.parquet")))


def kirli_karar_idleri(yol: Path | None = None) -> list[str]:
    """Parquet'te HÂLÂ HTML izi taşıyan kararların kimlikleri.

    Parquet onarımdan ÖNCE okunmalı — `onar_parquet` bu kanıtı siler.

    YALNIZCA `cleaned_text` BAKILIR — `raw_text` DEĞİL
    --------------------------------------------------
    `rag_chunks` satırları yalnızca `cleaned_text`'ten üretiliyor
    (`pipelines/chunk.py`). `raw_text` ise tanımı gereği HAM HTML'dir; her
    kararda `<` içerir. Onu da tespite katmak iki hataya birden yol açar:
      * DOĞRULUK: neredeyse TÜM kararlar "kirli" sayılır → 21.500 yerine
        117.000 chunk yeniden embed edilir, fatura 5 katına çıkar.
      * BELLEK: tüm külliyatın ham HTML'i belleğe çekilir → job OOM ile ölür
        (2026-08-07'de tam olarak bu oldu).

    TESPİT DuckDB'DE YAPILIR
    ------------------------
    Python'a yalnızca KİMLİKLER döner, metin hiç dönmez — bellek karar
    sayısıyla değil, kirli karar sayısıyla sınırlı. Desen `HTML_IZI_DESENI`
    üzerinden paylaşılıyor; DuckDB (RE2) ile Python `re` aynı sonucu veriyor
    ve bunu bir fark testi koruyor.
    """
    import duckdb

    yol = yol or _parquet_yolu()
    if not yol.exists():
        raise FileNotFoundError(
            f"parquet bulunamadı: {yol}\n"
            "Bayat tarama parquet'teki kirli metne dayanır; onsuz yapılamaz."
        )

    kaynak = "'" + str(yol).replace("'", "''") + "'"
    con = duckdb.connect()
    try:
        mevcut = con.execute(f"SELECT * FROM {kaynak} LIMIT 0").description
        adlar = [d[0] for d in mevcut]
        if "id" not in adlar or "cleaned_text" not in adlar:
            raise ValueError(
                f"parquet'te beklenen kolonlar yok: id + cleaned_text "
                f"(bulunan: {adlar[:10]})")

        satirlar = con.execute(
            f"SELECT DISTINCT id FROM {kaynak} "
            "WHERE cleaned_text IS NOT NULL "
            "  AND regexp_matches(cleaned_text, ?, 'i') "
            "ORDER BY id",
            [HTML_IZI_DESENI],
        ).fetchall()
    finally:
        con.close()

    return [str(s[0]) for s in satirlar]


def bayat_isaretle_parquetten(dry_run: bool) -> dict:
    """İŞARETSİZ temizlenmiş chunk'ları BAYAT olarak işaretle.

    KAPATILAN BOŞLUK
    ----------------
    İlk onarım koşuları metni temizliyor ama `embedding_model` sütununa BAYAT
    işareti YAZMIYORDU (o özellik sonradan eklendi). Sonuç: metni temiz,
    vektörü HTML çöpünden üretilmiş satırlar oluştu ve bunlar DB'de hiç kirli
    olmamış satırlardan ayırt edilemez hâle geldi — `--reembed` onları atlar,
    arama kalitesi sessizce bozuk kalır.

    ÇÖZÜM: parquet henüz onarılmadığı için kirli metni HÂLÂ içeriyor. Kirli
    KARAR kimlikleri oradan çıkarılıp o kararların TÜM chunk'ları işaretlenir.
    Bu, zaten işaretli olanların ÜST KÜMESİDİR — kayıp bırakmaz.

    GÜVENLİK: yalnızca `embedding_model IS NULL` satırlar işaretlenir. Gerçek
    bir model imzası taşıyan satırlar (onarımdan SONRA düzgün embed edilmiş)
    ellenmez.
    """
    from services import pg

    idler = kirli_karar_idleri()
    print(f"[BAYAT] parquet'te kirli karar: {len(idler):,}", file=sys.stderr)
    if not idler:
        print(
            "[BAYAT] UYARI: parquet'te kirli karar YOK.\n"
            "        Parquet zaten onarılmış olabilir (--parquet daha önce\n"
            "        çalıştıysa). O durumda bu tarama kanıtı bulamaz; yedeği\n"
            "        kullanın: DECISIONS_PARQUET=<...>.html-kirli-yedek",
            file=sys.stderr)
        return {"kirli_karar": 0, "isaretlenen": 0}

    if dry_run:
        with pg.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM rag_chunks "
                "WHERE decision_id = ANY(%s) AND embedding_model IS NULL",
                (idler,))
            adet = cur.fetchone()[0]
        print(f"[BAYAT] DRY-RUN — işaretlenecek chunk: {adet:,}", file=sys.stderr)
        return {"kirli_karar": len(idler), "isaretlenen": 0, "isaretlenecek": adet}

    isaretlenen = 0
    with pg.connection() as conn:
        for i in range(0, len(idler), _ISARET_PARTI):
            parca = idler[i:i + _ISARET_PARTI]
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE rag_chunks SET embedding_model = %s "
                    "WHERE decision_id = ANY(%s) AND embedding_model IS NULL",
                    (_BAYAT_ISARET, parca))
                isaretlenen += cur.rowcount
            conn.commit()
            print(f"[BAYAT] {min(i + _ISARET_PARTI, len(idler)):,}/{len(idler):,} "
                  f"karar tarandı, {isaretlenen:,} chunk işaretlendi",
                  file=sys.stderr)

    print(f"[BAYAT] BİTTİ — {isaretlenen:,} chunk BAYAT olarak işaretlendi.",
          file=sys.stderr)
    return {"kirli_karar": len(idler), "isaretlenen": isaretlenen}


def onar_parquet(dry_run: bool) -> dict:
    """Karar tam metni parquet'ini onarır (karar detay sayfası oradan okur)."""
    import duckdb

    yol = _parquet_yolu()
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
    ap.add_argument("--bayat-tara", action="store_true",
                    help="ESKİ koşuların işaretsiz temizlediği chunk'ları "
                         "parquet'teki kirli karar kimliklerinden bulup BAYAT "
                         "işaretle. --parquet ONARIMINDAN ÖNCE çalıştırın.")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="ÖLÇÜM: yalnızca ilk N satırı işle, süreyi ölç ve "
                         "tamamının ne kadar süreceğini tahmin et")
    ap.add_argument("--skip-db", action="store_true",
                    help="METİN TEMİZLEME taramasını atla (rag_chunks.document'e "
                         "dokunma). --bayat-tara ve --reembed bundan etkilenmez.")
    args = ap.parse_args()

    if args.dry_run:
        print("[REPAIR] DRY-RUN — hiçbir şey değiştirilmeyecek, "
              "API çağrısı YAPILMAYACAK.\n", file=sys.stderr)

    sonuc: dict = {}
    if not args.skip_db:
        sonuc["rag_chunks"] = onar_chunks(args.dry_run, args.max_rows)

    # SIRA ÖNEMLİ: bayat tarama parquet'teki kirli metne dayanır; `onar_parquet`
    # o kanıtı temizler. Bu yüzden tarama HER ZAMAN parquet onarımından önce.
    # NOT: --skip-db yalnızca METİN TEMİZLEME taramasını atlar. --bayat-tara
    # bağımsızdır; asıl kullanımı zaten "temizlik bitti, sadece işaretle" —
    # 4,5 saatlik taramayı yeniden çalıştırmaya gerek kalmasın.
    if args.bayat_tara:
        sonuc["bayat_tara"] = bayat_isaretle_parquetten(args.dry_run)

    if args.reembed and not args.dry_run:
        sonuc["embed"] = _yeniden_embed(args.onayla, args.max_embed)
    elif args.reembed and args.dry_run:
        print("[REPAIR] --dry-run ile --reembed birlikte verildi → "
              "embed aşaması ATLANDI.", file=sys.stderr)

    if args.parquet:
        if not args.bayat_tara:
            print(
                "\n[REPAIR] UYARI: parquet onarılıyor ama --bayat-tara verilmedi.\n"
                "         Parquet, ESKİ koşuların işaretsiz temizlediği chunk'ları\n"
                "         bulmak için kullanılan TEK kanıttır. Onarımdan sonra\n"
                "         yalnızca .html-kirli-yedek dosyasından bulunabilir.\n",
                file=sys.stderr)
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
