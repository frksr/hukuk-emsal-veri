"""PII sızıntı testi — dış API'lere giden HİÇBİR payload'da kişisel veri olmamalı.

Garanti: UYAP belgeleri ve sorgular dış embedding API'sine (Google) ve LLM'e
yalnızca anonimleştirilmiş halde gider. Bu test, httpx.post'u mock'layarak
GİDEN payload'ları yakalar ve örnek belgede geçen TCKN/isim/IBAN/telefonun
hiçbirinde bulunmadığını doğrular. Test kırmızıysa KVKK taahhüdü ihlaldedir —
merge ETMEYİN.
"""
from __future__ import annotations
import json
from unittest.mock import patch, MagicMock

import pytest

from services.pii_redaction import (
    redact, unredact, unredact_safe, redact_for_embedding, RedactionMap,
)

# Örnek UYAP belgesi — bilinen PII değerleriyle
ORNEK_BELGE = """
T.C. İSTANBUL 12. ASLİYE HUKUK MAHKEMESİ
Dosya No: 2024/123 E.

Davacı: Ahmet Yılmaz (TCKN: 12345678901)
Vekili: Av. Elif Kaya
Davalı: Mehmet Demir
Adres: Cumhuriyet Mahallesi Gül Sokak No: 12 Daire: 3 Kadıköy/İstanbul
Telefon: 0532 111 22 33
IBAN: TR12 0006 4000 0011 2345 6789 01
E-posta: ahmet.yilmaz@example.com

Davacı vekili, müvekkilinin alacağının tahsili için Yargıtay 12. HD 2021/456
sayılı emsal kararına dayanmıştır.
"""

PII_DEGERLERI = [
    "12345678901",
    "Ahmet Yılmaz",
    "Elif Kaya",
    "Mehmet Demir",
    "0532 111 22 33",
    "TR12 0006 4000 0011 2345 6789 01",
    "ahmet.yilmaz@example.com",
    "Cumhuriyet Mahallesi",
]


def _pii_yok(metin: str, kaynak: str):
    """Verilen metinde bilinen PII değerlerinden hiçbiri geçmemeli."""
    for deger in PII_DEGERLERI:
        assert deger not in metin, f"PII SIZINTISI ({kaynak}): '{deger}' bulundu!"


# ---------------------------------------------------------------------------
# Katman 1: redact_for_embedding tek başına PII bırakmamalı
# ---------------------------------------------------------------------------

def test_redact_for_embedding_pii_birakmaz():
    anonim = redact_for_embedding(ORNEK_BELGE)
    _pii_yok(anonim, "redact_for_embedding")
    # Jenerik etiketler yerinde olmalı, rastgele hex placeholder OLMAMALI
    assert "[TCKN]" in anonim
    assert "[KİŞİ]" in anonim
    assert "<PERSON_" not in anonim


def test_redact_for_embedding_atiflari_bozmaz():
    """Yargı atıfları ("12 HD") plaka sanılıp maskelenmemeli (kalite)."""
    anonim = redact_for_embedding("Yargıtay 12 HD 2021 tarihli kararı emsaldir.")
    assert "12 HD 2021" in anonim


# ---------------------------------------------------------------------------
# Katman 2: tenant_rag üzerinden dış embedding API'sine giden payload temiz mi?
# ---------------------------------------------------------------------------

def test_index_document_dis_apiye_pii_gondermez(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    yakalanan: list[str] = []

    def sahte_post(url, json=None, timeout=None):  # noqa: A002
        yakalanan.append(__import__("json").dumps(json, ensure_ascii=False))
        n = len(json.get("requests", [])) if json else 0
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"embeddings": [{"values": [0.1] * 768}] * n}
        resp.raise_for_status = MagicMock()
        return resp

    # DB yazımını da mock'la — test DB istemiyor
    sahte_conn = MagicMock()
    sahte_cm = MagicMock()
    sahte_cm.__enter__ = MagicMock(return_value=sahte_conn)
    sahte_cm.__exit__ = MagicMock(return_value=False)

    import services.embeddings as emb
    monkeypatch.setattr(emb, "PROVIDER", "google")

    with patch("httpx.post", side_effect=sahte_post), \
         patch("services.pg.connection", return_value=sahte_cm):
        from services.tenant_rag import index_document
        n = index_document(
            "12345678-1234-5678-1234-567812345678",
            "87654321-4321-8765-4321-876543218765",
            ORNEK_BELGE * 3,  # birden çok chunk üret
            metadata={"title": "dava dosyası"},
        )

    assert n > 0
    assert yakalanan, "Embedding API'sine hiç istek gitmedi — test düzeneği bozuk."
    for payload in yakalanan:
        _pii_yok(payload, "embedding API payload")


def test_search_tenant_sorguyu_anonim_embedler(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    yakalanan: list[str] = []

    def sahte_post(url, json=None, timeout=None):  # noqa: A002
        yakalanan.append(__import__("json").dumps(json, ensure_ascii=False))
        n = len(json.get("requests", [])) if json else 1
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"embeddings": [{"values": [0.1] * 768}] * n}
        resp.raise_for_status = MagicMock()
        return resp

    sahte_cur = MagicMock()
    sahte_cur.fetchall.return_value = []
    sahte_cur.description = [("chunk_id",), ("document_id",), ("chunk_index",),
                             ("document",), ("meta",), ("similarity",)]
    sahte_cur_cm = MagicMock()
    sahte_cur_cm.__enter__ = MagicMock(return_value=sahte_cur)
    sahte_cur_cm.__exit__ = MagicMock(return_value=False)
    sahte_conn = MagicMock()
    sahte_conn.cursor.return_value = sahte_cur_cm
    sahte_conn_cm = MagicMock()
    sahte_conn_cm.__enter__ = MagicMock(return_value=sahte_conn)
    sahte_conn_cm.__exit__ = MagicMock(return_value=False)

    import services.embeddings as emb
    monkeypatch.setattr(emb, "PROVIDER", "google")
    # Cache'i atla — sorgu benzersiz olsun
    sorgu = "Davacı Ahmet Yılmaz (TCKN 12345678901) dosyasında zamanaşımı var mı?"

    with patch("httpx.post", side_effect=sahte_post), \
         patch("services.pg.connection", return_value=sahte_conn_cm):
        from services.tenant_rag import search_tenant
        search_tenant("12345678-1234-5678-1234-567812345678", sorgu, k=3)

    assert yakalanan, "Embedding API'sine hiç istek gitmedi."
    for payload in yakalanan:
        _pii_yok(payload, "query embedding payload")


# ---------------------------------------------------------------------------
# Katman 3: unredact dayanıklılığı — kullanıcıya placeholder sızmamalı
# ---------------------------------------------------------------------------

def test_unredact_roundtrip():
    masked, mapping = redact(ORNEK_BELGE)
    _pii_yok(masked, "redact çıktısı")
    geri = unredact(masked, mapping)
    assert "Ahmet Yılmaz" in geri
    assert "12345678901" in geri


def test_unredact_safe_bozuk_placeholder_toparlar():
    masked, mapping = redact("Davacı Ahmet Yılmaz alacak talebinde bulundu.")
    ph = next(iter(mapping.forward))
    # LLM'in placeholder'ı kalınlaştırdığı senaryo: <**PERSON_xx**>
    etiket, hexid = ph.strip("<>").rsplit("_", 1)
    bozuk = f"Karar gereği <**{etiket}_{hexid}**> lehine hükmedildi."
    sonuc = unredact_safe(bozuk, mapping)
    assert "Ahmet Yılmaz" in sonuc
    assert "PERSON_" not in sonuc


def test_unredact_safe_cozulemyen_sizdirmaz():
    mapping = RedactionMap()
    mapping.get_or_create("PERSON", "Ahmet Yılmaz")
    # Haritada OLMAYAN bir placeholder (LLM uydurdu / harita kayboldu)
    metin = "Sonuç: <PERSON_deadbeef> kazandı."
    sonuc = unredact_safe(metin, mapping)
    assert "<PERSON_deadbeef>" not in sonuc
    assert "[gizlenmiş bilgi]" in sonuc
