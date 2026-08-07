"""scripts/repair_html_kirliligi.py :: bayat_isaretle_parquetten

KAPATILAN BOŞLUK
----------------
İlk onarım koşuları `rag_chunks.document` içindeki HTML'i temizliyor ama
`embedding_model` sütununa BAYAT işareti YAZMIYORDU (o güvenlik sonradan
eklendi). Sonuç: metni temiz, vektörü HTML çöpünden üretilmiş ~21.500 satır
oluştu. DB'ye bakarak bunlar hiç kirli olmamış satırlardan ayırt edilemez —
`--reembed` onları sessizce atlar ve arama kalitesi bozuk kalır.

Kanıt parquet'te: parquet henüz onarılmadığı için kirli metni hâlâ içeriyor.
Kirli KARAR kimlikleri oradan çıkarılıp o kararların TÜM chunk'ları
işaretlenir.

BU TESTLERİN KORUDUĞU DAVRANIŞLAR
  1. Kirli karar kimlikleri parquet'ten doğru çıkarılır (raw_text dahil).
  2. Yalnızca `embedding_model IS NULL` satırlar işaretlenir — düzgün embed
     edilmiş satırların imzası EZİLMEZ.
  3. Zaten BAYAT olanlar iki kez sayılmaz.
  4. Temiz kararlara DOKUNULMAZ (gereksiz API maliyeti doğmaz).
  5. --dry-run tek bir UPDATE bile yapmaz.
  6. Parquet yoksa sessizce "başarılı" dönmez, patlar.
  7. Parquet zaten onarılmışsa (kanıt yok) uyarı basar ve 0 döner.
"""
from __future__ import annotations

import sys
import types

import pytest

import scripts.repair_html_kirliligi as R

pd = pytest.importorskip("pandas")
pytest.importorskip("duckdb")


_KIRLI = ('<html><body><font face="Verdana">Danıştay 9. Daire. Esas No : '
          '2023/2318 Karar No : 2025/843 gerekçe uzun uzun devam eder ve '
          'burada biter.</font></body></html>')
_TEMIZ = ('Danıştay 9. Daire. Esas No : 2023/2318 Karar No : 2025/843 '
          'gerekçe uzun uzun devam eder ve burada biter.')


# ---------------------------------------------------------------------------
# Sahte DB — decision_id + embedding_model taşır
# ---------------------------------------------------------------------------

class _Cur:
    def __init__(self, satirlar, gunluk):
        self.satirlar = satirlar          # list[dict]
        self.gunluk = gunluk
        self._sonuc = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT count(*)"):
            idler = params[0]
            n = sum(1 for r in self.satirlar
                    if r["decision_id"] in idler and r["embedding_model"] is None)
            self._sonuc = [(n,)]
        elif s.startswith("UPDATE rag_chunks SET embedding_model"):
            isaret, idler = params
            n = 0
            for r in self.satirlar:
                if r["decision_id"] in idler and r["embedding_model"] is None:
                    r["embedding_model"] = isaret
                    n += 1
            self.rowcount = n
            self.gunluk.append(("update", len(idler), n))
        else:                                     # pragma: no cover
            raise AssertionError(f"beklenmeyen SQL: {s[:80]}")

    def fetchone(self):
        return self._sonuc[0] if self._sonuc else None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self, satirlar, gunluk):
        self.satirlar = satirlar
        self.gunluk = gunluk

    def cursor(self):
        return _Cur(self.satirlar, self.gunluk)

    def commit(self):
        self.gunluk.append(("commit",))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def sahte_pg(monkeypatch):
    def _kur(satirlar):
        gunluk: list[tuple] = []
        import services
        modul = types.ModuleType("services.pg")
        modul.connection = lambda: _Conn(satirlar, gunluk)
        monkeypatch.setitem(sys.modules, "services.pg", modul)
        monkeypatch.setattr(services, "pg", modul, raising=False)
        return gunluk
    return _kur


@pytest.fixture
def parquet_kur(tmp_path, monkeypatch):
    def _kur(kayitlar):
        yol = tmp_path / "all_decisions.parquet"
        pd.DataFrame(kayitlar).to_parquet(yol, index=False)
        monkeypatch.setenv("DECISIONS_PARQUET", str(yol))
        return yol
    return _kur


def _chunklar(*ciftler):
    """(decision_id, adet, embedding_model) → satır listesi."""
    out = []
    for did, adet, model in ciftler:
        for i in range(adet):
            out.append({"chunk_id": f"{did}_c{i:03d}",
                        "decision_id": did, "embedding_model": model})
    return out


# ---------------------------------------------------------------------------
# 1. Kimlik çıkarımı
# ---------------------------------------------------------------------------

def test_kirli_kimlikler_parquetten_cikar(parquet_kur):
    parquet_kur([
        {"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI},
        {"id": "k2", "cleaned_text": _TEMIZ, "raw_text": _TEMIZ},
        {"id": "k3", "cleaned_text": _KIRLI, "raw_text": _TEMIZ},
    ])
    assert sorted(R.kirli_karar_idleri()) == ["k1", "k3"]


def test_raw_text_kirliyse_de_yakalanir(parquet_kur):
    """cleaned_text temizlenmiş ama raw_text kirli kalmış olabilir."""
    parquet_kur([{"id": "k1", "cleaned_text": _TEMIZ, "raw_text": _KIRLI}])
    assert R.kirli_karar_idleri() == ["k1"]


def test_ayni_karar_iki_kez_sayilmaz(parquet_kur):
    parquet_kur([{"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI}])
    assert R.kirli_karar_idleri() == ["k1"]


def test_parquet_yoksa_patlar(tmp_path, monkeypatch):
    """Sessizce 'kirli yok' dönmek, boşluğu kapattı sanmamıza yol açardı."""
    monkeypatch.setenv("DECISIONS_PARQUET", str(tmp_path / "yok.parquet"))
    with pytest.raises(FileNotFoundError):
        R.kirli_karar_idleri()


def test_beklenen_kolonlar_yoksa_patlar(tmp_path, monkeypatch):
    yol = tmp_path / "p.parquet"
    pd.DataFrame([{"baska": 1}]).to_parquet(yol, index=False)
    monkeypatch.setenv("DECISIONS_PARQUET", str(yol))
    with pytest.raises(ValueError):
        R.kirli_karar_idleri()


# ---------------------------------------------------------------------------
# 2. İşaretleme
# ---------------------------------------------------------------------------

def test_isaretsiz_temizlenenler_bayat_yapilir(parquet_kur, sahte_pg):
    parquet_kur([
        {"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI},
        {"id": "k2", "cleaned_text": _TEMIZ, "raw_text": _TEMIZ},
    ])
    satirlar = _chunklar(("k1", 3, None), ("k2", 2, None))
    sahte_pg(satirlar)

    sonuc = R.bayat_isaretle_parquetten(dry_run=False)

    assert sonuc == {"kirli_karar": 1, "isaretlenen": 3}
    k1 = [r for r in satirlar if r["decision_id"] == "k1"]
    assert all(r["embedding_model"] == R._BAYAT_ISARET for r in k1)


def test_temiz_kararlara_DOKUNULMAZ(parquet_kur, sahte_pg):
    """Gereksiz işaret = gereksiz yeniden-embed = boşa ödenen API parası."""
    parquet_kur([
        {"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI},
        {"id": "k2", "cleaned_text": _TEMIZ, "raw_text": _TEMIZ},
    ])
    satirlar = _chunklar(("k1", 1, None), ("k2", 5, None))
    sahte_pg(satirlar)

    R.bayat_isaretle_parquetten(dry_run=False)

    k2 = [r for r in satirlar if r["decision_id"] == "k2"]
    assert all(r["embedding_model"] is None for r in k2)


def test_gercek_model_imzasi_EZILMEZ(parquet_kur, sahte_pg):
    """Onarımdan SONRA düzgün embed edilmiş satır yeniden embed edilmemeli."""
    parquet_kur([{"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI}])
    satirlar = _chunklar(("k1", 2, None))
    satirlar += [{"chunk_id": "k1_c009", "decision_id": "k1",
                  "embedding_model": "google:text-embedding-004:768"}]
    sahte_pg(satirlar)

    sonuc = R.bayat_isaretle_parquetten(dry_run=False)

    assert sonuc["isaretlenen"] == 2
    imzali = next(r for r in satirlar if r["chunk_id"] == "k1_c009")
    assert imzali["embedding_model"] == "google:text-embedding-004:768"


def test_zaten_bayat_olan_tekrar_sayilmaz(parquet_kur, sahte_pg):
    """49.631 zaten işaretli; rapor yalnızca YENİ bulunanları göstermeli."""
    parquet_kur([{"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI}])
    satirlar = _chunklar(("k1", 2, R._BAYAT_ISARET), ("k1", 0, None))
    satirlar += [{"chunk_id": "k1_c090", "decision_id": "k1",
                  "embedding_model": None}]
    sahte_pg(satirlar)

    sonuc = R.bayat_isaretle_parquetten(dry_run=False)

    assert sonuc["isaretlenen"] == 1


def test_partili_calisir(parquet_kur, sahte_pg, monkeypatch):
    """Binlerce kimlik tek UPDATE'e sığmaz; parti parti gitmeli."""
    monkeypatch.setattr(R, "_ISARET_PARTI", 2)
    parquet_kur([{"id": f"k{i}", "cleaned_text": _KIRLI, "raw_text": _KIRLI}
                 for i in range(5)])
    satirlar = _chunklar(*[(f"k{i}", 1, None) for i in range(5)])
    gunluk = sahte_pg(satirlar)

    sonuc = R.bayat_isaretle_parquetten(dry_run=False)

    assert sonuc["isaretlenen"] == 5
    assert len([g for g in gunluk if g[0] == "update"]) == 3   # 2+2+1
    assert len([g for g in gunluk if g[0] == "commit"]) == 3   # her parti commit


# ---------------------------------------------------------------------------
# 3. Güvenlikler
# ---------------------------------------------------------------------------

def test_dry_run_hicbir_sey_yazmaz(parquet_kur, sahte_pg):
    parquet_kur([{"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI}])
    satirlar = _chunklar(("k1", 4, None))
    gunluk = sahte_pg(satirlar)

    sonuc = R.bayat_isaretle_parquetten(dry_run=True)

    assert sonuc["isaretlenecek"] == 4
    assert sonuc["isaretlenen"] == 0
    assert not [g for g in gunluk if g[0] == "update"]
    assert all(r["embedding_model"] is None for r in satirlar)


def test_parquet_zaten_onarilmissa_uyarir(parquet_kur, sahte_pg, capsys):
    """Kanıt yoksa 'iş bitti' sanmamalıyız."""
    parquet_kur([{"id": "k1", "cleaned_text": _TEMIZ, "raw_text": _TEMIZ}])
    sahte_pg(_chunklar(("k1", 3, None)))

    sonuc = R.bayat_isaretle_parquetten(dry_run=False)

    assert sonuc == {"kirli_karar": 0, "isaretlenen": 0}
    assert "yedek" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# 4. CLI kablolaması — sıra kritik
# ---------------------------------------------------------------------------

def test_bayat_tara_parquet_onarimindan_ONCE_calisir(monkeypatch, parquet_kur):
    """onar_parquet kanıtı siler; tarama ondan önce olmalı."""
    parquet_kur([{"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI}])
    sira: list[str] = []
    monkeypatch.setattr(R, "onar_chunks", lambda *a, **k: {"temizlenen": 0})
    monkeypatch.setattr(R, "bayat_isaretle_parquetten",
                        lambda dry_run: sira.append("bayat") or {})
    monkeypatch.setattr(R, "onar_parquet",
                        lambda dry_run: sira.append("parquet") or {})
    monkeypatch.setattr(sys, "argv",
                        ["repair", "--skip-db", "--bayat-tara", "--parquet"])
    R.main()
    assert sira == ["bayat", "parquet"]

    sira.clear()
    monkeypatch.setattr(sys, "argv", ["repair", "--bayat-tara", "--parquet"])
    R.main()
    assert sira == ["bayat", "parquet"]


def test_skip_db_bayat_taramayi_ATLAMAZ(monkeypatch, parquet_kur):
    """Asıl kullanım: temizlik bitti, 4,5 saatlik taramayı tekrarlamadan
    yalnızca işaretle. --skip-db bunu engellememeli."""
    parquet_kur([{"id": "k1", "cleaned_text": _KIRLI, "raw_text": _KIRLI}])
    cagrildi: list[str] = []
    monkeypatch.setattr(R, "onar_chunks",
                        lambda *a, **k: cagrildi.append("tarama") or {})
    monkeypatch.setattr(R, "bayat_isaretle_parquetten",
                        lambda dry_run: cagrildi.append("bayat") or {})
    monkeypatch.setattr(sys, "argv", ["repair", "--skip-db", "--bayat-tara"])
    R.main()
    assert cagrildi == ["bayat"]        # pahalı tarama HİÇ çalışmadı


def test_bayat_tara_verilmezse_parquet_onarimi_uyarir(monkeypatch, capsys):
    monkeypatch.setattr(R, "onar_chunks", lambda *a, **k: {"temizlenen": 0})
    monkeypatch.setattr(R, "onar_parquet", lambda dry_run: {})
    monkeypatch.setattr(sys, "argv", ["repair", "--parquet"])
    R.main()
    assert "--bayat-tara verilmedi" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 5. DuckDB ön süzmesi ÜST KÜME olmalı — eleme yapmamalı
# ---------------------------------------------------------------------------

def test_yalnizca_entity_kirliligi_de_yakalanir(parquet_kur):
    """Kaçışlı HTML'de '<' karakteri HİÇ olmayabilir; ön süzme '&' ile de
    eşleşmezse bu kararlar sessizce atlanırdı."""
    parquet_kur([{"id": "k1",
                  "cleaned_text": "Karar metni &lt;font face=Verdana&gt; devam",
                  "raw_text": "Karar metni"}])
    assert R.kirli_karar_idleri() == ["k1"]


def test_matematiksel_kucuktur_isareti_kirli_SAYILMAZ(parquet_kur):
    """'<' içeren her metin HTML değil — yanlış işaretleme boşa API parası."""
    parquet_kur([{"id": "k1",
                  "cleaned_text": "Faiz oranı < %25 olarak belirlenmiştir.",
                  "raw_text": "Tutar 5 & 6 arası."}])
    assert R.kirli_karar_idleri() == []


def test_null_metin_cokmez(parquet_kur):
    parquet_kur([{"id": "k1", "cleaned_text": None, "raw_text": _KIRLI},
                 {"id": "k2", "cleaned_text": None, "raw_text": None}])
    assert R.kirli_karar_idleri() == ["k1"]
