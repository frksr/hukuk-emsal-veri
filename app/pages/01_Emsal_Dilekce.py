"""Emsal-Bağlamlı Dilekçe Üretici — Streamlit sayfası.

Çalıştır:
  streamlit run app/streamlit_app.py --server.fileWatcherType none
(Bu dosya çoklu-sayfalı Streamlit yapısı içinde otomatik yüklenir.)
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.dilekce_emsalli import (  # noqa: E402
    generate_dilekce,
    DILEKCE_TURU_LABEL,
)
from llm.provider import status as llm_status  # noqa: E402


st.set_page_config(
    page_title="Emsal-Bağlamlı Dilekçe",
    page_icon="📝",
    layout="wide",
)


# ---------------------------------------------------------------- Sidebar
with st.sidebar:
    st.header("LLM Sağlayıcı Durumu")
    try:
        s = llm_status()
        default = s.get("default", "—")
        anth_ok = s.get("anthropic", False)
        gem_ok = s.get("gemini", False)

        st.caption(f"Varsayılan: **{default}**")
        st.write(f"- Anthropic: {'✓ hazır' if anth_ok else '✗ key yok'}")
        st.write(f"- Gemini: {'✓ hazır' if gem_ok else '✗ key yok'}")

        if not (anth_ok or gem_ok):
            st.error(
                "Hiçbir LLM sağlayıcısı için API key bulunamadı. "
                "Proje kökündeki `.env` dosyasına `ANTHROPIC_API_KEY` "
                "veya `GOOGLE_API_KEY` ekleyin. Demo modunda yalnız "
                "emsaller listelenir."
            )
        else:
            st.success("LLM hazır — tam dilekçe üretilebilir.")
    except Exception as e:
        st.warning(f"LLM durumu okunamadı: {e}")

    st.divider()
    st.caption(
        "Bu araç bir AI taslak üretici. Hukuki sorumluluk için "
        "bir avukat tarafından incelenmesi gereklidir."
    )


# ---------------------------------------------------------------- Header
st.title("📝 Emsal-Bağlamlı Dilekçe Üretici")
st.write(
    "Davanızı anlatın; sistem ilgili emsal kararları bulup, atıflı bir "
    "dilekçe taslağı üretir."
)

st.warning(
    "**Yasal Uyarı:** Bu çıktı bir **AI taslağıdır**, hukuki danışmanlık "
    "yerine geçmez. Mahkemeye sunmadan önce mutlaka bir avukat tarafından "
    "incelenmelidir."
)


# ---------------------------------------------------------------- Form
with st.form("dilekce_form", clear_on_submit=False):
    col_a, col_b = st.columns([1, 1])

    with col_a:
        dilekce_turu_keys = list(DILEKCE_TURU_LABEL.keys())
        dilekce_turu = st.selectbox(
            "Dilekçe Türü",
            options=dilekce_turu_keys,
            format_func=lambda k: DILEKCE_TURU_LABEL.get(k, k),
            index=0,
        )
        k = st.slider("Kaç emsal karar kullanılsın?", 3, 10, 5)

    with col_b:
        alacakli = st.text_input(
            "Davacı / Alacaklı",
            placeholder="Ör. ABC Ticaret Ltd. Şti.",
        )
        borclu = st.text_input(
            "Davalı / Borçlu",
            placeholder="Ör. XYZ Sanayi A.Ş.",
        )

    durum = st.text_area(
        "Olay Anlatımı (Somut Durum)",
        height=220,
        placeholder=(
            "Örnek: Müvekkilim alacaklı olduğu çek bedelini tahsil için "
            "icra takibi başlatmıştır. Borçlu, çekin karşılıksız çıktığını "
            "ileri sürerek itiraz etmiş, takibi durdurmuştur. İtirazın "
            "haksız olduğu görüşündeyiz..."
        ),
    )

    submitted = st.form_submit_button("Dilekçe Üret", type="primary")


# ---------------------------------------------------------------- Process
if submitted:
    if not durum.strip():
        st.error("Olay anlatımı boş olamaz.")
        st.stop()

    taraflar = {
        "alacakli": alacakli.strip(),
        "borclu": borclu.strip(),
    }

    with st.spinner("Emsaller aranıyor ve dilekçe üretiliyor..."):
        try:
            result = generate_dilekce(
                durum=durum.strip(),
                dilekce_turu=dilekce_turu,
                taraflar=taraflar,
                k=k,
            )
        except Exception as e:
            st.error(f"Üretim sırasında hata: {e}")
            st.stop()

    uyari = result.get("uyari", "")
    if uyari:
        st.info(uyari)

    # ----------------------------------------------------- Two-column layout
    left, right = st.columns([3, 2])

    with left:
        st.subheader("📄 Dilekçe Taslağı")
        dilekce_metni = result.get("dilekce_metni", "")
        st.text_area(
            "Dilekçe Metni",
            value=dilekce_metni,
            height=600,
            disabled=True,
            label_visibility="collapsed",
        )

        # İndir butonu.
        dosya_adi = f"dilekce_{dilekce_turu}.txt"
        st.download_button(
            label="⬇️ Dilekçeyi .txt olarak indir",
            data=dilekce_metni.encode("utf-8"),
            file_name=dosya_adi,
            mime="text/plain",
        )

        st.caption(
            "Hatırlatma: Bu metin bir AI taslağıdır; bir avukat incelemesi "
            "gerekir."
        )

    with right:
        st.subheader("📚 Kullanılan Emsaller")
        emsaller = result.get("kullanilan_emsaller", [])
        if not emsaller:
            st.warning("Emsal karar bulunamadı.")
        else:
            for i, em in enumerate(emsaller, start=1):
                with st.expander(f"Emsal {i}: {em.get('atif_text', '—')}"):
                    karar_id = em.get("karar_id", "")
                    if karar_id:
                        st.caption(f"Karar ID: `{karar_id}`")
                    bolum = em.get("ilgili_bolum", "")
                    if bolum:
                        st.write(bolum)
                    else:
                        st.write("_(İlgili bölüm boş)_")
