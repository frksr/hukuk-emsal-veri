"""KVKK Uyum Kontrol Listesi — Streamlit sayfası.

Sektör + işlenen veri türleri seçilince KVKK uyumluluğu için checklist
üretir. Bazı maddeler statik (kanun referanslı), bazıları LLM ile sektöre
özel olarak üretilir. Kullanıcı checkbox'larla maddeleri işaretleyerek
gerçek zamanlı bir uyum skoru görür.

Çalıştır:
  streamlit run app/streamlit_app.py --server.fileWatcherType none
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.kvkk import (  # noqa: E402
    SEKTOR_ETIKETLERI,
    VERI_TURU_ETIKETLERI,
    YASAL_UYARI,
    checklist_uret,
    kategori_etiketi,
    maddeleri_kategoriye_grupla,
    sektor_etiketi,
    to_docx_bytes,
    to_markdown,
    to_pdf_bytes,
    uyum_skoru_hesapla,
    veri_turu_etiketi,
)
from llm.provider import status as llm_status  # noqa: E402


st.set_page_config(
    page_title="KVKK Uyum Kontrol Listesi",
    page_icon="🔒",
    layout="wide",
)


# --------------------------------------------------------------- Sidebar
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
            st.warning(
                "LLM sağlayıcı API key'i yok. Sektöre özel ek maddeler "
                "üretilemez; yalnızca statik checklist gösterilir."
            )
        else:
            st.success("LLM hazır — sektörel ek maddeler üretilebilir.")
    except Exception as e:
        st.warning(f"LLM durumu okunamadı: {e}")

    st.divider()
    st.caption(
        "Bu sayfa, KVKK uyum sürecinde bir başlangıç haritası sunar. "
        "Profesyonel KVKK danışmanlığının yerine geçmez."
    )


# --------------------------------------------------------------- Header
st.title("🔒 KVKK Uyum Kontrol Listesi")
st.write(
    "Sektörünüzü ve işlediğiniz veri türlerini seçin; size özel "
    "bir KVKK uyum checklist'i üretilsin. Maddeleri işaretledikçe "
    "uyum skorunuz canlı olarak güncellenir."
)

st.warning(f"**Yasal Uyarı:** {YASAL_UYARI}")


# --------------------------------------------------------------- Form
with st.form("kvkk_form", clear_on_submit=False):
    col_a, col_b, col_c = st.columns([1, 1, 1])

    with col_a:
        sektor = st.selectbox(
            "Sektör",
            options=list(SEKTOR_ETIKETLERI.keys()),
            format_func=lambda k: SEKTOR_ETIKETLERI.get(k, k),
            index=0,
        )

    with col_b:
        veri_turleri = st.multiselect(
            "İşlenen Veri Türleri",
            options=list(VERI_TURU_ETIKETLERI.keys()),
            default=["kisisel", "musteri"],
            format_func=lambda k: VERI_TURU_ETIKETLERI.get(k, k),
        )

    with col_c:
        sirket_buyuklugu = st.selectbox(
            "Şirket Büyüklüğü",
            options=["mikro", "kucuk", "orta", "buyuk", "kurumsal"],
            format_func=lambda k: {
                "mikro": "Mikro (< 10 kişi)",
                "kucuk": "Küçük (10-49)",
                "orta": "Orta (50-249)",
                "buyuk": "Büyük (250-999)",
                "kurumsal": "Kurumsal (1000+)",
            }.get(k, k),
            index=1,
        )

    llm_ek = st.checkbox(
        "LLM ile sektöre özel ek maddeler üret",
        value=True,
        help="Kapatırsanız yalnızca statik (kanun referanslı) maddeler gösterilir.",
    )

    submitted = st.form_submit_button("Checklist Üret", type="primary")


# --------------------------------------------------------------- Process
if submitted:
    if not veri_turleri:
        st.error("En az bir veri türü seçmelisiniz.")
        st.stop()

    with st.spinner("KVKK uyum checklist'i üretiliyor..."):
        try:
            sonuc = checklist_uret(
                sektor=sektor,
                veri_turleri=veri_turleri,
                llm_ek=llm_ek,
            )
        except Exception as e:
            st.error(f"Üretim sırasında hata: {e}")
            st.stop()

    # Session'a yaz: kullanıcı checkbox'ları sayfa rerun'ları arasında korunsun
    st.session_state["kvkk_sonuc"] = sonuc
    st.session_state["kvkk_sirket_buyuklugu"] = sirket_buyuklugu
    # Yeni üretimde tamamlananları sıfırla
    st.session_state["kvkk_tamamlananlar"] = set()


# --------------------------------------------------------------- Render results
sonuc = st.session_state.get("kvkk_sonuc")

if not sonuc:
    st.info("Form'u doldurup **Checklist Üret** butonuna basın.")
    st.stop()


maddeler = sonuc.get("maddeler", []) or []
tamam_set: set = st.session_state.get("kvkk_tamamlananlar", set())

# --- Üst panel: özet bilgi + Uyum Skoru gauge -----------------------------
st.divider()

ust_left, ust_right = st.columns([3, 2])

with ust_left:
    st.subheader("📋 Genel Bakış")
    st.markdown(
        f"**Sektör:** {sonuc.get('sektor_label','—')}  \n"
        f"**Veri türleri:** "
        f"{', '.join(veri_turu_etiketi(v) for v in sonuc.get('veri_turleri', [])) or '—'}  \n"
        f"**Şirket büyüklüğü:** "
        f"{st.session_state.get('kvkk_sirket_buyuklugu','—')}  \n"
        f"**Toplam madde:** {len(maddeler)}  \n"
        f"**Tahmin referans skor:** {sonuc.get('tahmin_uyum_skoru', 0)}/100  \n"
        f"**LLM ek üretimi:** "
        f"{'✓ kullanıldı' if sonuc.get('llm_kullanildi') else '✗ kullanılmadı'}"
    )
    ozet = sonuc.get("ozet", "")
    if ozet:
        st.caption(ozet)

with ust_right:
    skor = uyum_skoru_hesapla(maddeler, list(tamam_set))
    try:
        import plotly.graph_objects as go

        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=skor,
                number={"suffix": " / 100"},
                title={"text": "Uyum Skoru"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#1f77b4"},
                    "steps": [
                        {"range": [0, 40], "color": "#f8d7da"},
                        {"range": [40, 70], "color": "#fff3cd"},
                        {"range": [70, 100], "color": "#d4edda"},
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 3},
                        "thickness": 0.8,
                        "value": 70,
                    },
                },
            )
        )
        fig.update_layout(height=260, margin=dict(t=40, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.metric("Uyum Skoru", f"{skor} / 100")
        st.progress(skor / 100.0)


# --- Kategoriye göre grupla ve checkbox'lı listele -----------------------
st.divider()
st.subheader("✅ Maddeler (Kategoriye Göre)")

gruplu = maddeleri_kategoriye_grupla(maddeler)

# Kategori önceliklerini grup içinde sırala (yuksek -> orta -> dusuk)
oncelik_sirasi = {"yuksek": 0, "orta": 1, "dusuk": 2}
oncelik_etiketi = {"yuksek": "🔴 YÜKSEK", "orta": "🟡 ORTA", "dusuk": "🟢 DÜŞÜK"}

# Her kategori için expander
yeni_tamam_set: set = set()
for kategori, items in gruplu.items():
    items_sorted = sorted(
        items, key=lambda x: oncelik_sirasi.get(str(x.get("oncelik", "orta")), 1)
    )
    tamamlanmis_sayi = sum(1 for it in items_sorted if int(it["no"]) in tamam_set)
    baslik = (
        f"{kategori_etiketi(kategori)}  "
        f"({tamamlanmis_sayi}/{len(items_sorted)} tamamlandı)"
    )
    with st.expander(baslik, expanded=tamamlanmis_sayi < len(items_sorted)):
        for m in items_sorted:
            no = int(m.get("no", 0))
            oncelik = str(m.get("oncelik", "orta"))
            etiket = (
                f"**#{no}**  {oncelik_etiketi.get(oncelik, oncelik.upper())}  "
                f"— {m.get('madde','')}"
            )
            key = f"kvkk_md_{no}"
            isaretli = st.checkbox(
                etiket,
                value=(no in tamam_set),
                key=key,
            )
            if isaretli:
                yeni_tamam_set.add(no)
            not_metni = str(m.get("sektorel_not", "")).strip()
            if not_metni:
                st.caption(f"📌 Sektörel not: {not_metni}")

# Checkbox state'inden güncelle ve rerun (skor canlı güncellensin)
if yeni_tamam_set != tamam_set:
    st.session_state["kvkk_tamamlananlar"] = yeni_tamam_set
    st.rerun()


# --- Download butonları ----------------------------------------------------
st.divider()
st.subheader("⬇️ İndirme")

dl_col1, dl_col2, dl_col3 = st.columns(3)

tamam_list = sorted(st.session_state.get("kvkk_tamamlananlar", set()))

with dl_col1:
    md_text = to_markdown(sonuc, tamam_list)
    st.download_button(
        label="Markdown (.md)",
        data=md_text.encode("utf-8"),
        file_name=f"kvkk_checklist_{sonuc.get('sektor','genel')}.md",
        mime="text/markdown",
        use_container_width=True,
    )

with dl_col2:
    try:
        docx_bytes = to_docx_bytes(sonuc, tamam_list)
        st.download_button(
            label="Word (.docx)",
            data=docx_bytes,
            file_name=f"kvkk_checklist_{sonuc.get('sektor','genel')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f".docx üretilemedi: {e}")

with dl_col3:
    try:
        pdf_bytes = to_pdf_bytes(sonuc, tamam_list)
        st.download_button(
            label="PDF (.pdf)",
            data=pdf_bytes,
            file_name=f"kvkk_checklist_{sonuc.get('sektor','genel')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f".pdf üretilemedi: {e}")


# --- Alt yasal uyarı -------------------------------------------------------
st.divider()
st.caption(
    "ℹ️ " + sonuc.get("yasal_uyari", YASAL_UYARI)
)
