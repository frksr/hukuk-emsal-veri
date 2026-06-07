"""
Trend Analizi Servisi

Türk hukuk emsal kararları üzerinde DuckDB ile zaman serisi ve dağılım
analizleri üretir. Streamlit panelinden çağrılır.

Veri kaynağı: data/final/all_decisions.parquet
Sütunlar: id, source, court_chamber, case_no, decision_no,
          decision_date (DD.MM.YYYY), cleaned_text, topic_tags (list),
          char_count
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb

# -----------------------------------------------------------------------------
# Sabitler
# -----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PARQUET_PATH = ROOT / "data" / "final" / "all_decisions.parquet"

# DuckDB sorgularında kullanılan yıl regex'i: 1900-2099 arası dört haneli yıl.
YIL_REGEX = r"(19\d{2}|20\d{2})"


# -----------------------------------------------------------------------------
# Yardımcılar
# -----------------------------------------------------------------------------

def _parquet_path() -> str:
    """Parquet dosya yolunu DuckDB için forward-slash formatında döndürür."""
    return str(PARQUET_PATH).replace("\\", "/")


def _esc(value: str) -> str:
    """SQL string literal için tek tırnak escape."""
    return value.replace("'", "''")


def _connect() -> duckdb.DuckDBPyConnection:
    """Bellek içi DuckDB bağlantısı."""
    return duckdb.connect(database=":memory:")


def _parquet_var_mi() -> bool:
    return PARQUET_PATH.exists()


def _bos_sonuc(filters: Dict[str, Any], hata: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "data": [],
        "total": 0,
        "filters": filters,
    }
    if hata:
        out["hata"] = hata
    return out


# -----------------------------------------------------------------------------
# 1) Yıllık trend
# -----------------------------------------------------------------------------

def trend_yillik(
    konu_filtresi: Optional[str] = None,
    kaynak: Optional[str] = None,
    daire: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Yıllık karar sayısını döndürür.

    Args:
        konu_filtresi: Belirli bir topic tag (örn. "tazminat"). None/"" ise filtre yok.
        kaynak: source filtresi (örn. "yargitay", "danistay", "aym"). None/"" ise filtre yok.
        daire: court_chamber filtresi (LIKE %...% eşleşmesi). None/"" ise filtre yok.

    Returns:
        {
            "data": [(yil:str, sayi:int), ...],
            "total": int,
            "filters": {...},
        }
    """
    filters = {
        "konu": konu_filtresi or "",
        "kaynak": kaynak or "",
        "daire": daire or "",
    }

    if not _parquet_var_mi():
        return _bos_sonuc(filters, hata=f"Parquet bulunamadı: {PARQUET_PATH}")

    where_parts: List[str] = ["yil != ''"]
    if konu_filtresi:
        where_parts.append(
            f"list_contains(topic_tags, '{_esc(konu_filtresi)}')"
        )
    if kaynak:
        where_parts.append(f"source = '{_esc(kaynak)}'")
    if daire:
        where_parts.append(f"court_chamber ILIKE '%{_esc(daire)}%'")

    where_sql = " AND ".join(where_parts)

    sql = f"""
    WITH parsed AS (
      SELECT *,
        regexp_extract(COALESCE(decision_date, ''), '{YIL_REGEX}', 1) AS yil
      FROM '{_parquet_path()}'
    )
    SELECT yil, COUNT(*) AS c
    FROM parsed
    WHERE {where_sql}
    GROUP BY yil
    ORDER BY yil
    """

    try:
        con = _connect()
        rows = con.execute(sql).fetchall()
    except Exception as e:
        return _bos_sonuc(filters, hata=f"DuckDB sorgusu başarısız: {e}")

    data: List[Tuple[str, int]] = [(str(r[0]), int(r[1])) for r in rows]
    total = sum(v for _, v in data)
    return {"data": data, "total": total, "filters": filters}


# -----------------------------------------------------------------------------
# 2) Konu dağılımı (top 10)
# -----------------------------------------------------------------------------

def trend_konu_dagilimi(
    yil_baslangic: int,
    yil_bitis: int,
) -> Dict[str, Any]:
    """
    Belirli yıl aralığında topic_tags array'ini patlatıp en sık 10 konuyu döndürür.

    Args:
        yil_baslangic: Başlangıç yılı (dahil).
        yil_bitis: Bitiş yılı (dahil).

    Returns:
        {
            "data": [(konu:str, sayi:int), ...],
            "total": int,    # patlatılmış (etiket-bazlı) toplam
            "filters": {...},
        }
    """
    filters = {
        "yil_baslangic": yil_baslangic,
        "yil_bitis": yil_bitis,
    }

    if not _parquet_var_mi():
        return _bos_sonuc(filters, hata=f"Parquet bulunamadı: {PARQUET_PATH}")

    sql = f"""
    WITH parsed AS (
      SELECT topic_tags,
        TRY_CAST(regexp_extract(COALESCE(decision_date, ''), '{YIL_REGEX}', 1) AS INTEGER) AS yil
      FROM '{_parquet_path()}'
    ),
    filtreli AS (
      SELECT topic_tags
      FROM parsed
      WHERE yil IS NOT NULL
        AND yil BETWEEN {int(yil_baslangic)} AND {int(yil_bitis)}
        AND topic_tags IS NOT NULL
    ),
    patlamis AS (
      SELECT UNNEST(topic_tags) AS konu
      FROM filtreli
    )
    SELECT konu, COUNT(*) AS c
    FROM patlamis
    WHERE konu IS NOT NULL AND konu != ''
    GROUP BY konu
    ORDER BY c DESC
    LIMIT 10
    """

    try:
        con = _connect()
        rows = con.execute(sql).fetchall()
    except Exception as e:
        return _bos_sonuc(filters, hata=f"DuckDB sorgusu başarısız: {e}")

    data: List[Tuple[str, int]] = [(str(r[0]), int(r[1])) for r in rows]
    total = sum(v for _, v in data)
    return {"data": data, "total": total, "filters": filters}


# -----------------------------------------------------------------------------
# 3) Mahkeme × Konu heatmap matrisi
# -----------------------------------------------------------------------------

def trend_mahkeme_konu_matrix(
    top_n_mahkeme: int = 10,
    top_n_konu: int = 10,
) -> Dict[str, Any]:
    """
    Heatmap için mahkeme × konu matrisi üretir.

    Önce en sık top_n_mahkeme mahkeme (court_chamber) ve en sık top_n_konu
    konu (topic) seçilir; ardından çapraz tablo (matrix) hesaplanır.

    Returns:
        {
            "data": {
                "mahkemeler": [str, ...],
                "konular":   [str, ...],
                "matrix":    [[int, ...], ...]   # satır=mahkeme, sütun=konu
            },
            "total": int,
            "filters": {...},
        }
    """
    filters = {
        "top_n_mahkeme": int(top_n_mahkeme),
        "top_n_konu": int(top_n_konu),
    }

    if not _parquet_var_mi():
        return _bos_sonuc(filters, hata=f"Parquet bulunamadı: {PARQUET_PATH}")

    parquet = _parquet_path()
    n_mahkeme = int(top_n_mahkeme)
    n_konu = int(top_n_konu)

    try:
        con = _connect()

        # En sık geçen mahkemeler
        mahkeme_rows = con.execute(f"""
            SELECT court_chamber, COUNT(*) AS c
            FROM '{parquet}'
            WHERE court_chamber IS NOT NULL AND court_chamber != ''
            GROUP BY court_chamber
            ORDER BY c DESC
            LIMIT {n_mahkeme}
        """).fetchall()
        mahkemeler: List[str] = [str(r[0]) for r in mahkeme_rows]

        # En sık geçen konular
        konu_rows = con.execute(f"""
            WITH patlamis AS (
              SELECT UNNEST(topic_tags) AS konu
              FROM '{parquet}'
              WHERE topic_tags IS NOT NULL
            )
            SELECT konu, COUNT(*) AS c
            FROM patlamis
            WHERE konu IS NOT NULL AND konu != ''
            GROUP BY konu
            ORDER BY c DESC
            LIMIT {n_konu}
        """).fetchall()
        konular: List[str] = [str(r[0]) for r in konu_rows]

        if not mahkemeler or not konular:
            return {
                "data": {"mahkemeler": mahkemeler, "konular": konular, "matrix": []},
                "total": 0,
                "filters": filters,
            }

        # Çapraz tablo: her (mahkeme, konu) kombosu için sayım
        mahkeme_list_sql = ", ".join([f"'{_esc(m)}'" for m in mahkemeler])
        konu_list_sql = ", ".join([f"'{_esc(k)}'" for k in konular])

        cross_sql = f"""
        WITH patlamis AS (
          SELECT court_chamber, UNNEST(topic_tags) AS konu
          FROM '{parquet}'
          WHERE topic_tags IS NOT NULL
            AND court_chamber IS NOT NULL
            AND court_chamber != ''
        )
        SELECT court_chamber, konu, COUNT(*) AS c
        FROM patlamis
        WHERE court_chamber IN ({mahkeme_list_sql})
          AND konu IN ({konu_list_sql})
        GROUP BY court_chamber, konu
        """
        cross_rows = con.execute(cross_sql).fetchall()
    except Exception as e:
        return _bos_sonuc(filters, hata=f"DuckDB sorgusu başarısız: {e}")

    # Indeks haritaları
    mahkeme_idx = {m: i for i, m in enumerate(mahkemeler)}
    konu_idx = {k: j for j, k in enumerate(konular)}

    matrix: List[List[int]] = [[0 for _ in konular] for _ in mahkemeler]
    toplam = 0
    for mahkeme, konu, c in cross_rows:
        i = mahkeme_idx.get(str(mahkeme))
        j = konu_idx.get(str(konu))
        if i is None or j is None:
            continue
        val = int(c)
        matrix[i][j] = val
        toplam += val

    return {
        "data": {
            "mahkemeler": mahkemeler,
            "konular": konular,
            "matrix": matrix,
        },
        "total": toplam,
        "filters": filters,
    }


# -----------------------------------------------------------------------------
# 4) Aylık zaman serisi
# -----------------------------------------------------------------------------

def trend_aylik(
    konu_filtresi: str,
    yil_baslangic: int,
    yil_bitis: int,
) -> Dict[str, Any]:
    """
    Belirli bir konu (topic) ve yıl aralığı için aylık zaman serisi.

    Tarih formatı DD.MM.YYYY varsayımıyla, gün-ay-yıl bileşenleri regex ile
    çıkarılır ve "YYYY-MM" formatında aylık sayım üretilir.

    Args:
        konu_filtresi: Konu etiketi. Boş ise tüm kararlar dahil.
        yil_baslangic: Başlangıç yılı (dahil).
        yil_bitis: Bitiş yılı (dahil).

    Returns:
        {
            "data": [("YYYY-MM", sayi:int), ...],   # kronolojik sıralı
            "total": int,
            "filters": {...},
        }
    """
    filters = {
        "konu": konu_filtresi or "",
        "yil_baslangic": int(yil_baslangic),
        "yil_bitis": int(yil_bitis),
    }

    if not _parquet_var_mi():
        return _bos_sonuc(filters, hata=f"Parquet bulunamadı: {PARQUET_PATH}")

    parquet = _parquet_path()

    where_parts: List[str] = [
        "yil IS NOT NULL",
        "ay IS NOT NULL",
        f"yil BETWEEN {int(yil_baslangic)} AND {int(yil_bitis)}",
        "ay BETWEEN 1 AND 12",
    ]
    if konu_filtresi:
        where_parts.append(
            f"list_contains(topic_tags, '{_esc(konu_filtresi)}')"
        )
    where_sql = " AND ".join(where_parts)

    sql = f"""
    WITH parsed AS (
      SELECT
        topic_tags,
        TRY_CAST(regexp_extract(COALESCE(decision_date, ''), '{YIL_REGEX}', 1) AS INTEGER) AS yil,
        TRY_CAST(regexp_extract(COALESCE(decision_date, ''), '^(\\d{{1,2}})\\.(\\d{{1,2}})\\.(\\d{{4}})$', 2) AS INTEGER) AS ay
      FROM '{parquet}'
    )
    SELECT
      printf('%04d-%02d', yil, ay) AS yil_ay,
      COUNT(*) AS c
    FROM parsed
    WHERE {where_sql}
    GROUP BY yil_ay
    ORDER BY yil_ay
    """

    try:
        con = _connect()
        rows = con.execute(sql).fetchall()
    except Exception as e:
        return _bos_sonuc(filters, hata=f"DuckDB sorgusu başarısız: {e}")

    data: List[Tuple[str, int]] = [(str(r[0]), int(r[1])) for r in rows]
    total = sum(v for _, v in data)
    return {"data": data, "total": total, "filters": filters}


# -----------------------------------------------------------------------------
# Yardımcı: dropdown'lar için seçenek listeleri
# -----------------------------------------------------------------------------

def filtre_secenekleri() -> Dict[str, Any]:
    """
    Streamlit filtreleri için dağarcık üretir:
    kaynak listesi, daire listesi, konu listesi ve yıl aralığı (min, max).
    """
    out: Dict[str, Any] = {
        "kaynaklar": [],
        "daireler": [],
        "konular": [],
        "yil_min": 1990,
        "yil_max": 2025,
        "toplam_karar": 0,
    }

    if not _parquet_var_mi():
        out["hata"] = f"Parquet bulunamadı: {PARQUET_PATH}"
        return out

    parquet = _parquet_path()
    try:
        con = _connect()

        out["toplam_karar"] = int(con.execute(
            f"SELECT COUNT(*) FROM '{parquet}'"
        ).fetchone()[0])

        kaynaklar = con.execute(f"""
            SELECT DISTINCT source FROM '{parquet}'
            WHERE source IS NOT NULL AND source != ''
            ORDER BY source
        """).fetchall()
        out["kaynaklar"] = [str(r[0]) for r in kaynaklar]

        daireler = con.execute(f"""
            SELECT court_chamber, COUNT(*) AS c FROM '{parquet}'
            WHERE court_chamber IS NOT NULL AND court_chamber != ''
            GROUP BY court_chamber
            ORDER BY c DESC
            LIMIT 200
        """).fetchall()
        out["daireler"] = [str(r[0]) for r in daireler]

        konular = con.execute(f"""
            WITH patlamis AS (
              SELECT UNNEST(topic_tags) AS konu
              FROM '{parquet}'
              WHERE topic_tags IS NOT NULL
            )
            SELECT konu, COUNT(*) AS c
            FROM patlamis
            WHERE konu IS NOT NULL AND konu != ''
            GROUP BY konu
            ORDER BY c DESC
            LIMIT 200
        """).fetchall()
        out["konular"] = [str(r[0]) for r in konular]

        yil_row = con.execute(f"""
            WITH parsed AS (
              SELECT TRY_CAST(regexp_extract(COALESCE(decision_date, ''), '{YIL_REGEX}', 1) AS INTEGER) AS yil
              FROM '{parquet}'
            )
            SELECT MIN(yil), MAX(yil) FROM parsed WHERE yil IS NOT NULL
        """).fetchone()
        if yil_row and yil_row[0] is not None:
            out["yil_min"] = int(yil_row[0])
            out["yil_max"] = int(yil_row[1])
    except Exception as e:
        out["hata"] = f"DuckDB sorgusu başarısız: {e}"

    return out


# -----------------------------------------------------------------------------
# Yardımcı: top mahkemeler listesi (panelde bar chart için)
# -----------------------------------------------------------------------------

def trend_top_mahkemeler(
    top_n: int = 15,
    konu_filtresi: Optional[str] = None,
    kaynak: Optional[str] = None,
    yil_baslangic: Optional[int] = None,
    yil_bitis: Optional[int] = None,
) -> Dict[str, Any]:
    """En sık karar üreten top_n mahkeme (court_chamber)."""
    filters = {
        "top_n": int(top_n),
        "konu": konu_filtresi or "",
        "kaynak": kaynak or "",
        "yil_baslangic": yil_baslangic,
        "yil_bitis": yil_bitis,
    }

    if not _parquet_var_mi():
        return _bos_sonuc(filters, hata=f"Parquet bulunamadı: {PARQUET_PATH}")

    parquet = _parquet_path()
    where_parts: List[str] = [
        "court_chamber IS NOT NULL",
        "court_chamber != ''",
    ]
    if konu_filtresi:
        where_parts.append(
            f"list_contains(topic_tags, '{_esc(konu_filtresi)}')"
        )
    if kaynak:
        where_parts.append(f"source = '{_esc(kaynak)}'")
    if yil_baslangic is not None and yil_bitis is not None:
        where_parts.append(
            f"yil IS NOT NULL AND yil BETWEEN {int(yil_baslangic)} AND {int(yil_bitis)}"
        )
    where_sql = " AND ".join(where_parts)

    sql = f"""
    WITH parsed AS (
      SELECT *,
        TRY_CAST(regexp_extract(COALESCE(decision_date, ''), '{YIL_REGEX}', 1) AS INTEGER) AS yil
      FROM '{parquet}'
    )
    SELECT court_chamber, COUNT(*) AS c
    FROM parsed
    WHERE {where_sql}
    GROUP BY court_chamber
    ORDER BY c DESC
    LIMIT {int(top_n)}
    """

    try:
        con = _connect()
        rows = con.execute(sql).fetchall()
    except Exception as e:
        return _bos_sonuc(filters, hata=f"DuckDB sorgusu başarısız: {e}")

    data: List[Tuple[str, int]] = [(str(r[0]), int(r[1])) for r in rows]
    total = sum(v for _, v in data)
    return {"data": data, "total": total, "filters": filters}


# -----------------------------------------------------------------------------
# Yardımcı: kaynak dağılımı (pie chart için)
# -----------------------------------------------------------------------------

def trend_kaynak_dagilimi(
    konu_filtresi: Optional[str] = None,
    yil_baslangic: Optional[int] = None,
    yil_bitis: Optional[int] = None,
) -> Dict[str, Any]:
    """source bazlı dağılım (pie chart için)."""
    filters = {
        "konu": konu_filtresi or "",
        "yil_baslangic": yil_baslangic,
        "yil_bitis": yil_bitis,
    }

    if not _parquet_var_mi():
        return _bos_sonuc(filters, hata=f"Parquet bulunamadı: {PARQUET_PATH}")

    parquet = _parquet_path()
    where_parts: List[str] = ["source IS NOT NULL", "source != ''"]
    if konu_filtresi:
        where_parts.append(
            f"list_contains(topic_tags, '{_esc(konu_filtresi)}')"
        )
    if yil_baslangic is not None and yil_bitis is not None:
        where_parts.append(
            f"yil IS NOT NULL AND yil BETWEEN {int(yil_baslangic)} AND {int(yil_bitis)}"
        )
    where_sql = " AND ".join(where_parts)

    sql = f"""
    WITH parsed AS (
      SELECT *,
        TRY_CAST(regexp_extract(COALESCE(decision_date, ''), '{YIL_REGEX}', 1) AS INTEGER) AS yil
      FROM '{parquet}'
    )
    SELECT source, COUNT(*) AS c
    FROM parsed
    WHERE {where_sql}
    GROUP BY source
    ORDER BY c DESC
    """

    try:
        con = _connect()
        rows = con.execute(sql).fetchall()
    except Exception as e:
        return _bos_sonuc(filters, hata=f"DuckDB sorgusu başarısız: {e}")

    data: List[Tuple[str, int]] = [(str(r[0]), int(r[1])) for r in rows]
    total = sum(v for _, v in data)
    return {"data": data, "total": total, "filters": filters}
