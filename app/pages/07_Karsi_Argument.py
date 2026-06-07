"""
Karşı Argüman Öngörü Sayfası — "Şeytanın Avukatı" modu.

Kullanıcı kendi tezini anlatır, sistem RAG + LLM ile karşı tarafın
muhtemel argümanlarını ve her birine karşı rebuttal önerisini listeler.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Proje kökünü PYTHONPATH'e ekle (streamlit pages alt dizininden çalışırken gerekli).
_PROJE_KOK = Path(__file__).resolve().parents[2]
if str(_PROJE_KOK) not in sys.path:
    sys.path.insert(0, str(_PROJE_KOK))

# Servis importları.
try:
    from services.karsi_argument import (
        karsi_argument_uret,
        DAVA_TURU_LABEL,
        YASAL_UYARI,
    )
    _SERVIS_HAZIR = True
    _SERVIS_HATA = None
except Exception as e:  # pragma: no cover
    _SERVIS_HAZIR = False
    _SERVIS_HATA = str(e)
    DAVA_TURU_LABEL = {"genel": "Genel"}
    YASAL_UYARI = (
        "Bu çıktı bir yapay zekâ öngörüsüdür; gerçek mahkeme süreci farklı "
        "olabilir."
    )

try:
    from llm.provider import is_available as _llm_is_available
    _LLM_VAR = _llm_is_available()
except Exception:
    _LLM_VAR = False


st.set_page_config(
    page_title="Karşı Argüman Öngörüsü",
    page_icon="⚔️",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Başlık
# ---------------------------------------------------------------------------

st.title("⚔️ Karşı Argüman Öngörüsü")
st.caption(
    "Kendi tezinizi anlatın — sistem 'şeytanın avukatı' rolüne girerek "
    "karşı tarafın yapabileceği en güçlü argümanları sıralar ve her birine "
    "karşı rebuttal önerir."
)


# ---------------------------------------------------------------------------
# Servis / LLM durum kontrolleri
# ---------------------------------------------------------------------------

if not _SERVIS_HAZIR:
    st.error(
        "Karşı argüman servisi (services/karsi_argument.py) yüklenemedi:\n\n"
        f"`{_SERVIS_HATA}`"
    )
    st.stop()

if not _LLM_VAR:
    st.warning(
        "LLM API key bulunamadı (`ANTHROPIC_API_KEY` veya `GOOGLE_API_KEY`). "
        "**DEMO MODU**: sadece RAG ile emsaller çekilir, karşı argüman ve "
        "rebuttal üretimi sınırlı olur. Tam analiz için `.env` dosyasına "
        "API key ekleyin."
    )


# ---------------------------------------------------------------------------
# Yan panel: ayarlar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Ayarlar")
    top_k = st.slider(
        "Çekilecek emsal sayısı (k)",
        min_value=3, max_value=10, value=5, step=1,
        help="RAG ile karşıt sorgu üzerinden çekilecek emsal karar sayısı.",
    )
    st.divider()
    st.markdown("**Yasal Uyarı**")
    st.info(YASAL_UYARI)


# ---------------------------------------------------------------------------
# Form: tez + dava türü
# ---------------------------------------------------------------------------

st.markdown("### 1. Tezinizi Anlatın")

with st.form("karsi_arg_form", clear_on_submit=False):
    tez = st.text_area(
        "Kendi teziniz",
        height=180,
        placeholder=(
            "Davamda şunu iddia ediyorum: ...\n\n"
            "Örnek: Müvekkilim emekli olup tek geliri emekli maaşıdır. "
            "Bu nedenle, kendisine karşı başlatılan icra takibinde emekli "
            "maaşı haczedilemez; haciz işleminin kaldırılmasını talep "
            "ediyoruz."
        ),
        key="tez_input",
    )

    col_a, col_b = st.columns([2, 1])
    with col_a:
        dava_anahtarlari = list(DAVA_TURU_LABEL.keys())
        dava_turu = st.selectbox(
            "Dava türü",
            options=dava_anahtarlari,
            index=dava_anahtarlari.index("genel") if "genel" in dava_anahtarlari else 0,
            format_func=lambda x: DAVA_TURU_LABEL.get(x, x),
        )
    with col_b:
        st.caption(" ")  # hizalama
        submit = st.form_submit_button(
            "⚔️ Karşı Argümanları Üret",
            type="primary",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Çalıştır
# ---------------------------------------------------------------------------

if submit:
    if not tez or not tez.strip():
        st.error("Lütfen önce tezinizi yazın.")
    else:
        with st.spinner(
            "Anti-tez sorgusu üretiliyor, emsaller çekiliyor, "
            "karşı argümanlar hazırlanıyor..."
        ):
            try:
                sonuc = karsi_argument_uret(
                    kendi_tezi=tez.strip(),
                    dava_turu=dava_turu,
                    k=top_k,
                )
            except Exception as e:
                sonuc = None
                st.error(f"Karşı argüman üretimi başarısız: {e}")

        if sonuc:
            st.session_state["karsi_arg_sonuc"] = sonuc


# ---------------------------------------------------------------------------
# Sonuçları göster
# ---------------------------------------------------------------------------

sonuc = st.session_state.get("karsi_arg_sonuc")

if sonuc:
    st.divider()
    st.markdown("### 2. Analiz Sonucu")

    # Üst meta
    mcol1, mcol2, mcol3 = st.columns([1, 1, 2])
    with mcol1:
        st.metric(
            "Argüman sayısı",
            len(sonuc.get("muhtemel_karsi_argumanlar", [])),
        )
    with mcol2:
        st.metric(
            "Dayanak emsal",
            len(sonuc.get("dayanak_emsaller", [])),
        )
    with mcol3:
        if sonuc.get("demo_modu"):
            st.warning("DEMO MODU aktif (sınırlı çıktı).")

    # Anti-tez sorgusu — neyle aradığımızı gösterelim, debug ve şeffaflık için.
    anti_q = sonuc.get("anti_tez_query") or ""
    if anti_q:
        with st.expander(
            "🔍 RAG için üretilen anti-tez sorgusu (şeffaflık)",
            expanded=False,
        ):
            st.code(anti_q, language="text")

    # Özet uyarı
    ozet_uyari = (sonuc.get("ozet_uyari") or "").strip()
    if ozet_uyari:
        st.markdown("#### ⚠️ Tezinizin En Zayıf Noktası")
        st.warning(ozet_uyari)

    # Uyarı / hata satırı (varsa)
    uyari = (sonuc.get("uyari") or "").strip()
    if uyari:
        st.caption(f"_İşlem notu: {uyari}_")

    # Karşı argüman kartları — her biri bir card.
    st.markdown("#### 🛡️ Muhtemel Karşı Argümanlar")
    argumanlar = sonuc.get("muhtemel_karsi_argumanlar", []) or []

    if not argumanlar:
        st.info("Karşı argüman üretilemedi.")
    else:
        # Karar_id -> atif ve özet için lookup hazırla.
        emsal_lookup = {
            d["karar_id"]: d for d in sonuc.get("dayanak_emsaller", [])
        }

        for i, arg in enumerate(argumanlar, start=1):
            with st.container(border=True):
                ust1, ust2 = st.columns([3, 1])
                with ust1:
                    st.markdown(f"##### Karşı Argüman {i}")
                with ust2:
                    guc = int(arg.get("guc_skoru") or 0)
                    st.caption(f"Güç skoru: **{guc}/10**")

                # Progress bar (0-1 aralığında).
                st.progress(
                    max(0.0, min(1.0, guc / 10.0)),
                    text=f"Tehdit gücü: {guc}/10",
                )

                # Argüman metni
                st.markdown("**Argüman:**")
                st.write(arg.get("arguman", "—"))

                # Dayanak emsaller
                dayanak_ids = arg.get("dayanak_emsal", []) or []
                if dayanak_ids:
                    st.markdown("**Dayanak Emsal(ler):**")
                    for kid in dayanak_ids:
                        em = emsal_lookup.get(kid)
                        if em:
                            atif = em.get("atif") or kid
                            st.markdown(f"- `{kid}` — {atif}")
                        else:
                            st.markdown(f"- `{kid}`")
                else:
                    st.caption("_Dayanak emsal belirtilmedi._")

                # Rebuttal
                st.markdown("**🗡️ Sizin cevabınız (rebuttal):**")
                st.success(arg.get("rebuttal") or "—")

    # Alt: kullanılan emsallerin detayı
    st.divider()
    st.markdown("### 3. Kullanılan Emsal Kararlar")
    emsaller = sonuc.get("dayanak_emsaller", []) or []
    if not emsaller:
        st.info("RAG'dan emsal çekilemedi.")
    else:
        for i, em in enumerate(emsaller, start=1):
            with st.expander(
                f"📚 Emsal {i} — {em.get('atif', '—')} "
                f"(karar_id: `{em.get('karar_id', '—')}`)",
                expanded=False,
            ):
                st.markdown("**Karar ID:** " + str(em.get("karar_id", "—")))
                st.markdown("**Atıf:** " + str(em.get("atif", "—")))
                st.markdown("**İlgili Bölüm:**")
                st.write(em.get("ozet", "") or "_(boş)_")

    # Yasal uyarı — sayfa altı.
    st.divider()
    st.warning(
        "⚖️ **Yasal Uyarı:** "
        + (sonuc.get("yasal_uyari") or YASAL_UYARI)
        + " Bu AI öngörüsüdür, gerçek mahkeme süreci farklı olabilir."
    )

    # Sonucu temizleme butonu
    if st.button("🧹 Sonucu Temizle", use_container_width=False):
        st.session_state.pop("karsi_arg_sonuc", None)
        st.rerun()

else:
    st.info(
        "Tezinizi yazıp **Karşı Argümanları Üret** butonuna basın. "
        "Sistem, sizin pozisyonunuza karşı tarafın yapabileceği "
        "argümanları sıralayacak."
    )
