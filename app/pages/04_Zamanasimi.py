"""
Zamanaşımı Hesaplayıcı — Streamlit Sayfası

Türk hukukunda farklı dava/alacak türleri için zamanaşımı süresini hesaplar.
LLM kullanmaz; deterministik tarih aritmetiği yapar.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from typing import List

import streamlit as st

# Proje kökünü sys.path'e ekle (services modülünü içe aktarmak için)
_PROJE_KOKU = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJE_KOKU not in sys.path:
    sys.path.insert(0, _PROJE_KOKU)

from services.zamanasimi import (  # noqa: E402
    ZAMANASIMI_SURELERI,
    YASAL_UYARI,
    alt_tip_etiketi,
    hesapla,
    kategori_etiketi,
    list_kategoriler,
)


st.set_page_config(page_title="Zamanaşımı Hesaplayıcı", page_icon="⏳", layout="wide")

st.title("⏳ Zamanaşımı Hesaplayıcı")
st.caption(
    "Türk hukukunda bir alacak veya tazminat talebinizin zamanaşımı süresini "
    "yaklaşık olarak hesaplar. LLM kullanmaz, sabit kanun referanslarına dayanır."
)

# Üst kısımda kalıcı yasal uyarı
st.warning(
    "**YAKLAŞIK HESAP — KESİN BİLGİ DEĞİLDİR.**\n\n"
    + YASAL_UYARI
)

# -----------------------------------------------------------------------------
# Form
# -----------------------------------------------------------------------------
kategoriler_map = list_kategoriler()
kategori_kodlari = sorted(kategoriler_map.keys())

st.subheader("1) Dava / Alacak Türü")

col1, col2 = st.columns(2)

with col1:
    kategori = st.selectbox(
        "Kategori",
        options=kategori_kodlari,
        format_func=kategori_etiketi,
        key="zaman_kategori",
        help="Hangi tür talep olduğunu seçin.",
    )

with col2:
    alt_tip_secenekleri = kategoriler_map.get(kategori, [])
    alt_tip = st.selectbox(
        "Alt tip",
        options=alt_tip_secenekleri,
        format_func=lambda a: alt_tip_etiketi(kategori, a),
        key=f"zaman_alttip_{kategori}",  # kategori değişince reset
        help="Seçtiğiniz kategori altındaki spesifik tür.",
    )

# Seçilen tür için temel bilgi
if (kategori, alt_tip) in ZAMANASIMI_SURELERI:
    yil, kanun, aciklama = ZAMANASIMI_SURELERI[(kategori, alt_tip)]
    st.info(
        f"**Seçilen tür:** {alt_tip_etiketi(kategori, alt_tip)}  \n"
        f"**Yasal süre:** {yil} yıl  \n"
        f"**Kanun referansı:** {kanun}  \n"
        f"**Açıklama:** {aciklama}"
    )

st.subheader("2) Olay Tarihi")
bugun = date.today()
olay_tarihi = st.date_input(
    "Olayın gerçekleştiği / alacağın doğduğu tarih",
    value=bugun - timedelta(days=365),
    min_value=date(1950, 1, 1),
    max_value=bugun,
    help=(
        "Zamanaşımı süresi bu tarihten itibaren işlemeye başlar. "
        "Haksız fiilde fiili öğrendiğiniz tarih, alacaklarda muaccel olduğu tarih."
    ),
    key="zaman_olay_tarihi",
)

# -----------------------------------------------------------------------------
# Opsiyonel: Kesilme tarihleri
# -----------------------------------------------------------------------------
st.subheader("3) Zamanaşımını Kesen Olaylar (opsiyonel)")
st.caption(
    "İhtarname, dava açma, icra takibi veya borçlunun ikrarı gibi olaylar "
    "zamanaşımını keser ve süre yeniden başlar (TBK 154). Varsa tarihleri girin."
)

kesilme_var = st.checkbox("Zamanaşımını kesen bir olay yaşandı", value=False, key="zaman_kesilme_var")

kesilme_tarihleri: List[date] = []

if kesilme_var:
    sayi = st.number_input(
        "Kaç adet kesilme olayı vardı?",
        min_value=1,
        max_value=10,
        value=1,
        step=1,
        key="zaman_kesilme_sayi",
    )
    kcols = st.columns(min(int(sayi), 3))
    for i in range(int(sayi)):
        col = kcols[i % len(kcols)]
        with col:
            kt = st.date_input(
                f"Kesilme tarihi #{i + 1}",
                value=bugun,
                min_value=olay_tarihi,
                max_value=bugun,
                key=f"zaman_kesilme_{i}",
                help="İhtarnamenin tebliğ edildiği veya davanın açıldığı tarih.",
            )
            if kt:
                kesilme_tarihleri.append(kt)

# -----------------------------------------------------------------------------
# Hesapla
# -----------------------------------------------------------------------------
st.subheader("4) Sonuç")

if st.button("⏳ Zamanaşımını Hesapla", type="primary", use_container_width=True):
    sonuc = hesapla(
        kategori=kategori,
        alt_tip=alt_tip,
        olay_tarihi=olay_tarihi,
        kesilme_tarihleri=kesilme_tarihleri if kesilme_tarihleri else None,
    )
    st.session_state["zaman_sonuc"] = sonuc

sonuc = st.session_state.get("zaman_sonuc")

if sonuc:
    if sonuc.get("hata"):
        st.error(f"Hata: {sonuc['hata']}")
    else:
        durum = sonuc["durum"]
        kalan = sonuc["kalan_gun"]

        # Durum -> renk + ikon + başlık
        durum_konfig = {
            "guncel": ("✅", "Zamanaşımı GÜNCEL", "green"),
            "yaklasan": ("⚠️", "Zamanaşımı YAKLAŞIYOR", "orange"),
            "kritik": ("🚨", "KRİTİK — Az süre kaldı", "red"),
            "asıldı": ("❌", "Zamanaşımı GEÇMİŞ", "red"),
        }
        ikon, baslik, renk = durum_konfig.get(durum, ("ℹ️", durum, "gray"))

        # Renk barı
        st.markdown(
            f"""
            <div style="background-color:{renk};padding:18px;border-radius:10px;
                        text-align:center;color:white;margin-bottom:14px;">
                <div style="font-size:22px;font-weight:600;">{ikon} {baslik}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Metric'ler
        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            if kalan >= 0:
                st.metric(
                    label="Kalan Gün",
                    value=f"{kalan:,}".replace(",", "."),
                    delta=f"~{kalan // 30} ay" if kalan >= 30 else None,
                )
            else:
                st.metric(
                    label="Geçen Gün",
                    value=f"{abs(kalan):,}".replace(",", "."),
                    delta="zamanaşımı süresi geçmiş",
                    delta_color="inverse",
                )
        with mcol2:
            st.metric(label="Yasal Süre", value=f"{sonuc['zamanasimi_yil']} yıl")
        with mcol3:
            st.metric(label="Bitiş Tarihi", value=sonuc["bitis_tarihi"].strftime("%d.%m.%Y"))

        # Detaylar
        with st.expander("Hesaplama Detayları", expanded=True):
            st.markdown(
                f"""
- **Olay tarihi:** {sonuc['olay_tarihi'].strftime("%d.%m.%Y")}
- **Süre başlangıcı:** {sonuc['baslangic_tarihi'].strftime("%d.%m.%Y")}{" (en son kesilme tarihi)" if sonuc['kesilme_sayisi'] > 0 else ""}
- **Zamanaşımı bitişi:** {sonuc['bitis_tarihi'].strftime("%d.%m.%Y")}
- **Kanun referansı:** `{sonuc['kanun']}`
- **Açıklama:** {sonuc['aciklama']}
- **Kesilme sayısı:** {sonuc['kesilme_sayisi']}
                """.strip()
            )

        # Sonraki adım önerisi
        st.subheader("Sonraki Adım Önerisi")
        if durum == "asıldı":
            st.error(
                "Süre dolmuş görünüyor. Yine de bazı hallerde (kesilme, borçlunun ikrarı, "
                "zamanaşımı def'inin ileri sürülmemesi) hak korunmuş olabilir. **Acilen bir "
                "avukata danışın.**"
            )
        elif durum == "kritik":
            st.error(
                "Süreniz 30 günden az! Şu seçenekleri değerlendirin:\n"
                "1. **Dava açın** — zamanaşımı dava ile kesilir.\n"
                "2. **İcra takibi başlatın** — takip de süreyi keser.\n"
                "3. **İhtarname gönderin** — bazı durumlarda süreyi keser."
            )
        elif durum == "yaklasan":
            st.warning(
                "6 aydan az süreniz var. Hukuki strateji belirlemek ve gerekli "
                "belgeleri toplamak için **şimdi bir avukatla görüşmeniz** önerilir."
            )
        else:
            st.success(
                "Şu an için süre güvende. Yine de delillerinizi (sözleşme, fatura, "
                "yazışmalar) düzenli arşivleyin; ileride dava açmanız gerekirse hazır olun."
            )

        # İhtarname yönlendirme
        st.divider()
        ic1, ic2 = st.columns([3, 1])
        with ic1:
            st.markdown(
                "**Zamanaşımını kesmek için ihtarname göndermek istiyorsanız**, "
                "ihtarname taslağı oluşturma sayfasını kullanabilirsiniz."
            )
        with ic2:
            if st.button("📝 İhtarname Taslağı Oluştur", use_container_width=True):
                st.info(
                    "Soldaki menüden **05_Ihtarname** sayfasına geçin. "
                    "(Streamlit çok sayfalı uygulamada sayfalar arası otomatik geçiş "
                    "için sol menüyü kullanın.)"
                )

        # Uyarılar
        st.subheader("Önemli Uyarılar")
        for uyari in sonuc["uyarilar"]:
            st.warning(uyari)

# Alt kısım — kalıcı yasal not
st.divider()
st.caption(
    "**Yasal Not:** Bu hesaplayıcı eğitim ve ön bilgilendirme amaçlıdır. "
    "Hukuki tavsiye yerine geçmez. Zamanaşımı süresi somut olayın özelliklerine "
    "(kesilme, durma, ikrar, def'inin ileri sürülmesi vb.) göre değişir. "
    "Hak kaybı yaşamamak için mutlaka bir avukata danışın."
)
