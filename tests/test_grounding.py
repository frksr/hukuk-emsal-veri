"""services/grounding.py — LLM'in uydurduğu emsal atıflarını yakalama.

Bu ürünün en ağır hata türü, avukatın mahkemeye var olmayan bir emsal
sunmasıdır. Prompt'ta "uydurma" talimatı vardı ama programatik kontrol yoktu.
"""
from __future__ import annotations

from services.grounding import (
    dogrula,
    izinli_atiflar,
    metindeki_atiflar,
)


def _emsal(case_no: str, decision_no: str) -> dict:
    """services.rag.search() çıktısı biçiminde tek emsal."""
    return {"chunk_id": "c1", "text": "...", "similarity": 0.8,
            "meta": {"case_no": case_no, "decision_no": decision_no,
                     "court_chamber": "12. HD", "decision_id": "d1"}}


EMSALLER = [_emsal("2023/1234", "2024/5678"), _emsal("2021/99", "2022/100")]


def test_baglamdaki_atif_dogrulanir():
    metin = "Yargıtay 12. HD 2023/1234 E. sayılı kararında belirtildiği üzere..."
    r = dogrula(metin, EMSALLER)
    assert r["temiz"] is True
    assert r["dogrulanmamis"] == []
    assert "2023/1234" in r["dogrulanan"]


def test_uydurma_atif_yakalanir():
    metin = "Yargıtay 12. HD'nin 2019/7777 E. sayılı kararı bu yöndedir."
    r = dogrula(metin, EMSALLER)
    assert r["temiz"] is False
    assert r["dogrulanmamis"] == ["2019/7777"]
    assert "2019/7777" in r["uyari"]


def test_karisik_metinde_yalnizca_uydurma_isaretlenir():
    metin = ("2023/1234 E. kararı ile 2019/7777 E. kararı birlikte "
             "değerlendirildiğinde 2024/5678 K. sonucuna varılır.")
    r = dogrula(metin, EMSALLER)
    assert r["dogrulanmamis"] == ["2019/7777"]
    assert set(r["dogrulanan"]) == {"2023/1234", "2024/5678"}


def test_temizle_politikasi_metinden_cikarir():
    metin = "Bkz. 2019/7777 E. kararı."
    r = dogrula(metin, EMSALLER, politika="temizle")
    assert "2019/7777" not in r["metin"]
    assert "[atıf doğrulanamadı]" in r["metin"]


def test_isaretle_politikasi_metni_bozmaz():
    metin = "Bkz. 2019/7777 E. kararı."
    r = dogrula(metin, EMSALLER)  # varsayılan politika
    assert r["metin"] == metin


def test_kanun_madde_atiflari_emsal_sayilmaz():
    """İİK 67, TBK 117 gibi mevzuat atıfları emsal listesinde aranmaz."""
    metin = "İİK 2004/4949 sayılı Kanun md. 67 uyarınca..."
    r = dogrula(metin, EMSALLER)
    assert r["dogrulanmamis"] == [], r["dogrulanmamis"]


def test_bosluklu_ve_sifir_dolgulu_numaralar_normalize_edilir():
    metin = "2023 / 01234 E."
    r = dogrula(metin, EMSALLER)
    assert r["temiz"] is True


def test_bos_emsal_listesinde_her_atif_supheli():
    metin = "2023/1234 E. kararı uyarınca..."
    r = dogrula(metin, [])
    assert r["dogrulanmamis"] == ["2023/1234"]


def test_atifsiz_metin_temiz():
    r = dogrula("Bu dilekçe genel hukuki bilgiyle hazırlanmıştır.", EMSALLER)
    assert r["temiz"] is True
    assert r["uyari"] is None


def test_ayni_atif_tekrarlanirsa_bir_kez_raporlanir():
    metin = "2019/7777 E. ... yine 2019/7777 E. ... tekrar 2019/7777 E."
    r = dogrula(metin, EMSALLER)
    assert r["dogrulanmamis"] == ["2019/7777"]


def test_izinli_atiflar_duz_sozlukten_de_okur():
    duz = [{"case_no": "2020/1", "decision_no": "2021/2"}]
    assert izinli_atiflar(duz) == {"2020/1", "2021/2"}


def test_gecersiz_yil_atif_sayilmaz():
    """1899/5 gibi anlamsız değerler dosya numarası olarak algılanmamalı."""
    assert metindeki_atiflar("1899/5 böyle bir şey yok") == []


def test_metin_none_veya_bos_ise_patlamaz():
    assert dogrula("", EMSALLER)["temiz"] is True
    assert metindeki_atiflar("") == []
