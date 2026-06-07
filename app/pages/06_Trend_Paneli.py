"""
Karar Trend Paneli (Streamlit)

Türk hukuk emsal kararı dataset'i üzerinde zaman serisi, kaynak/konu
dağılımı ve mahkeme yoğunluk analizleri görselleştirir.

Kullanım: streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# Proje kökünü PYTHONPATH'e ekle
_PROJE_KOK = Path(__file__).resolve().parents[2]
if str(_PROJE_KOK) not in sys.path:
    sys.path.insert(0, str(_PROJE_KOK))


# -----------------------------------------------------------------------------
# Sayfa konfigürasyonu
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Karar Trend Paneli",
    page_icon="📊",
    layout="wide",
)


# -----------------------------------------------------------------------------
# Servis ve kütüphane importları
# -----------------------------------------------------------------------------

try:
    from services.trend import (
        trend_yillik,
        trend_konu_dagilimi,
        trend_mahkeme_konu_matrix,
        trend_aylik,
        trend_top_mahkemeler,
        trend_kaynak_dagilimi,
        filtre_secenekleri,
    )
    _SERVIS_HAZIR = True
    _SERVIS_HATA = None
except Exception as e:
    _SERVIS_HAZIR = False
    _SERVIS_HATA = str(e)


try:
    import pandas as pd
    _PD_HAZIR = True
except Exception as e:
    _PD_HAZIR = False
    pd = None  # type: ignore

try:
    import plotly.express as px
    import plotly.graph_objects as go
    _PLOTLY_HAZIR = True
except Exception as e:
    _PLOTLY_HAZIR = False


st.title("📊 Karar Trend Paneli")
st.caption(
    "Türk emsal kararları üzerinde yıllık trendler, kaynak/konu dağılımları "
    "ve mahkeme yoğunluk analizleri."
)


# -----------------------------------------------------------------------------
# Servis durumu
# -----------------------------------------------------------------------------

if not _SERVIS_HAZIR:
    st.error(f"Trend servisi yüklenemedi: {_SERVIS_HATA}")
    st.stop()

if not _PD_HAZIR:
    st.error("pandas yüklenemedi. `pip install pandas` ile kurun.")
    st.stop()

if not _PLOTLY_HAZIR:
    st.error("plotly yüklenemedi. `pip install plotly>=5` ile kurun.")
    st.stop()


# -----------------------------------------------------------------------------
# Filtre seçenekleri (cache'li)
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=600)
def _secenekleri_yukle() -> Dict[str, Any]:
    return filtre_secenekleri()


with st.spinner("Filtre seçenekleri yükleniyor..."):
    secenekler = _secenekleri_yukle()

if secenekler.get("hata"):
    st.error(f"Veri kaynağı okunamadı: {secenekler['hata']}")
    st.stop()

toplam_karar = int(secenekler.get("toplam_karar", 0))
yil_min = int(secenekler.get("yil_min", 1990))
yil_max = int(secenekler.get("yil_max", 2025))
if yil_min >= yil_max:
    yil_max = yil_min + 1

kaynak_listesi: List[str] = secenekler.get("kaynaklar", []) or []
daire_listesi: List[str] = secenekler.get("daireler", []) or []
konu_listesi: List[str] = secenekler.get("konular", []) or []


# -----------------------------------------------------------------------------
# Yan panel: Filtreler
# -----------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Filtreler")

    konu_secim = st.selectbox(
        "Konu (topic_tag)",
        options=["(Tümü)"] + konu_listesi,
        index=0,
        help="Belirli bir konu (topic) seçerek o etikete sahip kararları süzün.",
    )
    konu_filtresi = "" if konu_secim == "(Tümü)" else konu_secim

    kaynak_secim = st.selectbox(
        "Kaynak (source)",
        options=["(Tümü)"] + kaynak_listesi,
        index=0,
        help="Yargıtay, Danıştay, AYM gibi kaynak filtreleri.",
    )
    kaynak_filtresi = "" if kaynak_secim == "(Tümü)" else kaynak_secim

    daire_secim = st.selectbox(
        "Daire / Mahkeme",
        options=["(Tümü)"] + daire_listesi,
        index=0,
        help="Belirli bir daire veya mahkeme adı.",
    )
    daire_filtresi = "" if daire_secim == "(Tümü)" else daire_secim

    yil_araligi = st.slider(
        "Yıl aralığı",
        min_value=int(yil_min),
        max_value=int(yil_max),
        value=(int(yil_min), int(yil_max)),
        step=1,
    )
    yil_bas, yil_son = int(yil_araligi[0]), int(yil_araligi[1])

    st.divider()
    st.caption(f"Veri seti: **{toplam_karar:,}** karar")
    st.caption(f"Yıl aralığı (tüm veri): **{yil_min} – {yil_max}**")


# -----------------------------------------------------------------------------
# Sorgular (cache'li)
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=300)
def _yillik_cache(konu: str, kaynak: str, daire: str) -> Dict[str, Any]:
    return trend_yillik(
        konu_filtresi=konu or None,
        kaynak=kaynak or None,
        daire=daire or None,
    )


@st.cache_data(show_spinner=False, ttl=300)
def _konu_dagilimi_cache(yb: int, ys: int) -> Dict[str, Any]:
    return trend_konu_dagilimi(yb, ys)


@st.cache_data(show_spinner=False, ttl=300)
def _matrix_cache(n_m: int, n_k: int) -> Dict[str, Any]:
    return trend_mahkeme_konu_matrix(n_m, n_k)


@st.cache_data(show_spinner=False, ttl=300)
def _aylik_cache(konu: str, yb: int, ys: int) -> Dict[str, Any]:
    return trend_aylik(konu, yb, ys)


@st.cache_data(show_spinner=False, ttl=300)
def _top_mahkeme_cache(
    n: int, konu: str, kaynak: str, yb: int, ys: int
) -> Dict[str, Any]:
    return trend_top_mahkemeler(
        top_n=n,
        konu_filtresi=konu or None,
        kaynak=kaynak or None,
        yil_baslangic=yb,
        yil_bitis=ys,
    )


@st.cache_data(show_spinner=False, ttl=300)
def _kaynak_dagilimi_cache(konu: str, yb: int, ys: int) -> Dict[str, Any]:
    return trend_kaynak_dagilimi(
        konu_filtresi=konu or None,
        yil_baslangic=yb,
        yil_bitis=ys,
    )


with st.spinner("Trend verileri hesaplanıyor..."):
    yillik = _yillik_cache(konu_filtresi, kaynak_filtresi, daire_filtresi)
    konu_dag = _konu_dagilimi_cache(yil_bas, yil_son)
    matrix = _matrix_cache(10, 10)
    top_mahkemeler = _top_mahkeme_cache(
        15, konu_filtresi, kaynak_filtresi, yil_bas, yil_son
    )
    kaynak_dag = _kaynak_dagilimi_cache(konu_filtresi, yil_bas, yil_son)


# -----------------------------------------------------------------------------
# Yıllık veriyi yıl aralığına göre kırp
# -----------------------------------------------------------------------------

def _yillik_df(sonuc: Dict[str, Any], yb: int, ys: int):
    rows = sonuc.get("data", []) or []
    df = pd.DataFrame(rows, columns=["yil", "karar_sayisi"])
    if df.empty:
        return df
    df["yil_int"] = pd.to_numeric(df["yil"], errors="coerce")
    df = df.dropna(subset=["yil_int"])
    df["yil_int"] = df["yil_int"].astype(int)
    df = df[(df["yil_int"] >= yb) & (df["yil_int"] <= ys)]
    df = df.sort_values("yil_int")
    return df


df_yillik = _yillik_df(yillik, yil_bas, yil_son)


# -----------------------------------------------------------------------------
# Bilgilendirici metric'ler
# -----------------------------------------------------------------------------

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Toplam karar (veri seti)", f"{toplam_karar:,}")
with m2:
    st.metric(
        "Filtreli karar (yıllık)",
        f"{int(df_yillik['karar_sayisi'].sum()) if not df_yillik.empty else 0:,}",
    )
with m3:
    st.metric("Yıl aralığı", f"{yil_bas} – {yil_son}")
with m4:
    en_yogun = "—"
    if not df_yillik.empty:
        idx = df_yillik["karar_sayisi"].idxmax()
        en_yogun = f"{int(df_yillik.loc[idx, 'yil_int'])} ({int(df_yillik.loc[idx, 'karar_sayisi']):,})"
    st.metric("En yoğun yıl", en_yogun)

# Aktif filtre özeti
aktif_filtreler = []
if konu_filtresi:
    aktif_filtreler.append(f"Konu: **{konu_filtresi}**")
if kaynak_filtresi:
    aktif_filtreler.append(f"Kaynak: **{kaynak_filtresi}**")
if daire_filtresi:
    aktif_filtreler.append(f"Daire: **{daire_filtresi}**")
if aktif_filtreler:
    st.info("Aktif filtreler: " + " | ".join(aktif_filtreler))

st.divider()


# -----------------------------------------------------------------------------
# 1) Bar chart: Yıllık karar sayısı
# -----------------------------------------------------------------------------

st.subheader("📈 Yıllık karar sayısı")
if df_yillik.empty:
    st.info("Seçilen filtreler için yıllık veri bulunamadı.")
else:
    fig_yillik = px.bar(
        df_yillik,
        x="yil_int",
        y="karar_sayisi",
        labels={"yil_int": "Yıl", "karar_sayisi": "Karar sayısı"},
        title=None,
        text="karar_sayisi",
    )
    fig_yillik.update_traces(textposition="outside", cliponaxis=False)
    fig_yillik.update_layout(
        xaxis=dict(dtick=1, type="category"),
        yaxis_title="Karar sayısı",
        xaxis_title="Yıl",
        margin=dict(l=10, r=10, t=20, b=10),
        height=380,
    )
    st.plotly_chart(fig_yillik, use_container_width=True)


# -----------------------------------------------------------------------------
# 2) Pie chart: Kaynak dağılımı + Konu dağılımı (yan yana)
# -----------------------------------------------------------------------------

c1, c2 = st.columns(2)

with c1:
    st.subheader("🥧 Kaynak dağılımı")
    kaynak_rows = kaynak_dag.get("data", []) or []
    df_kaynak = pd.DataFrame(kaynak_rows, columns=["kaynak", "karar_sayisi"])
    if df_kaynak.empty:
        st.info("Kaynak dağılımı için veri yok.")
    else:
        fig_kaynak = px.pie(
            df_kaynak,
            names="kaynak",
            values="karar_sayisi",
            hole=0.35,
        )
        fig_kaynak.update_traces(textposition="inside", textinfo="percent+label")
        fig_kaynak.update_layout(
            margin=dict(l=10, r=10, t=20, b=10),
            height=400,
            showlegend=True,
        )
        st.plotly_chart(fig_kaynak, use_container_width=True)

with c2:
    st.subheader("🏷️ En sık 10 konu")
    konu_rows = konu_dag.get("data", []) or []
    df_konu = pd.DataFrame(konu_rows, columns=["konu", "karar_sayisi"])
    if df_konu.empty:
        st.info("Konu dağılımı için veri yok.")
    else:
        df_konu_sorted = df_konu.sort_values("karar_sayisi", ascending=True)
        fig_konu = px.bar(
            df_konu_sorted,
            x="karar_sayisi",
            y="konu",
            orientation="h",
            labels={"karar_sayisi": "Karar sayısı", "konu": "Konu"},
            text="karar_sayisi",
        )
        fig_konu.update_traces(textposition="outside", cliponaxis=False)
        fig_konu.update_layout(
            margin=dict(l=10, r=10, t=20, b=10),
            height=400,
        )
        st.plotly_chart(fig_konu, use_container_width=True)


# -----------------------------------------------------------------------------
# 3) Heatmap: Mahkeme × Konu yoğunluğu
# -----------------------------------------------------------------------------

st.subheader("🔥 Mahkeme × Konu yoğunluk haritası (Top 10 × Top 10)")
mx = matrix.get("data", {}) or {}
mahkemeler = mx.get("mahkemeler", []) or []
konular = mx.get("konular", []) or []
matriks = mx.get("matrix", []) or []

if not mahkemeler or not konular or not matriks:
    st.info("Mahkeme × Konu matrisi için yeterli veri yok.")
else:
    df_heat = pd.DataFrame(matriks, index=mahkemeler, columns=konular)
    fig_heat = px.imshow(
        df_heat,
        labels=dict(x="Konu", y="Mahkeme / Daire", color="Karar sayısı"),
        x=konular,
        y=mahkemeler,
        color_continuous_scale="YlOrRd",
        aspect="auto",
        text_auto=True,
    )
    fig_heat.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        height=520,
        xaxis=dict(tickangle=-30),
    )
    st.plotly_chart(fig_heat, use_container_width=True)


# -----------------------------------------------------------------------------
# 4) Top 15 mahkeme bar chart
# -----------------------------------------------------------------------------

st.subheader("🏛️ En sık karar üreten 15 mahkeme / daire")
top_rows = top_mahkemeler.get("data", []) or []
df_top = pd.DataFrame(top_rows, columns=["mahkeme", "karar_sayisi"])
if df_top.empty:
    st.info("Filtreye uygun mahkeme verisi yok.")
else:
    df_top_sorted = df_top.sort_values("karar_sayisi", ascending=True)
    fig_top = px.bar(
        df_top_sorted,
        x="karar_sayisi",
        y="mahkeme",
        orientation="h",
        labels={"karar_sayisi": "Karar sayısı", "mahkeme": "Mahkeme / Daire"},
        text="karar_sayisi",
    )
    fig_top.update_traces(textposition="outside", cliponaxis=False)
    fig_top.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        height=520,
    )
    st.plotly_chart(fig_top, use_container_width=True)


# -----------------------------------------------------------------------------
# 5) (Bonus) Aylık zaman serisi — konu seçildiyse
# -----------------------------------------------------------------------------

if konu_filtresi:
    st.subheader(f"🗓️ Aylık trend — “{konu_filtresi}”")
    aylik = _aylik_cache(konu_filtresi, yil_bas, yil_son)
    aylik_rows = aylik.get("data", []) or []
    df_aylik = pd.DataFrame(aylik_rows, columns=["yil_ay", "karar_sayisi"])
    if df_aylik.empty:
        st.info("Seçilen konu/yıl aralığında aylık veri bulunamadı.")
    else:
        df_aylik["tarih"] = pd.to_datetime(df_aylik["yil_ay"] + "-01", errors="coerce")
        df_aylik = df_aylik.dropna(subset=["tarih"]).sort_values("tarih")
        fig_aylik = px.line(
            df_aylik,
            x="tarih",
            y="karar_sayisi",
            markers=True,
            labels={"tarih": "Ay", "karar_sayisi": "Karar sayısı"},
        )
        fig_aylik.update_layout(
            margin=dict(l=10, r=10, t=20, b=10),
            height=360,
        )
        st.plotly_chart(fig_aylik, use_container_width=True)


# -----------------------------------------------------------------------------
# Veriyi indir (CSV)
# -----------------------------------------------------------------------------

st.divider()
st.subheader("⬇️ Veriyi indir")

ind_col1, ind_col2, ind_col3, ind_col4 = st.columns(4)


def _csv_bytes(df) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue().encode("utf-8-sig")


with ind_col1:
    if not df_yillik.empty:
        st.download_button(
            "Yıllık (CSV)",
            data=_csv_bytes(df_yillik[["yil_int", "karar_sayisi"]].rename(
                columns={"yil_int": "yil"}
            )),
            file_name="trend_yillik.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("Yıllık (CSV)", disabled=True, use_container_width=True)

with ind_col2:
    df_konu_full = pd.DataFrame(konu_dag.get("data", []) or [],
                                columns=["konu", "karar_sayisi"])
    if not df_konu_full.empty:
        st.download_button(
            "Konu dağılımı (CSV)",
            data=_csv_bytes(df_konu_full),
            file_name="trend_konu_dagilimi.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("Konu dağılımı (CSV)", disabled=True, use_container_width=True)

with ind_col3:
    if mahkemeler and konular and matriks:
        df_heat_full = pd.DataFrame(matriks, index=mahkemeler, columns=konular)
        df_heat_long = df_heat_full.reset_index().melt(
            id_vars="index", var_name="konu", value_name="karar_sayisi"
        ).rename(columns={"index": "mahkeme"})
        st.download_button(
            "Mahkeme×Konu (CSV)",
            data=_csv_bytes(df_heat_long),
            file_name="trend_mahkeme_konu_matrix.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("Mahkeme×Konu (CSV)", disabled=True, use_container_width=True)

with ind_col4:
    if not df_top.empty:
        st.download_button(
            "Top mahkemeler (CSV)",
            data=_csv_bytes(df_top),
            file_name="trend_top_mahkemeler.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("Top mahkemeler (CSV)", disabled=True, use_container_width=True)


# -----------------------------------------------------------------------------
# Notlar
# -----------------------------------------------------------------------------

with st.expander("ℹ️ Yöntem ve veri notları"):
    st.markdown(
        """
- **Veri kaynağı:** `data/final/all_decisions.parquet` (DuckDB ile sorgulanır).
- **Yıl çıkarımı:** `decision_date` alanından `(19\\d{2}|20\\d{2})` regex'i ile çıkarılır.
  Bu nedenle yıl bilgisi eksik/bozuk olan kayıtlar zaman serisinden hariç tutulur.
- **Konu dağılımı:** `topic_tags` array'i `UNNEST` ile patlatılır; bir karar
  birden fazla konuya katkı verebilir.
- **Heatmap:** En sık 10 mahkeme × en sık 10 konu üzerinden hesaplanır.
- **Hatalar (`hata` alanı):** parquet dosyası bulunamazsa veya DuckDB sorgusu
  başarısız olursa servis fonksiyonları boş veri + `hata` mesajıyla döner.
        """
    )

# Hata mesajları (varsa)
for ad, sonuc in [
    ("Yıllık", yillik),
    ("Konu dağılımı", konu_dag),
    ("Mahkeme×Konu", matrix),
    ("Top mahkemeler", top_mahkemeler),
    ("Kaynak dağılımı", kaynak_dag),
]:
    if isinstance(sonuc, dict) and sonuc.get("hata"):
        st.warning(f"{ad}: {sonuc['hata']}")
