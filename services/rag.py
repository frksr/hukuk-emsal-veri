"""Ortak RAG arama servisi — pgvector (Cloud SQL) + API embedding.

Tüm özelliklerin (dilekçe, atıf önerici, karşı argüman) kullandığı temel.

Mimari (bkz. PGVECTOR_GOC_PLANI.md):
- Embedding: services.embeddings (Google API / lokal e5; sorgu cache'li)
- Vektör deposu: Postgres 'rag_chunks' tablosu, cosine HNSW indeksli
- Tam karar metni + listeleme: hâlâ parquet üzerinden (DuckDB, düşük bellek)

Public fonksiyon imzaları ESKİSİYLE AYNI (search/get_collection_stats/...);
router ve servis caller'ları değişmez.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

log = logging.getLogger("services.rag")

ROOT = Path(__file__).resolve().parent.parent
DECISIONS_PARQUET = Path(os.environ.get(
    "DECISIONS_PARQUET", str(ROOT / "data" / "final" / "all_decisions.parquet")))

# Chroma where-dict'inden çıkarılabilen filtre alanları (yalnızca bunlar kullanılıyor).
_FILTER_COLS = {"source", "court_chamber"}


def _extract_filters(where: dict | None) -> dict:
    """Eski Chroma where formatını {kolon: değer} sözlüğüne indirger.

    Desteklenen biçimler:
      {"source": "yargitay"}
      {"$and": [{"source": "yargitay"}, {"court_chamber": "12. HD"}]}
    """
    out: dict = {}
    if not where:
        return out
    if "$and" in where:
        for sub in where["$and"]:
            out.update(_extract_filters(sub))
        return out
    for key, val in where.items():
        if key in _FILTER_COLS and not isinstance(val, dict):
            out[key] = val
    return out


# ---------------------------------------------------------------------------
# Kalite parametreleri
# ---------------------------------------------------------------------------
# NEDEN EŞİK VAR: eski `search()` her zaman tam k sonuç döndürüyordu — "alakasız"
# diye bir kavram yoktu. Veri tabanı ağırlıklı icra hukuku içerdiğinden, bir iş
# hukuku sorusu sorulduğunda sistem alakasız icra kararlarını "emsal" diye
# sunuyor, bunlar dilekçe/karşı argüman servisleri üzerinden kullanıcıya
# ulaşıyordu. Hukuk ürününde bu, kabul edilebilir bir davranış değil.
MIN_SIMILARITY = float(os.environ.get("RAG_MIN_SIMILARITY", "0.35"))

#: LLM'e bağlam olarak verilecek emsaller için daha katı eşik.
CONTEXT_MIN_SIMILARITY = float(os.environ.get("RAG_CONTEXT_MIN_SIMILARITY", "0.45"))

#: Aynı karardan sonuç listesine en fazla kaç chunk girebilir (çeşitlilik).
#: Chunk'lar örtüşmeli bölündüğü için top-5'in tamamı aynı kararın parçaları
#: olabiliyordu; kullanıcı "5 emsal" görüyor ama aslında 1 karar okuyordu.
MAX_CHUNKS_PER_DECISION = int(os.environ.get("RAG_MAX_CHUNKS_PER_DECISION", "2"))

#: HNSW arama genişliği. Yüksek = daha iyi recall, daha yavaş.
HNSW_EF_SEARCH = int(os.environ.get("RAG_HNSW_EF_SEARCH", "80"))

#: RRF sabiti — düşük sıralardaki sonuçların etkisini yumuşatır (standart: 60).
_RRF_K = 60


# ---------------------------------------------------------------------------
# Tam metin arama ifadesi
# ---------------------------------------------------------------------------
# NEDEN GENERATED KOLON DEĞİL DE İFADE İNDEKSİ:
# Önce `document_tsv` adlı bir GENERATED STORED kolon tasarlanmıştı. Onu eklemek
# tabloyu baştan yazıyor ve süresince ACCESS EXCLUSIVE kilit tutuyor — canlıda
# dakikalarca kesinti, Cloud SQL Studio gibi kısa ömürlü istemcilerde ise
# "database is currently unavailable" ile kopma demek. İfade indeksi aynı hızı
# verir, kolon eklemez, CONCURRENTLY ile kesintisiz kurulur.
#
# TÜRKÇE KARAKTER KATLAMASI:
# 'simple' sözlüğü hiçbir katlama yapmaz; "itirazın" ile "itirazin" FARKLI
# token'dır. Kullanıcı Türkçe klavyesi olmadan yazdığında tam metin tarafı
# hiçbir şey bulamıyordu. `f_unaccent()` sarmalayıcısı ı→i, ş→s, ğ→g, ü→u,
# ö→o, ç→c katlaması yapar (bkz. infra/db/33_rag_unaccent.sql).
#
# GERİYE DÖNÜK UYUMLULUK:
# Fonksiyon/indeks henüz kurulmamışsa (lokal geliştirme, migration'dan önceki
# dağıtım) katlamasız ifadeye düşülür. Böylece kod ile migration'ın dağıtım
# SIRASI önemsizleşir — hangisi önce giderse gitsin sistem çalışır.

#: Süreç ömrü boyunca bir kez sınanır. None = henüz bakılmadı.
_UNACCENT_DESTEGI: bool | None = None

#: RAG_UNACCENT=0 ile zorla kapatılabilir (indeksi düşürüp geri almak için).
_UNACCENT_ACIK = os.environ.get("RAG_UNACCENT", "1").strip().lower() not in {"0", "false", "hayir"}


def _unaccent_kullanilabilir(conn) -> bool:
    """`f_unaccent(text)` fonksiyonu bu veritabanında var mı?"""
    global _UNACCENT_DESTEGI
    if not _UNACCENT_ACIK:
        return False
    if _UNACCENT_DESTEGI is None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regprocedure('f_unaccent(text)') IS NOT NULL")
                _UNACCENT_DESTEGI = bool(cur.fetchone()[0])
        except Exception as e:
            log.info("f_unaccent sınanamadı, katlamasız devam: %s", e)
            _UNACCENT_DESTEGI = False
        log.info(
            "Tam metin araması: Türkçe karakter katlaması %s",
            "AÇIK (f_unaccent)" if _UNACCENT_DESTEGI else "KAPALI — 33_rag_unaccent.sql uygulandı mı?",
        )
    return _UNACCENT_DESTEGI


def _metin_sql_uret(conn, kolonlar: str, filtre: str) -> str:
    """Tam metin sorgusunu üret — indekste hangi ifade varsa onunla.

    DİKKAT: buradaki ifade, indekstekiyle KARAKTER KARAKTER aynı olmalıdır;
    aksi halde planner indeksi kullanamaz ve sorgu sequential scan'e düşer.
    Doğrulama: `EXPLAIN` çıktısında "Bitmap Index Scan on rag_chunks_tsv*_idx".
    """
    if _unaccent_kullanilabilir(conn):
        belge = "to_tsvector('simple', f_unaccent(document))"
        sorgu = "to_tsquery('simple', f_unaccent(%(tsq)s))"
    else:
        belge = "to_tsvector('simple', document)"
        sorgu = "to_tsquery('simple', %(tsq)s)"

    return f"""
        SELECT {kolonlar}, ts_rank({belge}, {sorgu}) AS similarity
        FROM rag_chunks
        {filtre}
          AND {belge} @@ {sorgu}
        ORDER BY similarity DESC
        LIMIT %(lim)s
    """


def _tsquery_hazirla(query: str) -> str:
    """Serbest metni Postgres `to_tsquery` için güvenli bir OR sorgusuna çevirir.

    Kullanıcı girdisi doğrudan to_tsquery'ye verilemez (sözdizimi hatası atar).
    Alfanümerik token'lara bölüp OR ile birleştiriyoruz; "2023/1234" gibi
    ifadeler "2023 | 1234" olur ve dosya numarası eşleşmesini yakalar.
    """
    import re as _re

    tokens = [t for t in _re.split(r"[^\wçğıöşüÇĞİÖŞÜ]+", query) if len(t) > 1]
    return " | ".join(tokens[:24])


def search(
    query: str,
    k: int = 5,
    where: dict | None = None,
    min_similarity: float | None = None,
    hybrid: bool = True,
    max_chunks_per_decision: int | None = None,
) -> list[dict]:
    """RAG araması — hibrit (vektör + tam metin), eşikli ve çeşitlendirilmiş.

    Args:
        k: döndürülecek maksimum sonuç. Eşiği geçen daha az sonuç varsa DAHA AZ
           döner (hatta boş liste) — "her zaman k sonuç" garantisi YOKTUR.
        min_similarity: kosinüs benzerliği eşiği. None → MIN_SIMILARITY.
                        0 veya negatif verilirse eşik uygulanmaz.
        hybrid: True ise tam metin sıralaması da hesaplanıp RRF ile birleştirilir.
                Şema henüz `document_tsv` içermiyorsa sessizce saf vektöre düşer.
        max_chunks_per_decision: aynı karardan en fazla kaç parça (çeşitlilik).

    Returns:
      [{'text', 'meta', 'similarity', 'chunk_id', 'rank_kaynak'}, ...]
      Benzerliğe göre azalan sırada.
    """
    from services import embeddings
    from services import pg

    esik = MIN_SIMILARITY if min_similarity is None else float(min_similarity)
    per_decision = (MAX_CHUNKS_PER_DECISION if max_chunks_per_decision is None
                    else int(max_chunks_per_decision))

    try:
        q_emb = embeddings.embed_query(query)
    except Exception as e:
        log.warning("Embedding üretilemedi: %s", e)
        return []

    filters = _extract_filters(where)
    # Aday havuzu k'dan geniş tutulur: eşik + çeşitlilik filtresi eleyeceği için.
    aday_limit = max(int(k) * 6, 30)

    kolonlar = ("chunk_id, decision_id, chunk_index, document, source, court_chamber, "
                "case_no, decision_no, decision_date, topic_tags, source_url")
    filtre = ("WHERE (%(source)s::text IS NULL OR source = %(source)s) "
              "AND (%(court)s::text IS NULL OR court_chamber = %(court)s)")
    params = {
        "q": q_emb,
        "source": filters.get("source"),
        "court": filters.get("court_chamber"),
        "lim": aday_limit,
        "tsq": _tsquery_hazirla(query),
    }

    vektor_sql = f"""
        SELECT {kolonlar}, 1 - (embedding <=> %(q)s::vector) AS similarity
        FROM rag_chunks
        {filtre}
        ORDER BY embedding <=> %(q)s::vector
        LIMIT %(lim)s
    """
    def _calistir(cur, sql) -> list[dict]:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    vektor_sonuc: list[dict] = []
    metin_sonuc: list[dict] = []
    try:
        with pg.connection() as conn:
            with conn.cursor() as cur:
                # HNSW recall ayarı — oturum bazlı, indeksi değiştirmez.
                try:
                    cur.execute("SET LOCAL hnsw.ef_search = %s", (HNSW_EF_SEARCH,))
                except Exception:
                    pass  # pgvector sürümü desteklemiyorsa önemli değil
                vektor_sonuc = _calistir(cur, vektor_sql)

            if hybrid and params["tsq"]:
                try:
                    metin_sql = _metin_sql_uret(conn, kolonlar, filtre)
                    with conn.cursor() as cur:
                        metin_sonuc = _calistir(cur, metin_sql)
                except Exception as e:
                    # İndeks yoksa sorgu yine ÇALIŞIR (sequential scan), sadece
                    # yavaş olur. Buraya düşmek gerçek bir hata demektir —
                    # yine de aramayı komple düşürmeyip saf vektöre geri çekiliyoruz.
                    log.warning("Tam metin araması başarısız, saf vektöre düşüldü: %s", e)
                    try:
                        conn.rollback()   # bozuk transaction'ı temizle
                    except Exception:
                        pass
    except Exception as e:
        log.warning("pgvector araması başarısız: %s — şema/seed gerekli?", e)
        return []

    birlesik = _rrf_birlestir(vektor_sonuc, metin_sonuc)
    return _sonuclari_hazirla(birlesik, k=k, esik=esik, per_decision=per_decision)


def _rrf_birlestir(vektor: list[dict], metin: list[dict]) -> list[dict]:
    """İki sıralamayı Reciprocal Rank Fusion ile birleştir.

    RRF skor bazlı değil SIRA bazlıdır; kosinüs benzerliği ile ts_rank farklı
    ölçeklerde olduğundan doğrudan toplanamaz, RRF bu sorunu çözer.
    Görüntülenen `similarity` daima VEKTÖR benzerliğidir (kullanıcıya "%78
    benzer" derken tutarlı bir ölçü göstermek için).
    """
    kayit: dict[str, dict] = {}
    skor: dict[str, float] = {}

    for sira, r in enumerate(vektor):
        cid = r["chunk_id"]
        kayit[cid] = r
        skor[cid] = skor.get(cid, 0.0) + 1.0 / (_RRF_K + sira + 1)
        r["rank_kaynak"] = "vektor"

    for sira, r in enumerate(metin):
        cid = r["chunk_id"]
        if cid in kayit:
            kayit[cid]["rank_kaynak"] = "hibrit"
        else:
            # Yalnızca tam metinden gelen kayıt: vektör benzerliği bilinmiyor.
            r["similarity"] = None
            r["rank_kaynak"] = "tam_metin"
            kayit[cid] = r
        skor[cid] = skor.get(cid, 0.0) + 1.0 / (_RRF_K + sira + 1)

    sirali = sorted(kayit.values(), key=lambda r: skor[r["chunk_id"]], reverse=True)
    for r in sirali:
        r["_rrf"] = skor[r["chunk_id"]]
    return sirali


def _sonuclari_hazirla(rows: list[dict], k: int, esik: float,
                       per_decision: int) -> list[dict]:
    """Eşik + karar bazlı çeşitlilik uygula, dış formata çevir."""
    karar_sayaci: dict[str, int] = {}
    out: list[dict] = []

    for rec in rows:
        sim = rec.get("similarity")
        # Yalnızca tam metin eşleşmesinden gelen kayıtlarda vektör benzerliği
        # yok; bunlar tam eşleşme oldukları için eşikten muaf tutulur.
        if sim is not None and esik > 0 and float(sim) < esik:
            continue

        did = rec.get("decision_id") or rec["chunk_id"]
        if per_decision > 0 and karar_sayaci.get(did, 0) >= per_decision:
            continue
        karar_sayaci[did] = karar_sayaci.get(did, 0) + 1

        out.append({
            "chunk_id": rec["chunk_id"],
            "text": rec["document"],
            "similarity": float(sim) if sim is not None else 0.0,
            "rank_kaynak": rec.get("rank_kaynak", "vektor"),
            "meta": {
                "decision_id": rec["decision_id"],
                "chunk_index": rec["chunk_index"],
                "source": rec["source"],
                "court_chamber": rec["court_chamber"],
                "case_no": rec["case_no"],
                "decision_no": rec["decision_no"],
                "decision_date": rec["decision_date"],
                "topic_tags": rec["topic_tags"],
                "source_url": rec["source_url"],
            },
        })
        if len(out) >= k:
            break

    # Kullanıcıya gösterim sırası benzerliğe göre (RRF sırası iç detaydır).
    out.sort(key=lambda r: r["similarity"], reverse=True)
    return out


def search_for_context(query: str, k: int = 5, where: dict | None = None) -> list[dict]:
    """LLM'e bağlam olarak verilecek emsaller — daha KATI eşik.

    Bir emsali kullanıcıya "ilgili olabilir" diye listelemek ile onu LLM'e
    "bu karara dayanarak dilekçe yaz" diye vermek aynı şey değildir. İkincisinde
    yanlış emsal doğrudan hukuki bir metne giriyor, o yüzden eşik daha yüksek.
    """
    return search(query, k=k, where=where, min_similarity=CONTEXT_MIN_SIMILARITY)


def get_collection_stats() -> dict:
    from services import pg
    try:
        with pg.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM rag_chunks")
                count = cur.fetchone()[0]
        return {"chunk_count": int(count), "available": True}
    except Exception as e:
        return {"chunk_count": 0, "available": False, "error": str(e)}


def get_full_decision(decision_id: str) -> dict | None:
    """Parquet'ten tam karar metnini çek."""
    import duckdb
    parquet = DECISIONS_PARQUET
    if not parquet.exists():
        return None
    try:
        con = duckdb.connect()
        cur = con.execute(
            "SELECT * FROM read_parquet(?) WHERE id = ? LIMIT 1",
            [str(parquet), decision_id],
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        con.close()
        if not rows:
            return None
        return dict(zip(cols, rows[0]))
    except Exception:
        return None


def list_decisions(limit: int = 100, offset: int = 0,
                   source: str | None = None) -> list[dict]:
    """Karar detay sayfaları için sayfalı liste (parquet'ten).

    Yalnızca anonymization_check'i geçen kayıtlar döner — KVKK: kişisel veri
    içerme şüphesi olan karar public sayfada yayımlanmaz.
    """
    import duckdb
    if not DECISIONS_PARQUET.exists():
        return []
    try:
        con = duckdb.connect()
        sql = (
            "SELECT id, source, court_chamber, case_no, decision_no, "
            "decision_date, topic_tags, char_count "
            "FROM read_parquet(?) "
            "WHERE COALESCE(CAST(anonymization_check AS VARCHAR), '') "
            "  NOT IN ('failed', 'false', '0') "
        )
        params: list = [str(DECISIONS_PARQUET)]
        if source:
            sql += "AND source = ? "
            params.append(source)
        sql += "ORDER BY decision_date DESC NULLS LAST LIMIT ? OFFSET ?"
        params += [int(limit), int(offset)]
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        con.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []


def related_decisions(decision_id: str, limit: int = 6) -> list[dict]:
    """Verilen karara 'ilgili' kararları döndür (aynı daire, sonra aynı kaynak).

    İç linkleme/topical authority için (SEO_ANALIZ B3): karar detay sayfaları
    izole kalmasın. Maliyetsiz — parquet/DuckDB metadata filtresi, LLM yok.
    Yalnızca anonymization_check'i geçen kararlar; kendisi hariç tutulur.
    """
    import duckdb
    if not DECISIONS_PARQUET.exists():
        return []
    try:
        con = duckdb.connect()
        src = str(DECISIONS_PARQUET)
        # Önce mevcut kararın daire/kaynağını al.
        ref = con.execute(
            "SELECT source, court_chamber FROM read_parquet(?) WHERE id = ? LIMIT 1",
            [src, decision_id],
        ).fetchall()
        if not ref:
            con.close()
            return []
        source, court_chamber = ref[0][0], ref[0][1]

        anon_ok = (
            "COALESCE(CAST(anonymization_check AS VARCHAR), '') "
            "NOT IN ('failed', 'false', '0')"
        )
        base_cols = (
            "id, source, court_chamber, case_no, decision_no, "
            "decision_date, topic_tags"
        )

        rows: list = []
        cols: list = []
        # 1) Aynı daire (en alakalı).
        if court_chamber:
            cur = con.execute(
                f"SELECT {base_cols} FROM read_parquet(?) "
                f"WHERE court_chamber = ? AND id <> ? AND {anon_ok} "
                f"ORDER BY decision_date DESC NULLS LAST LIMIT ?",
                [src, court_chamber, decision_id, int(limit)],
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        # 2) Yetersizse aynı kaynaktan tamamla.
        if len(rows) < limit and source:
            haric = [decision_id] + [r[0] for r in rows]
            ph = ", ".join("?" for _ in haric)
            cur = con.execute(
                f"SELECT {base_cols} FROM read_parquet(?) "
                f"WHERE source = ? AND id NOT IN ({ph}) AND {anon_ok} "
                f"ORDER BY decision_date DESC NULLS LAST LIMIT ?",
                [src, source, *haric, int(limit - len(rows))],
            )
            if not cols:
                cols = [d[0] for d in cur.description]
            rows += cur.fetchall()
        con.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []
