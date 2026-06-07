"""
Karar Özetleyici Streamlit Sayfası

Kullanıcı bir karar metnini yapıştırır veya dataset'ten seçer,
sistem sade Türkçe özet üretir.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Proje kökünü PYTHONPATH'e ekle (streamlit pages alt dizininden çalışırken gerekli)
_PROJE_KOK = Path(__file__).resolve().parents[2]
if str(_PROJE_KOK) not in sys.path:
    sys.path.insert(0, str(_PROJE_KOK))

# Servis importları
try:
    from services.karar_ozet import ozet_uret, UZUNLUK_PROFILLERI, YASAL_NOT
    _SERVIS_HAZIR = True
    _SERVIS_HATA = None
except Exception as e:
    _SERVIS_HAZIR = False
    _SERVIS_HATA = str(e)

try:
    from services.rag import get_full_decision
    _RAG_HAZIR = True
    _RAG_HATA = None
except Exception as e:
    _RAG_HAZIR = False
    _RAG_HATA = str(e)

try:
    from llm.provider import generate as _llm_generate  # noqa: F401
    _LLM_HAZIR = True
except Exception:
    _LLM_HAZIR = False


st.set_page_config(
    page_title="Karar Özetleyici",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Karar Özetleyici")
st.caption(
    "Türk mahkeme kararlarını sade Türkçe'ye çevirir. "
    "Genç avukatlar ve hukuk bilgisi olmayan vatandaşlar için anlaşılır özetler üretir."
)

# Servis / LLM durum kontrolü
if not _SERVIS_HAZIR:
    st.error(f"Özet servisi yüklenemedi: {_SERVIS_HATA}")
    st.stop()

if not _LLM_HAZIR:
    st.warning(
        "LLM provider (llm/provider.py) bulunamadı veya yüklenemedi. "
        "Özet üretebilmek için LLM yapılandırmasını tamamlayın."
    )

# ---- Yan panel: Uzunluk ayarı ----
with st.sidebar:
    st.subheader("Özet Ayarları")
    uzunluk_secim = st.select_slider(
        "Özet uzunluğu",
        options=["kisa", "orta", "detayli"],
        value="orta",
        format_func=lambda x: {
            "kisa": "Kısa (3 paragraf)",
            "orta": "Orta (5 paragraf)",
            "detayli": "Detaylı (7-10 paragraf)",
        }[x],
    )
    profil = UZUNLUK_PROFILLERI[uzunluk_secim]
    st.caption(f"Yaklaşık {profil['paragraf']}, {profil['aciklama']}.")

    st.divider()
    st.markdown("**Yasal Uyarı**")
    st.info(YASAL_NOT)


# ---- Sekmeler: Manuel Yapıştır / Dataset'ten Seç ----
tab1, tab2 = st.tabs(["✍️ Manuel Yapıştır", "🔎 Dataset'ten Seç"])

karar_metni: str = ""
kaynak_etiketi: str = ""

with tab1:
    st.markdown("Karar metnini aşağıya yapıştırın:")
    manuel_metin = st.text_area(
        "Karar metni",
        height=400,
        placeholder="Mahkeme karar metnini buraya yapıştırın...",
        key="manuel_metin",
        label_visibility="collapsed",
    )
    if manuel_metin and manuel_metin.strip():
        karar_metni = manuel_metin
        kaynak_etiketi = "Manuel giriş"
        st.caption(f"Karakter sayısı: {len(manuel_metin):,}")

with tab2:
    if not _RAG_HAZIR:
        st.warning(f"Dataset servisi (services/rag.py) yüklenemedi: {_RAG_HATA}")
    else:
        st.markdown("Karar ID'si girerek dataset'ten karar yükleyin:")
        col_a, col_b = st.columns([3, 1])
        with col_a:
            decision_id = st.text_input(
                "Karar ID",
                placeholder="örn: 2023/12345",
                key="decision_id_input",
                label_visibility="collapsed",
            )
        with col_b:
            yukle_btn = st.button("Karar Yükle", use_container_width=True)

        if yukle_btn and decision_id and decision_id.strip():
            with st.spinner("Karar yükleniyor..."):
                try:
                    tam_metin = get_full_decision(decision_id.strip())
                    if tam_metin:
                        st.session_state["dataset_karar_metni"] = tam_metin
                        st.session_state["dataset_karar_id"] = decision_id.strip()
                        st.success(f"Karar yüklendi ({len(tam_metin):,} karakter).")
                    else:
                        st.error(f"'{decision_id}' ID'li karar bulunamadı.")
                        st.session_state.pop("dataset_karar_metni", None)
                except Exception as e:
                    st.error(f"Karar yüklenirken hata: {e}")
                    st.session_state.pop("dataset_karar_metni", None)

        if "dataset_karar_metni" in st.session_state:
            karar_metni = st.session_state["dataset_karar_metni"]
            kaynak_etiketi = f"Dataset: {st.session_state.get('dataset_karar_id', '')}"
            with st.expander("Yüklenen karar metnini gör (önizleme)", expanded=False):
                onizleme = karar_metni[:3000] + (
                    "\n\n[... metin kısaltıldı, tamamı özetlemeye gönderilecek ...]"
                    if len(karar_metni) > 3000 else ""
                )
                st.text(onizleme)


st.divider()

# ---- Özet Üret Butonu ----
buton_aktif = bool(karar_metni and karar_metni.strip()) and _LLM_HAZIR
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    ozet_btn = st.button(
        "✨ Özet Üret",
        type="primary",
        use_container_width=True,
        disabled=not buton_aktif,
    )

if not buton_aktif:
    if not karar_metni:
        st.info("Önce bir karar metni yapıştırın veya dataset'ten yükleyin.")
    elif not _LLM_HAZIR:
        st.warning("LLM yapılandırması olmadan özet üretilemez.")


# ---- Özet Üretimi ve Sonuç Gösterimi ----
if ozet_btn and buton_aktif:
    with st.spinner("Özet üretiliyor, lütfen bekleyin..."):
        sonuc = ozet_uret(karar_metni, uzunluk=uzunluk_secim)

    if sonuc.get("hata"):
        st.error(f"Hata: {sonuc['hata']}")
    else:
        st.session_state["son_ozet"] = sonuc
        st.session_state["son_ozet_kaynak"] = kaynak_etiketi


if "son_ozet" in st.session_state:
    sonuc = st.session_state["son_ozet"]
    kaynak = st.session_state.get("son_ozet_kaynak", "")

    st.divider()
    st.subheader("📑 Özet Sonucu")

    # Meta bilgiler
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        st.metric("Kaynak", kaynak or "—")
    with mcol2:
        st.metric("Karakter", f"{sonuc.get('kaynak_char_count', 0):,}")
    with mcol3:
        st.metric("Uzunluk", sonuc.get("uzunluk", "—"))
    with mcol4:
        st.metric("Model", sonuc.get("model", "—"))

    # Özet (markdown)
    st.markdown("### Özet")
    ozet_md = sonuc.get("ozet", "")
    if ozet_md:
        st.markdown(ozet_md)
    else:
        st.info("Özet üretilemedi.")

    # Anahtar noktalar (bullet list)
    anahtar = sonuc.get("anahtar_noktalar", []) or []
    if anahtar:
        st.markdown("### Anahtar Noktalar")
        for nokta in anahtar:
            st.markdown(f"- {nokta}")

    # İlgili kanunlar (tag formatında)
    kanunlar = sonuc.get("ilgili_kanunlar", []) or []
    if kanunlar:
        st.markdown("### İlgili Kanunlar ve İçtihatlar")
        # Etiket benzeri görünüm
        tag_html_parts = []
        for k in kanunlar:
            tag_html_parts.append(
                f"<span style='display:inline-block; padding:4px 10px; margin:3px; "
                f"background:#eef2ff; color:#1e3a8a; border-radius:12px; "
                f"font-size:0.9em; border:1px solid #c7d2fe;'>{k}</span>"
            )
        st.markdown(" ".join(tag_html_parts), unsafe_allow_html=True)

    # Yasal uyarı
    st.divider()
    st.warning(f"⚖️ {sonuc.get('yasal_not', YASAL_NOT)}")

    # Download butonu (.md)
    md_satirlari = []
    md_satirlari.append(f"# Karar Özeti")
    if kaynak:
        md_satirlari.append(f"**Kaynak:** {kaynak}  ")
    md_satirlari.append(f"**Uzunluk:** {sonuc.get('uzunluk', '—')}  ")
    md_satirlari.append(f"**Model:** {sonuc.get('model', '—')}  ")
    md_satirlari.append(f"**Kaynak karakter sayısı:** {sonuc.get('kaynak_char_count', 0):,}")
    md_satirlari.append("")
    md_satirlari.append("## Özet")
    md_satirlari.append(ozet_md or "_(boş)_")
    md_satirlari.append("")
    if anahtar:
        md_satirlari.append("## Anahtar Noktalar")
        for n in anahtar:
            md_satirlari.append(f"- {n}")
        md_satirlari.append("")
    if kanunlar:
        md_satirlari.append("## İlgili Kanunlar ve İçtihatlar")
        for k in kanunlar:
            md_satirlari.append(f"- {k}")
        md_satirlari.append("")
    md_satirlari.append("---")
    md_satirlari.append(f"> {sonuc.get('yasal_not', YASAL_NOT)}")

    md_icerik = "\n".join(md_satirlari)
    dosya_adi = "karar_ozeti.md"
    if kaynak.startswith("Dataset:"):
        guv_id = kaynak.replace("Dataset:", "").strip().replace("/", "_").replace(" ", "_")
        if guv_id:
            dosya_adi = f"karar_ozeti_{guv_id}.md"

    st.download_button(
        label="⬇️ Özeti .md Olarak İndir",
        data=md_icerik.encode("utf-8"),
        file_name=dosya_adi,
        mime="text/markdown",
        use_container_width=True,
    )
