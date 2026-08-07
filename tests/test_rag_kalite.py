"""services/rag.py — benzerlik eşiği, çeşitlilik ve hibrit birleştirme.

DB'siz test edilir: `search()`'ün SQL'den sonraki kalite katmanları
(_sonuclari_hazirla / _rrf_birlestir) doğrudan sınanır.

Kilitlenen regresyon: eski `search()` her zaman tam k sonuç döndürüyordu ve
"alakasız" diye bir kavram yoktu — iş hukuku sorusuna icra kararı "emsal"
olarak dönüyor, bu da dilekçe/karşı argüman üzerinden kullanıcıya ulaşıyordu.
"""
from __future__ import annotations

import pytest

from services import rag


def _ham(chunk_id: str, decision_id: str, similarity: float | None) -> dict:
    """SQL'den dönen ham satır biçimi."""
    return {
        "chunk_id": chunk_id, "decision_id": decision_id, "chunk_index": 0,
        "document": f"metin-{chunk_id}", "source": "yargitay",
        "court_chamber": "12. HD", "case_no": "2023/1", "decision_no": "2024/2",
        "decision_date": "2024-01-01", "topic_tags": "icra",
        "source_url": "https://x", "similarity": similarity,
    }


# --------------------------------------------------------------------------
# Eşik
# --------------------------------------------------------------------------

def test_esigin_altindaki_sonuclar_elenir():
    rows = [_ham("c1", "d1", 0.80), _ham("c2", "d2", 0.20), _ham("c3", "d3", 0.10)]
    out = rag._sonuclari_hazirla(rows, k=5, esik=0.35, per_decision=2)
    assert [r["chunk_id"] for r in out] == ["c1"]


def test_hicbiri_esigi_gecmezse_bos_doner():
    """En önemli davranış: 'k sonuç garantisi' YOK."""
    rows = [_ham("c1", "d1", 0.10), _ham("c2", "d2", 0.05)]
    assert rag._sonuclari_hazirla(rows, k=5, esik=0.35, per_decision=2) == []


def test_esik_sifirsa_hicbir_sey_elenmez():
    rows = [_ham("c1", "d1", 0.01)]
    assert len(rag._sonuclari_hazirla(rows, k=5, esik=0, per_decision=2)) == 1


def test_tam_metin_eslesmesi_esikten_muaf():
    """Vektör benzerliği olmayan (yalnız tam metinden gelen) kayıt elenmez —
    'İİK 67/1' gibi tam eşleşmeler semantik skoru düşük olsa da doğrudur."""
    row = _ham("c1", "d1", None)
    row["rank_kaynak"] = "tam_metin"
    out = rag._sonuclari_hazirla([row], k=5, esik=0.9, per_decision=2)
    assert len(out) == 1
    assert out[0]["rank_kaynak"] == "tam_metin"


# --------------------------------------------------------------------------
# Çeşitlilik
# --------------------------------------------------------------------------

def test_ayni_karardan_sinirli_sayida_parca_gelir():
    """Örtüşmeli chunk'lar yüzünden top-5'in tamamı tek karar olabiliyordu."""
    rows = [_ham(f"c{i}", "AYNI_KARAR", 0.9 - i * 0.01) for i in range(5)]
    out = rag._sonuclari_hazirla(rows, k=5, esik=0.3, per_decision=2)
    assert len(out) == 2


def test_cesitlilik_farkli_kararlara_yer_acar():
    rows = [
        _ham("a1", "d1", 0.90), _ham("a2", "d1", 0.89), _ham("a3", "d1", 0.88),
        _ham("b1", "d2", 0.70), _ham("c1", "d3", 0.60),
    ]
    out = rag._sonuclari_hazirla(rows, k=4, esik=0.3, per_decision=2)
    kararlar = [r["meta"]["decision_id"] for r in out]
    assert kararlar.count("d1") == 2
    assert "d2" in kararlar and "d3" in kararlar


def test_per_decision_sifirsa_sinir_uygulanmaz():
    rows = [_ham(f"c{i}", "d1", 0.9) for i in range(4)]
    assert len(rag._sonuclari_hazirla(rows, k=10, esik=0.3, per_decision=0)) == 4


def test_k_siniri_uygulanir():
    rows = [_ham(f"c{i}", f"d{i}", 0.9) for i in range(10)]
    assert len(rag._sonuclari_hazirla(rows, k=3, esik=0.3, per_decision=2)) == 3


def test_sonuclar_benzerlige_gore_sirali():
    rows = [_ham("c1", "d1", 0.5), _ham("c2", "d2", 0.9), _ham("c3", "d3", 0.7)]
    out = rag._sonuclari_hazirla(rows, k=5, esik=0.3, per_decision=2)
    skorlar = [r["similarity"] for r in out]
    assert skorlar == sorted(skorlar, reverse=True)


# --------------------------------------------------------------------------
# Hibrit birleştirme (RRF)
# --------------------------------------------------------------------------

def test_rrf_her_iki_listede_olani_one_alir():
    vektor = [_ham("a", "d1", 0.7), _ham("b", "d2", 0.75)]
    metin = [_ham("b", "d2", 0.9)]          # 'b' iki listede de var
    birlesik = rag._rrf_birlestir(vektor, metin)
    assert birlesik[0]["chunk_id"] == "b"
    assert birlesik[0]["rank_kaynak"] == "hibrit"


def test_rrf_yalniz_tam_metinden_geleni_isaretler():
    birlesik = rag._rrf_birlestir([_ham("a", "d1", 0.7)], [_ham("z", "d9", 0.5)])
    z = next(r for r in birlesik if r["chunk_id"] == "z")
    assert z["rank_kaynak"] == "tam_metin"
    assert z["similarity"] is None      # vektör benzerliği bilinmiyor


def test_rrf_bos_metin_listesiyle_calisir():
    birlesik = rag._rrf_birlestir([_ham("a", "d1", 0.7)], [])
    assert len(birlesik) == 1 and birlesik[0]["rank_kaynak"] == "vektor"


# --------------------------------------------------------------------------
# tsquery güvenliği
# --------------------------------------------------------------------------

@pytest.mark.parametrize("girdi", [
    "icra takibine itiraz",
    "2023/1234 E. sayılı karar",
    "İİK 67/1 & | ! ( ) : *",       # to_tsquery operatörleri
    "'; DROP TABLE rag_chunks; --",  # enjeksiyon denemesi
])
def test_tsquery_guvenli_uretilir(girdi):
    q = rag._tsquery_hazirla(girdi)
    # Yalnızca token'lar ve ' | ' ayırıcısı kalmalı
    assert not any(c in q for c in "&!():*';-")
    if q:
        assert all(p.strip() for p in q.split("|"))


def test_tsquery_bos_girdide_bos_doner():
    assert rag._tsquery_hazirla("") == ""
    assert rag._tsquery_hazirla("a") == ""   # tek harfli token atılır


def test_context_esigi_arama_esiginden_kati():
    """LLM'e giden emsallerin eşiği, listelenen sonuçlarınkinden yüksek olmalı."""
    assert rag.CONTEXT_MIN_SIMILARITY > rag.MIN_SIMILARITY


# --------------------------------------------------------------------------
# Türkçe karakter katlaması (f_unaccent) — indeks/kod uyumu
# --------------------------------------------------------------------------

class _SahteCursor:
    def __init__(self, unaccent_var: bool):
        self._v = unaccent_var

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **kw):
        pass

    def fetchone(self):
        return (self._v,)


class _SahteConn:
    def __init__(self, unaccent_var: bool):
        self._v = unaccent_var

    def cursor(self):
        return _SahteCursor(self._v)


def _sql(unaccent_var: bool, monkeypatch=None) -> str:
    rag._UNACCENT_DESTEGI = None          # süreç-içi cache'i sıfırla
    return rag._metin_sql_uret(_SahteConn(unaccent_var), "chunk_id", "WHERE 1=1")


def test_unaccent_varsa_katlamali_ifade_kullanilir():
    sql = _sql(True)
    assert sql.count("f_unaccent(document)") >= 2      # ts_rank + @@
    assert "f_unaccent(%(tsq)s)" in sql


def test_unaccent_yoksa_katlamasiz_ifadeye_duser():
    """Migration'dan ÖNCE dağıtılırsa sistem çalışmaya devam etmeli."""
    sql = _sql(False)
    assert "f_unaccent" not in sql
    assert "to_tsvector('simple', document)" in sql


def test_belge_ve_sorgu_ifadeleri_ayni_katlamayi_kullanir():
    """İkisi ayrışırsa eşleşme sessizce bozulur."""
    for durum in (True, False):
        sql = _sql(durum)
        belge_katlamali = "f_unaccent(document)" in sql
        sorgu_katlamali = "f_unaccent(%(tsq)s)" in sql
        assert belge_katlamali == sorgu_katlamali


def test_ifade_indeksle_birebir_ayni_yazilir():
    """Planner'ın indeksi kullanabilmesi için ifade, migration'daki ile
    KARAKTER KARAKTER aynı olmalı. Ayrışırsa sorgu sessizce Seq Scan'e düşer
    ve tam metin araması yavaşlar — hata vermez, o yüzden test şart."""
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent
    migration = (kok / "infra" / "db" / "33_rag_unaccent.sql").read_text(encoding="utf-8")
    assert "to_tsvector('simple', f_unaccent(document))" in migration, \
        "33_rag_unaccent.sql'deki indeks ifadesi değişmiş — rag.py ile hizalayın."

    m32 = (kok / "infra" / "db" / "32_rag_hybrid_search.sql").read_text(encoding="utf-8")
    assert "to_tsvector('simple', document)" in m32, \
        "32_rag_hybrid_search.sql'deki indeks ifadesi değişmiş — rag.py ile hizalayın."

    assert "to_tsvector('simple', f_unaccent(document))" in _sql(True)
    assert "to_tsvector('simple', document)" in _sql(False)


def test_env_ile_kapatilabilir(monkeypatch):
    """RAG_UNACCENT=0 → indeksi geri almak gerekirse kodu değiştirmeden dön."""
    monkeypatch.setattr(rag, "_UNACCENT_ACIK", False)
    rag._UNACCENT_DESTEGI = None
    assert rag._unaccent_kullanilabilir(_SahteConn(True)) is False
