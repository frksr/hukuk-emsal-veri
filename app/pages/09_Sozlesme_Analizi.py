"""
Sözleşme Analizi — Streamlit sayfası.

Kullanıcı bir sözleşme dosyası (PDF/DOCX/TXT) yükler. Sistem:
1. Dosyayı parse eder.
2. Maddeleri ayırır.
3. LLM ile madde madde risk analizi yapar.
4. Genel özet, taraflar, eksik maddeler ve toplam risk skoru üretir.

Yasal Uyarı: AI analizi hukuki danışmanlığın yerine geçmez.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Proje kökünü PYTHONPATH'e ekle
_PROJE_KOK = Path(__file__).resolve().parents[2]
if str(_PROJE_KOK) not in sys.path:
    sys.path.insert(0, str(_PROJE_KOK))

# Servis importları
try:
    from services.sozlesme import (
        parse_dosya,
        madde_ayir,
        analiz_et,
        rapor_docx,
        rapor_pdf,
        SOZLESME_TURLERI,
        YASAL_UYARI,
    )
    _SERVIS_HAZIR = True
    _SERVIS_HATA = None
except Exception as e:
    _SERVIS_HAZIR = False
    _SERVIS_HATA = str(e)

try:
    from llm.provider import status as llm_status  # noqa: E402
    _LLM_DURUM_VAR = True
except Exception:
    _LLM_DURUM_VAR = False


st.set_page_config(
    page_title="Sözleşme Analizi",
    page_icon="📑",
    layout="wide",
)

st.title("📑 Sözleşme Analizi")
st.caption(
    "Sözleşmenizi yükleyin — sistem maddelere ayırır, her madde için risk seviyesi "
    "ve öneri üretir, eksik maddeleri tespit eder."
)

st.warning(f"⚖️ **Yasal Uyarı:** {YASAL_UYARI}")

# ---- Servis durum kontrolü ------------------------------------------------
if not _SERVIS_HAZIR:
    st.error(f"Sözleşme analiz servisi yüklenemedi: {_SERVIS_HATA}")
    st.stop()

# ---- Sidebar: LLM durum + ayarlar ----------------------------------------
with st.sidebar:
    st.subheader("LLM Sağlayıcı")
    if _LLM_DURUM_VAR:
        try:
            s = llm_status()
            st.caption(f"Varsayılan: **{s.get('default', '—')}**")
            anth = s.get("anthropic", False)
            gem = s.get("gemini", False)
            st.write(f"- Anthropic: {'✓ hazır' if anth else '✗ key yok'}")
            st.write(f"- Gemini: {'✓ hazır' if gem else '✗ key yok'}")
            if not (anth or gem):
                st.error(
                    "Hiçbir LLM key bulunamadı. `.env` dosyasına "
                    "`ANTHROPIC_API_KEY` veya `GOOGLE_API_KEY` ekleyin."
                )
        except Exception as e:
            st.warning(f"LLM durumu okunamadı: {e}")
    else:
        st.info("LLM durum modülü yüklenemedi.")

    st.divider()
    st.markdown("**Bu araç hakkında**")
    st.caption(
        "Sözleşmeyi TBK, TTK ve KVKK çerçevesinde değerlendirir. "
        "Çıktı yalnızca bilgilendirme amaçlıdır."
    )


# ---- Form: dosya + sözleşme türü -----------------------------------------
col_u1, col_u2 = st.columns([2, 1])

with col_u1:
    yuklenen = st.file_uploader(
        "Sözleşme dosyası (PDF, DOCX veya TXT)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=False,
        key="sozlesme_dosya",
    )

with col_u2:
    sozlesme_turu = st.selectbox(
        "Sözleşme türü",
        options=list(SOZLESME_TURLERI.keys()),
        format_func=lambda k: SOZLESME_TURLERI[k],
        index=list(SOZLESME_TURLERI.keys()).index("genel"),
        key="sozlesme_turu_secim",
    )

# Parse edilen metni hemen göster (önizleme)
parse_metin: str = ""
parse_hata: str | None = None
maddeler_onizleme: list[dict] = []

if yuklenen is not None:
    ad = yuklenen.name
    ext = Path(ad).suffix.lower()
    try:
        parse_metin = parse_dosya(yuklenen, ext)
    except Exception as e:
        parse_hata = str(e)

    if parse_hata:
        st.error(f"Dosya parse edilemedi: {parse_hata}")
    elif parse_metin:
        maddeler_onizleme = madde_ayir(parse_metin)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Karakter", f"{len(parse_metin):,}")
        with m2:
            st.metric("Tahmini madde sayısı", len(maddeler_onizleme))
        with m3:
            st.metric("Dosya", ad)
        with st.expander("Parse edilen metni ön izle", expanded=False):
            onizleme = parse_metin[:4000] + (
                "\n\n[... metin kısaltıldı ...]" if len(parse_metin) > 4000 else ""
            )
            st.text(onizleme)
    else:
        st.warning("Dosyadan metin çıkarılamadı.")

st.divider()

# ---- Analiz Et butonu -----------------------------------------------------
buton_aktif = bool(parse_metin and parse_metin.strip())
col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
with col_b2:
    analiz_btn = st.button(
        "🔍 Analiz Et",
        type="primary",
        use_container_width=True,
        disabled=not buton_aktif,
    )

if analiz_btn and buton_aktif:
    with st.spinner("Sözleşme analiz ediliyor — bu işlem 30-90 saniye sürebilir..."):
        try:
            sonuc = analiz_et(parse_metin, sozlesme_turu=sozlesme_turu)
            st.session_state["sozlesme_sonuc"] = sonuc
            st.session_state["sozlesme_dosya_adi"] = (
                yuklenen.name if yuklenen is not None else "sozlesme"
            )
        except Exception as e:
            st.error(f"Analiz sırasında hata: {e}")


# ---- Sonuç gösterimi ------------------------------------------------------
def _risk_renk(seviye: str) -> str:
    return {
        "dusuk": "#16a34a",  # yeşil
        "orta": "#d97706",   # turuncu
        "yuksek": "#dc2626",  # kırmızı
    }.get(seviye, "#6b7280")


def _risk_etiket(seviye: str) -> str:
    return {
        "dusuk": "DÜŞÜK",
        "orta": "ORTA",
        "yuksek": "YÜKSEK",
    }.get(seviye, "BİLİNMİYOR")


def _risk_badge_html(seviye: str) -> str:
    renk = _risk_renk(seviye)
    etiket = _risk_etiket(seviye)
    return (
        f"<span style='display:inline-block; padding:3px 10px; "
        f"background:{renk}; color:white; border-radius:12px; "
        f"font-size:0.78em; font-weight:600;'>{etiket}</span>"
    )


def _gauge_chart(skor: int):
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    if skor < 35:
        bar_color = "#16a34a"
    elif skor < 65:
        bar_color = "#d97706"
    else:
        bar_color = "#dc2626"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=skor,
        number={"suffix": " / 100", "font": {"size": 28}},
        title={"text": "Toplam Risk Skoru", "font": {"size": 16}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": bar_color, "thickness": 0.3},
            "steps": [
                {"range": [0, 35], "color": "#dcfce7"},
                {"range": [35, 65], "color": "#fef3c7"},
                {"range": [65, 100], "color": "#fee2e2"},
            ],
            "threshold": {
                "line": {"color": "black", "width": 2},
                "thickness": 0.75,
                "value": skor,
            },
        },
    ))
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


if "sozlesme_sonuc" in st.session_state:
    sonuc = st.session_state["sozlesme_sonuc"]
    dosya_adi_taban = Path(st.session_state.get("sozlesme_dosya_adi", "sozlesme")).stem

    if sonuc.get("hata"):
        st.error(f"Analiz hatası: {sonuc['hata']}")
    else:
        st.divider()
        st.subheader("📊 Analiz Sonucu")

        # ---- Üst: özet kartları + risk gauge ----
        ust_sol, ust_sag = st.columns([3, 2])

        with ust_sol:
            k1, k2, k3 = st.columns(3)
            with k1:
                st.markdown("**Taraflar**")
                taraflar = sonuc.get("taraflar", []) or []
                if taraflar:
                    for t in taraflar:
                        st.markdown(f"- {t}")
                else:
                    st.caption("Tespit edilemedi")
            with k2:
                st.markdown("**Ana Konu**")
                st.write(sonuc.get("ana_konu", "") or "—")
            with k3:
                st.markdown("**Süre & Fesih**")
                st.write(sonuc.get("sure_ve_fesih", "") or "—")

            st.markdown("**Genel Özet**")
            st.info(sonuc.get("genel_ozet", "") or "—")

            ana_riskler = sonuc.get("ana_riskler", []) or []
            if ana_riskler:
                st.markdown("**Ana Riskler**")
                for r in ana_riskler:
                    st.markdown(f"- ⚠️ {r}")

        with ust_sag:
            skor = int(sonuc.get("toplam_risk_skoru", 0))
            fig = _gauge_chart(skor)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.metric("Toplam Risk Skoru", f"{skor} / 100")

            mm1, mm2 = st.columns(2)
            with mm1:
                st.metric("Madde", sonuc.get("madde_sayisi", 0))
            with mm2:
                st.metric("Karakter", f"{sonuc.get('karakter_sayisi', 0):,}")

        st.divider()

        # ---- Orta: madde madde liste + kritik öneriler ----
        madde_analizleri: list[dict] = sonuc.get("madde_analizleri", []) or []
        sol, sag = st.columns([3, 2])

        with sol:
            st.markdown("### 📋 Madde Madde Analiz")
            if not madde_analizleri:
                st.caption("Madde analizi üretilemedi.")
            else:
                # Filtre
                filtre_secimi = st.multiselect(
                    "Risk seviyesine göre filtrele",
                    options=["dusuk", "orta", "yuksek"],
                    default=["dusuk", "orta", "yuksek"],
                    format_func=_risk_etiket,
                    key="risk_filtre",
                )
                for m in madde_analizleri:
                    seviye = m.get("risk_seviye", "orta")
                    if seviye not in filtre_secimi:
                        continue
                    no = m.get("no", "?")
                    baslik = (
                        "Giriş / Başlık"
                        if str(no).lower() == "giris"
                        else f"Madde {no}"
                    )
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.markdown(f"**{baslik}**")
                        with c2:
                            st.markdown(_risk_badge_html(seviye), unsafe_allow_html=True)
                        if m.get("ozet"):
                            st.write(m["ozet"])
                        if m.get("oneri"):
                            st.markdown(f"💡 **Öneri:** {m['oneri']}")
                        kanunlar = m.get("ilgili_kanunlar", []) or []
                        if kanunlar:
                            tags = " ".join(
                                f"<span style='display:inline-block; padding:2px 8px; "
                                f"margin:2px; background:#eef2ff; color:#1e3a8a; "
                                f"border-radius:10px; font-size:0.78em; "
                                f"border:1px solid #c7d2fe;'>{k}</span>"
                                for k in kanunlar
                            )
                            st.markdown(tags, unsafe_allow_html=True)

        with sag:
            st.markdown("### 🚨 Kritik Maddeler")
            kritikler = [
                m for m in madde_analizleri
                if m.get("risk_seviye") == "yuksek"
            ]
            if not kritikler:
                st.success(
                    "Yüksek riskli madde tespit edilmedi. "
                    "Yine de orta riskli maddeleri gözden geçirmenizi tavsiye ederiz."
                )
            else:
                st.caption(
                    f"{len(kritikler)} adet yüksek riskli madde bulundu. "
                    "Öneriler aşağıdadır:"
                )
                for m in kritikler:
                    no = m.get("no", "?")
                    with st.container(border=True):
                        st.markdown(
                            f"**Madde {no}** {_risk_badge_html('yuksek')}",
                            unsafe_allow_html=True,
                        )
                        if m.get("oneri"):
                            st.markdown(f"💡 {m['oneri']}")
                        else:
                            st.caption("Öneri üretilemedi.")

        st.divider()

        # ---- Alt: eksik maddeler ----
        eksikler = sonuc.get("eksik_maddeler", []) or []
        st.markdown("### 📝 Eksik / Eklenmesi Önerilen Maddeler")
        if eksikler:
            for e in eksikler:
                st.markdown(f"- ➕ {e}")
        else:
            st.caption("Eksik madde tespit edilmedi.")

        # ---- Yasal uyarı ----
        st.divider()
        st.warning(f"⚖️ {sonuc.get('yasal_uyari', YASAL_UYARI)}")

        # ---- Download butonları ----
        st.markdown("### ⬇️ Raporu İndir")
        d1, d2 = st.columns(2)

        with d1:
            try:
                docx_bytes = rapor_docx(sonuc)
                st.download_button(
                    label="📄 .docx olarak indir",
                    data=docx_bytes,
                    file_name=f"{dosya_adi_taban}_analiz.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            except Exception as e:
                st.caption(f".docx üretilemedi: {e}")

        with d2:
            try:
                pdf_bytes = rapor_pdf(sonuc)
                st.download_button(
                    label="📑 .pdf olarak indir",
                    data=pdf_bytes,
                    file_name=f"{dosya_adi_taban}_analiz.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.caption(f".pdf üretilemedi: {e}")
