"""Streamlit: Faiz & Tahsilat Hesaplayıcı.

LLM kullanmaz — services.faiz_hesaplayici üzerinden saf Decimal hesabı.
"""
from __future__ import annotations

import io
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

# services modülüne erişim için proje kökünü PATH'e ekle
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.faiz_hesaplayici import hesapla, UYARI_METNI  # noqa: E402


st.set_page_config(
    page_title="Faiz & Tahsilat Hesaplayıcı",
    page_icon="💰",
    layout="wide",
)

st.title("💰 Faiz & Tahsilat Hesaplayıcı")
st.caption(
    "Türk hukuku icra/tahsilat süreci — temerrüt faizi, İİK harçları "
    "ve vekalet ücreti tahmini."
)

st.warning(
    "⚠️ **Yasal Sorumluluk Reddi:** Bu araç **tahmini** hesap yapar, "
    "**kesin değer değildir**. Resmi tahsilat için **avukat/muhasebeci kontrolü "
    "zorunludur**. Mahkeme ve icra müdürlüğü takdiri esastır.",
    icon="⚖️",
)


# -----------------------------------------------------------------------------
# Form
# -----------------------------------------------------------------------------

with st.form("faiz_form"):
    col1, col2 = st.columns(2)

    with col1:
        anapara_input = st.number_input(
            "Anapara (TRY)",
            min_value=0.0,
            value=100000.0,
            step=1000.0,
            format="%.2f",
            help="Alacağın anaparası — Türk Lirası cinsinden.",
        )
        temerrut_tarihi = st.date_input(
            "Temerrüt tarihi",
            value=date.today() - timedelta(days=365),
            min_value=date(2000, 1, 1),
            max_value=date.today(),
            help="Borçlunun temerrüde düştüğü tarih. Faiz bu tarihten itibaren işlemeye başlar.",
        )

    with col2:
        vade_tarihi = st.date_input(
            "Vade / hesap kesim tarihi",
            value=date.today(),
            min_value=date(2000, 1, 1),
            help="Hesabın kesileceği tarih. Bugün varsayılan.",
        )
        faiz_turu = st.selectbox(
            "Faiz türü",
            options=["yasal", "ticari_avans", "tcmb_reeskont"],
            format_func=lambda x: {
                "yasal": "Yasal Faiz (TBK 88)",
                "ticari_avans": "Ticari Avans (TCMB)",
                "tcmb_reeskont": "TCMB Reeskont",
            }.get(x, x),
            help="Yasal: TBK 88. Ticari: tacirler arası. Reeskont: TCMB politika oranı.",
        )

    hesapla_btn = st.form_submit_button(
        "Hesapla", type="primary", use_container_width=True
    )


# -----------------------------------------------------------------------------
# Sonuç
# -----------------------------------------------------------------------------

def _format_try(x: Decimal | float) -> str:
    """Türk lirası formatı — 1.234.567,89 ₺."""
    if isinstance(x, Decimal):
        f = float(x)
    else:
        f = float(x)
    return f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " ₺"


if hesapla_btn:
    try:
        sonuc = hesapla(
            anapara=Decimal(str(anapara_input)),
            temerrut_tarihi=temerrut_tarihi,
            vade_tarihi=vade_tarihi,
            faiz_turu=faiz_turu,
        )
    except Exception as e:
        st.error(f"Hesaplama hatası: {e}")
        st.stop()

    st.subheader("📊 Sonuç Özeti")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Anapara", _format_try(sonuc["anapara"]))
    m2.metric(
        "Faiz Tutarı",
        _format_try(sonuc["faiz_tutari"]),
        delta=f"{sonuc['gun_sayisi']} gün",
    )
    m3.metric(
        "Harçlar (Cezaevi + Tahsil)",
        _format_try(sonuc["cezaevi_harci"] + sonuc["tahsil_harci"]),
    )
    m4.metric("Vekalet Ücreti", _format_try(sonuc["vekalet_ucreti"]))

    st.markdown(
        f"### 💵 Toplam Alacak: **{_format_try(sonuc['toplam_alacak'])}**"
    )

    st.caption(
        f"Faiz dönemi: **{sonuc['faiz_baslangic'].isoformat()}** → "
        f"**{sonuc['faiz_bitis'].isoformat()}** "
        f"({sonuc['gun_sayisi']} gün)"
    )

    # -- Detay tablosu --
    st.subheader("📋 Kalem Detayı")
    detay_df = pd.DataFrame([
        {"Kalem": "Anapara", "Tutar (TRY)": float(sonuc["anapara"])},
        {"Kalem": "Faiz Tutarı", "Tutar (TRY)": float(sonuc["faiz_tutari"])},
        {"Kalem": "Cezaevi Harcı (%2)", "Tutar (TRY)": float(sonuc["cezaevi_harci"])},
        {"Kalem": "Tahsil Harcı (%4.55)", "Tutar (TRY)": float(sonuc["tahsil_harci"])},
        {"Kalem": "Vekalet Ücreti (AAÜT 2024)", "Tutar (TRY)": float(sonuc["vekalet_ucreti"])},
        {"Kalem": "TOPLAM ALACAK", "Tutar (TRY)": float(sonuc["toplam_alacak"])},
    ])
    st.dataframe(
        detay_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tutar (TRY)": st.column_config.NumberColumn(format="%.2f ₺"),
        },
    )

    # -- Yıllık breakdown --
    if sonuc["yillik_breakdown"]:
        st.subheader("📅 Yıllık Faiz Dağılımı")
        yillik_df = pd.DataFrame([
            {
                "Yıl": b["yil"],
                "Gün Sayısı": b["gun"],
                "Yıllık Oran (%)": b["oran"],
                "Faiz (TRY)": float(b["faiz"]),
            }
            for b in sonuc["yillik_breakdown"]
        ])
        st.dataframe(
            yillik_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Faiz (TRY)": st.column_config.NumberColumn(format="%.2f ₺"),
                "Yıllık Oran (%)": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    # -- Pasta grafiği --
    st.subheader("🥧 Tutar Dağılımı")
    try:
        import plotly.express as px

        pasta_df = pd.DataFrame({
            "Kalem": ["Anapara", "Faiz", "Cezaevi Harcı", "Tahsil Harcı", "Vekalet"],
            "Tutar": [
                float(sonuc["anapara"]),
                float(sonuc["faiz_tutari"]),
                float(sonuc["cezaevi_harci"]),
                float(sonuc["tahsil_harci"]),
                float(sonuc["vekalet_ucreti"]),
            ],
        })
        # 0 olanları çıkar (görsel temizliği)
        pasta_df = pasta_df[pasta_df["Tutar"] > 0]
        fig = px.pie(
            pasta_df,
            names="Kalem",
            values="Tutar",
            title="Toplam Alacak Dağılımı",
            hole=0.35,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.info("Plotly kurulu değil — grafik gösterilemiyor. `pip install plotly` ile kurabilirsiniz.")

    # -- Uyarı --
    st.error(f"⚖️ {sonuc['uyari']}", icon="⚠️")

    # -- Excel indirme --
    st.subheader("📥 Excel Olarak İndir")

    @st.cache_data
    def _excel_olustur(detay: pd.DataFrame, yillik: pd.DataFrame | None, meta: dict) -> bytes:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            detay.to_excel(w, sheet_name="Özet", index=False)
            meta_df = pd.DataFrame(list(meta.items()), columns=["Alan", "Değer"])
            meta_df.to_excel(w, sheet_name="Meta", index=False)
            if yillik is not None and not yillik.empty:
                yillik.to_excel(w, sheet_name="Yıllık Faiz", index=False)
        return buf.getvalue()

    meta = {
        "Faiz Türü": {
            "yasal": "Yasal Faiz (TBK 88)",
            "ticari_avans": "Ticari Avans (TCMB)",
            "tcmb_reeskont": "TCMB Reeskont",
        }.get(faiz_turu, faiz_turu),
        "Temerrüt Tarihi": temerrut_tarihi.isoformat(),
        "Vade Tarihi": vade_tarihi.isoformat(),
        "Faiz Başlangıç": sonuc["faiz_baslangic"].isoformat(),
        "Faiz Bitiş": sonuc["faiz_bitis"].isoformat(),
        "Gün Sayısı": sonuc["gun_sayisi"],
        "Uyarı": sonuc["uyari"],
    }

    yillik_excel = pd.DataFrame([
        {
            "Yıl": b["yil"],
            "Gün Sayısı": b["gun"],
            "Yıllık Oran (%)": b["oran"],
            "Faiz (TRY)": float(b["faiz"]),
        }
        for b in sonuc["yillik_breakdown"]
    ]) if sonuc["yillik_breakdown"] else None

    try:
        excel_bytes = _excel_olustur(detay_df, yillik_excel, meta)
        st.download_button(
            label="📄 Excel İndir (.xlsx)",
            data=excel_bytes,
            file_name=f"faiz_hesabi_{vade_tarihi.isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except ImportError:
        st.warning("Excel indirme için `openpyxl` kurulu olmalı: `pip install openpyxl`")

else:
    st.info(
        "Yukarıdaki formu doldurun ve **Hesapla** düğmesine basın. "
        "Hesaplama yerel ve hızlıdır (LLM kullanılmaz)."
    )

# -----------------------------------------------------------------------------
# Yardım
# -----------------------------------------------------------------------------

with st.expander("ℹ️ Hesaplama Hakkında"):
    st.markdown(
        """
        **Faiz türleri:**
        - **Yasal Faiz (TBK 88):** Bakanlar Kurulu kararıyla belirlenen, taraflar arası anlaşma yoksa uygulanan oran.
        - **Ticari Avans (TCMB):** Tacirler arası işlerde uygulanan TCMB avans oranı.
        - **TCMB Reeskont:** TCMB reeskont politika oranı.

        **İİK harçları:**
        - **Cezaevi harcı (%2):** İcra İflas Kanunu — alacak üzerinden.
        - **Tahsil harcı (%4.55):** Harçlar Kanunu — tahsilat aşamasında.

        **Vekalet ücreti:** Avukatlık Asgari Ücret Tarifesi 2024 — kademeli, yaklaşık.

        **Gün hesabı:** `temerrüt_tarihi + 1` günden `vade_tarihi`ne kadar (her iki uç dahil).
        Yıllar arası farklı oranlar için aralık yıllara bölünerek ayrı ayrı hesaplanır.

        **Para hesabı:** `Decimal` aritmetiği — kuruşa yuvarlama (`ROUND_HALF_UP`).

        ---
        """
        f"_{UYARI_METNI}_"
    )
