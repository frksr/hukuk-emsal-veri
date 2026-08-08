"""scripts/repair_html_kirliligi.py :: model_dogrula + --reembed model kapısı

KAPATILAN BOŞLUK
----------------
`rag_chunks`'taki eski satırların `embedding_model` sütunu NULL — hangi
modelle üretildikleri hiçbir yerde kayıtlı değil. 90.096 chunk'ı FARKLI bir
modelle yeniden embed edersek tek indekste İKİ AYRI SEMANTİK UZAY oluşur:
yeni vektörlerle eski vektörler karşılaştırılamaz hâle gelir ve arama
kalitesi TÜM külliyatta bozulur. Bu SESSİZCE olur — hata fırlamaz, sadece
sonuçlar saçmalar. Geri dönüşü 166.734 chunk'ın tamamını yeniden embed etmek.

Doğrulama: hiç dokunulmamış (embedding_model IS NULL) bir satırın metni ilk
embed'den beri değişmemiştir. Aynı metin şu anki modelle yeniden embed edilip
saklı vektörle kosinüs benzerliği ölçülür. ~1.0 → aynı model.

BU TESTLERİN KORUDUĞU DAVRANIŞLAR
  1. Aynı model → geçer.
  2. Farklı model (düşük benzerlik) → DURDURUR.
  3. Boyut uyuşmazlığı → kesin hata, benzerlik hesaplanmadan durdurur.
  4. --reembed --onayla, doğrulama geçmeden ASLA API'ye gitmez (exit 3).
  5. --dry-run / --onayla'sız koşu doğrulama için bile API çağırmaz.
  6. Bilinçli geçiş yalnızca --model-uyusmazligini-yoksay ile mümkün.
"""
from __future__ import annotations

import math
import sys
import types

import pytest

import scripts.repair_html_kirliligi as R


def _vek(n: int, tohum: float = 1.0) -> list[float]:
    """Deterministik birim-olmayan vektör."""
    return [math.sin(tohum * (i + 1)) for i in range(n)]


def _dondur(v: list[float], aci: float) -> list[float]:
    """İlk iki bileşeni döndürerek benzerliği kontrollü şekilde düşür."""
    out = list(v)
    x, y = out[0], out[1]
    out[0] = x * math.cos(aci) - y * math.sin(aci)
    out[1] = x * math.sin(aci) + y * math.cos(aci)
    return out


class _Sayaci:
    PROVIDER = "google"
    API_MODEL = "models/gemini-embedding-001"
    LOCAL_MODEL = "yok"
    EMBEDDING_DIM = 8

    def __init__(self, uretici):
        self.cagri = 0
        self.gonderilen = 0
        self._uretici = uretici

    def embed_passages(self, texts):
        self.cagri += 1
        self.gonderilen += len(texts)
        return self._uretici(texts)


@pytest.fixture
def ortam(monkeypatch):
    """(saklanan_vektorler, api_uretici) → sahte pg + embeddings kurar."""
    def _kur(saklanan: list[list[float]], uretici, bayat: int = 0):
        satirlar = [
            {"chunk_id": f"c{i:03d}", "document": "uzun karar metni " * 30,
             "embedding": v}
            for i, v in enumerate(saklanan)
        ]

        class _Cur:
            def __enter__(self): return self
            def __exit__(self, *a): return False

            def execute(self, sql, params=None):
                s = " ".join(sql.split())
                if s.startswith("SELECT chunk_id, document, embedding::text"):
                    lim = params[0]
                    self._r = [
                        (r["chunk_id"], r["document"],
                         "[" + ",".join(repr(x) for x in r["embedding"]) + "]")
                        for r in satirlar[:lim]
                    ]
                elif s.startswith("SELECT count(*), COALESCE"):
                    self._r = [(bayat, bayat * 700)]
                elif s.startswith("SELECT chunk_id, document FROM rag_chunks"):
                    self._r = []
                else:
                    self._r = []

            def executemany(self, sql, seq):
                pass

            def fetchall(self): return self._r
            def fetchone(self): return self._r[0] if self._r else None

        class _Conn:
            def cursor(self, name=None): return _Cur()
            def commit(self): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False

        import services
        pgm = types.ModuleType("services.pg")
        pgm.connection = lambda: _Conn()
        monkeypatch.setitem(sys.modules, "services.pg", pgm)
        monkeypatch.setattr(services, "pg", pgm, raising=False)

        sayici = _Sayaci(uretici)
        em = types.ModuleType("services.embeddings")
        for attr in ("PROVIDER", "API_MODEL", "LOCAL_MODEL", "EMBEDDING_DIM"):
            setattr(em, attr, getattr(_Sayaci, attr))
        em.embed_passages = sayici.embed_passages
        monkeypatch.setitem(sys.modules, "services.embeddings", em)
        monkeypatch.setattr(services, "embeddings", em, raising=False)
        return sayici
    return _kur


# ---------------------------------------------------------------------------
# 1. Ölçüm doğru mu
# ---------------------------------------------------------------------------

def test_ayni_model_gecer(ortam):
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    ortam(saklanan, lambda texts: [list(v) for v in saklanan[:len(texts)]])

    sonuc = R.model_dogrula()

    assert sonuc["dogrulandi"] is True
    assert sonuc["ayni_model"] is True
    assert sonuc["en_dusuk_benzerlik"] >= R._AYNI_MODEL_ESIGI


def test_olcek_farki_model_farki_SAYILMAZ(ortam):
    """Kosinüs benzerliği büyüklükten bağımsızdır; aynı yön = aynı model."""
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    ortam(saklanan, lambda texts: [[x * 7.5 for x in v]
                                   for v in saklanan[:len(texts)]])

    assert R.model_dogrula()["ayni_model"] is True


def test_farkli_model_DURDURUR(ortam):
    """Farklı semantik uzay → düşük benzerlik → geçmemeli."""
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    ortam(saklanan, lambda texts: [_dondur(v, 1.2)
                                   for v in saklanan[:len(texts)]])

    sonuc = R.model_dogrula()

    assert sonuc["dogrulandi"] is True
    assert sonuc["ayni_model"] is False


def test_EN_DUSUK_benzerlik_belirleyici(ortam):
    """Bir örnek bile uyuşmuyorsa geçmemeli — ortalama gizlerdi."""
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]

    def uretici(texts):
        out = [list(v) for v in saklanan[:len(texts)]]
        out[-1] = _dondur(out[-1], 1.2)          # yalnızca sonuncusu bozuk
        return out

    ortam(saklanan, uretici)
    assert R.model_dogrula()["ayni_model"] is False


def test_boyut_uyusmazligi_kesin_hata(ortam):
    saklanan = [_vek(8, 1.0)]
    ortam(saklanan, lambda texts: [_vek(16, 1.0) for _ in texts])

    sonuc = R.model_dogrula()

    assert sonuc["dogrulandi"] is False
    assert sonuc["sebep"] == "boyut"
    assert sonuc["saklanan_boyut"] == 8
    assert sonuc["yeni_boyut"] == 16


def test_ornek_yoksa_sessizce_GECMEZ(ortam):
    """Doğrulanamadıysa 'doğrulandı' demek en tehlikeli yalan olurdu."""
    ortam([], lambda texts: [])
    sonuc = R.model_dogrula()
    assert sonuc["dogrulandi"] is False
    assert sonuc["sebep"] == "ornek_yok"


def test_eksik_vektor_donerse_gecmez(ortam):
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    ortam(saklanan, lambda texts: [list(saklanan[0])])   # 3 yerine 1
    sonuc = R.model_dogrula()
    assert sonuc["dogrulandi"] is False
    assert sonuc["sebep"] == "eksik_vektor"


def test_tek_API_istegi_yapar(ortam):
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    sayici = ortam(saklanan, lambda texts: [list(v)
                                            for v in saklanan[:len(texts)]])
    R.model_dogrula()
    assert sayici.cagri == 1
    assert sayici.gonderilen == R._DOGRULAMA_ORNEK


# ---------------------------------------------------------------------------
# 2. --reembed kapısı — asıl para koruması
# ---------------------------------------------------------------------------

def _argv(monkeypatch, *ek):
    monkeypatch.setattr(sys, "argv", ["repair", "--skip-db", *ek])


def test_model_uyusmazsa_reembed_CALISMAZ(ortam, monkeypatch):
    """EN KRİTİK: yanlış modelle 90.096 chunk embed edilmemeli."""
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    sayici = ortam(saklanan,
                   lambda texts: [_dondur(v, 1.2) for v in saklanan[:len(texts)]],
                   bayat=90096)
    cagrildi = []
    monkeypatch.setattr(R, "_yeniden_embed",
                        lambda *a, **k: cagrildi.append("embed") or {})
    _argv(monkeypatch, "--reembed", "--onayla")

    kod = R.main()

    assert kod == 3, "uyuşmazlıkta sıfır olmayan çıkış kodu dönmeli"
    assert cagrildi == [], "MODEL UYUŞMUYORKEN EMBED ÇALIŞTI — para/kalite riski"
    assert sayici.cagri == 1, "yalnızca doğrulama isteği atılmalıydı"


def test_model_uyusuyorsa_reembed_calisir(ortam, monkeypatch):
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    ortam(saklanan, lambda texts: [list(v) for v in saklanan[:len(texts)]],
          bayat=90096)
    cagrildi = []
    monkeypatch.setattr(R, "_yeniden_embed",
                        lambda *a, **k: cagrildi.append("embed") or {})
    _argv(monkeypatch, "--reembed", "--onayla")

    assert R.main() == 0
    assert cagrildi == ["embed"]


def test_yoksay_bayragi_ile_bilincli_gecilir(ortam, monkeypatch):
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    ortam(saklanan,
          lambda texts: [_dondur(v, 1.2) for v in saklanan[:len(texts)]],
          bayat=90096)
    cagrildi = []
    monkeypatch.setattr(R, "_yeniden_embed",
                        lambda *a, **k: cagrildi.append("embed") or {})
    _argv(monkeypatch, "--reembed", "--onayla", "--model-uyusmazligini-yoksay")

    assert R.main() == 0
    assert cagrildi == ["embed"]


def test_onaysiz_reembed_dogrulama_icin_bile_API_CAGIRMAZ(ortam, monkeypatch):
    """Maliyet tahmini koşusu tek kuruş harcamamalı."""
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    sayici = ortam(saklanan, lambda texts: [list(v)
                                            for v in saklanan[:len(texts)]],
                   bayat=90096)
    _argv(monkeypatch, "--reembed")

    R.main()

    assert sayici.cagri == 0, "ONAYSIZ API ÇAĞRISI YAPILDI"


def test_dry_run_API_CAGIRMAZ(ortam, monkeypatch):
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    sayici = ortam(saklanan, lambda texts: [list(v)
                                            for v in saklanan[:len(texts)]],
                   bayat=90096)
    _argv(monkeypatch, "--reembed", "--onayla", "--dry-run")

    R.main()

    assert sayici.cagri == 0, "DRY-RUN'DA API ÇAĞRISI YAPILDI"


def test_model_dogrula_tek_basina_calisir(ortam, monkeypatch):
    """Embed etmeden sadece ölçmek isteyebiliriz."""
    saklanan = [_vek(8, t) for t in (1.0, 2.0, 3.0)]
    sayici = ortam(saklanan, lambda texts: [list(v)
                                            for v in saklanan[:len(texts)]])
    cagrildi = []
    monkeypatch.setattr(R, "_yeniden_embed",
                        lambda *a, **k: cagrildi.append("embed") or {})
    _argv(monkeypatch, "--model-dogrula")

    assert R.main() == 0
    assert sayici.cagri == 1
    assert cagrildi == []
