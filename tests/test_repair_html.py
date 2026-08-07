"""scripts/repair_html_kirliligi.py — sonlanma (termination) garantisi.

KİLİTLENEN HATA
---------------
İlk sürüm gerçek koşuda `OFFSET 0`'da sabit duruyor, "satırlar temizlendikçe
filtreden düşer" varsayıyordu. Ama iki tür satır ASLA değişmiyor:

  * %20 kuralıyla atlananlar (temizlik metni aşırı kısaltıyorsa)
  * temizlik sonrası metni aynen kalan yanlış pozitifler

Bunlar filtreye takılmaya devam edip aynı partiyi sonsuza dek döndürüyordu.
Cloud Run job'u 1 saat boyunca aynı 500 satırı işleyip durdu.

Çözüm: chunk_id üzerinden keyset sayfalama — imleç her turda kesin ilerler.
"""
from __future__ import annotations

import pytest

from scripts import repair_html_kirliligi as R


class _SahteCursor:
    """rag_chunks'ı taklit eden asgari imleç.

    UPDATE'leri uygular; böylece "temizlenen satır filtreden düşer" davranışı
    da, "hiç değişmeyen satır filtrede kalır" davranışı da gerçekçi olur.
    """

    def __init__(self, store: dict[str, str], sayac: dict[str, int]):
        self.store = store
        self.sayac = sayac
        self._sonuc: list = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @staticmethod
    def _kirli(metin: str) -> bool:
        d = metin.lower()
        return any(x in d for x in ("<html", "<font", "<br>", "<body",
                                    "http-equiv", "&lt;"))

    def execute(self, sql, params=None):
        self.sayac["sorgu"] = self.sayac.get("sorgu", 0) + 1
        if self.sayac["sorgu"] > 500:
            raise AssertionError("SONSUZ DÖNGÜ — sorgu sayısı 500'ü aştı")

        s = " ".join(sql.split())
        if s.startswith("SELECT count(*)"):
            self._sonuc = [(sum(1 for v in self.store.values() if self._kirli(v)),)]
        elif s.startswith("SELECT chunk_id, document"):
            son = (params or {}).get("son", "")
            lim = (params or {}).get("lim", 500)
            uygun = sorted(
                (k, v) for k, v in self.store.items()
                if k > son and self._kirli(v))
            self._sonuc = uygun[:lim]
        elif s.startswith("UPDATE rag_chunks SET document"):
            pass  # executemany üzerinden gelir
        else:
            self._sonuc = []

    def executemany(self, sql, seq):
        if "SET document" in sql:
            # (metin, embedding_model, chunk_id)
            for yeni, _model, chunk_id in seq:
                self.store[chunk_id] = yeni

    def fetchall(self):
        return self._sonuc

    def fetchone(self):
        return self._sonuc[0] if self._sonuc else None

    # Sunucu tarafı imleç davranışı: sonuç üzerinde doğrudan iterasyon
    def __iter__(self):
        return iter(list(self._sonuc))

    itersize = 500


class _SahteConn:
    def __init__(self, store, sayac):
        self.store = store
        self.sayac = sayac

    def cursor(self, name=None):
        return _SahteCursor(self.store, self.sayac)

    def commit(self):
        pass

    def rollback(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def sahte_pg(monkeypatch):
    def _kur(store: dict[str, str]):
        sayac: dict[str, int] = {}

        class _PG:
            @staticmethod
            def connection():
                return _SahteConn(store, sayac)

        import sys
        import types

        import services

        modul = types.ModuleType("services.pg")
        modul.connection = _PG.connection
        # Hem sys.modules hem paket ÖZNİTELİĞİ gerekli: `from services import pg`
        # paket zaten import edilmişse sys.modules'a bakmadan özniteliği alır.
        # (Bu testler tek başına geçip tüm pakette patlıyordu — sebebi buydu.)
        monkeypatch.setitem(sys.modules, "services.pg", modul)
        monkeypatch.setattr(services, "pg", modul, raising=False)
        return sayac

    return _kur


_KIRLI = '<html><body><font face="Verdana">Danıştay 9. Daire kararı metni burada. ' \
         'Esas No : 2023/2318 Karar No : 2025/843 gerekçe uzun uzun devam eder.</font></body></html>'


def test_temizlenebilen_satirlar_islenir_ve_biter(sahte_pg):
    store = {f"c{i:04d}": _KIRLI for i in range(120)}
    sahte_pg(store)

    sonuc = R.onar_chunks(dry_run=False)

    assert sonuc["temizlenen"] == 120
    assert all("<font" not in v for v in store.values())
    assert all("Danıştay 9. Daire" in v for v in store.values())


def test_hic_degismeyen_satirlar_sonsuz_donguye_sokmaz(sahte_pg):
    """ASIL REGRESYON.

    `&lt;` içeren ama temizlenince aynen kalan satırlar filtrede kalmaya devam
    eder. Eski OFFSET-sabit mantığı burada sonsuza dek dönüyordu.
    """
    # Temizlik bunları DEĞİŞTİRMEZ: etiket/entity yok, sadece filtreye takılan
    # bir kelime ("http-equiv") geçiyor. Yanlış pozitif → filtrede kalmaya devam.
    store = {
        f"z{i:04d}": "http-equiv kelimesi gecen duz metin, etiket yok, "
                     "karar gerekcesi uzun uzun devam eder."
        for i in range(30)
    }
    sayac = sahte_pg(store)

    sonuc = R.onar_chunks(dry_run=False)   # patlamamalı

    assert sonuc["temizlenen"] == 0
    assert sayac["sorgu"] < 20, f"gereğinden çok sorgu: {sayac['sorgu']}"


def test_karisik_durum_da_biter(sahte_pg):
    """Temizlenebilenler + hiç değişmeyenler bir arada."""
    store = {f"a{i:04d}": _KIRLI for i in range(60)}
    store.update({
        f"b{i:04d}": "http-equiv kelimesi gecen duz metin, etiket yok, "
                     "karar gerekcesi uzun uzun devam eder."
        for i in range(60)
    })
    sayac = sahte_pg(store)

    sonuc = R.onar_chunks(dry_run=False)

    assert sonuc["temizlenen"] == 60
    assert sayac["sorgu"] < 30


def test_dry_run_hicbir_seyi_degistirmez(sahte_pg):
    store = {f"c{i:04d}": _KIRLI for i in range(40)}
    sahte_pg(store)

    sonuc = R.onar_chunks(dry_run=True)

    assert sonuc["temizlenen"] == 40          # raporlar
    assert all(v == _KIRLI for v in store.values())   # ama yazmaz


def test_asiri_kisalan_metin_atlanir(sahte_pg):
    """Parse hatasıyla karar metni yok edilmesin."""
    # Etiketlerden ibaret: temizlenince neredeyse hiçbir şey kalmaz
    store = {"c0001": '<html><body><font face="Verdana"></font></body></html>'}
    sahte_pg(store)

    sonuc = R.onar_chunks(dry_run=False)

    assert sonuc["atlanan"] == 1
    assert sonuc["temizlenen"] == 0
    assert store["c0001"].startswith("<html")   # dokunulmadı


def test_bos_tabloda_hemen_doner(sahte_pg):
    sayac = sahte_pg({})
    assert R.onar_chunks(dry_run=False)["toplam"] == 0
    assert sayac["sorgu"] == 1                  # yalnızca count sorgusu


def test_sorgu_offset_kullanmiyor():
    """Regresyon kilidi: OFFSET sayfalaması geri gelmesin (O(n²) tarama)."""
    sql = R._kirli_sorgusu().upper()
    assert "OFFSET" not in sql, "OFFSET sayfalaması geri gelmiş — O(n²) tarama."
    assert "CHUNK_ID > %(SON)S" in " ".join(sql.split()), "keyset imleci yok."
    assert "ORDER BY CHUNK_ID" in " ".join(sql.split()), "sıralama yok — imleç bozulur."


def test_sunucu_tarafi_imlec_kullanilmiyor():
    """services/pg.py havuzu autocommit; named cursor DECLARE bir transaction
    ister, autocommit'te anında yok olur ve ilk FETCH patlar. Cloud Run job'u
    tam olarak bu yüzden anında düştü — geri gelmesin."""
    import inspect
    kaynak = inspect.getsource(R.onar_chunks)
    assert "cursor(name=" not in kaynak, (
        "Sunucu tarafı imleç geri gelmiş — autocommit havuzda çalışmaz."
    )


def test_tek_baglanti_kullanilir():
    """Havuz max_size=2; iki bağlantı birden almak kilitlenme riski."""
    import inspect
    kaynak = inspect.getsource(R.onar_chunks)
    assert kaynak.count("pg.connection()") == 1, (
        f"{kaynak.count('pg.connection()')} bağlantı alınıyor — bir tane olmalı."
    )


def test_sorgu_sayisi_dogrusal_artar(sahte_pg):
    """OFFSET'te sorgu maliyeti KARESEL artıyordu. Keyset'te tur sayısı
    satır/parti oranıyla DOĞRUSAL artmalı — 40 kat veri, ~40 kat tur."""
    kucuk = {f"c{i:05d}": _KIRLI for i in range(50)}
    sayac_k = sahte_pg(kucuk)
    R.onar_chunks(dry_run=False)
    sorgu_kucuk = sayac_k["sorgu"]

    buyuk = {f"c{i:05d}": _KIRLI for i in range(2000)}
    sayac_b = sahte_pg(buyuk)
    R.onar_chunks(dry_run=False)

    # 2000/500 = 4 tur + count; 50 satır = 1 tur + count
    assert sayac_b["sorgu"] <= 8, f"beklenenden çok sorgu: {sayac_b['sorgu']}"
    assert sorgu_kucuk <= 3


# ==========================================================================
# MALİYET GÜVENLİKLERİ
# ==========================================================================
# Bu testler paranın korunmasını kilitler. Biri kırılırsa gerçek para riski var.

class _EmbedSayaci:
    """embed_passages çağrılarını sayan sahte sağlayıcı."""

    def __init__(self, hata_versin: bool = False, eksik_donsun: bool = False,
                 hata_baslangici: int | None = None):
        self.cagri = 0
        self.gonderilen = 0
        self.hata_versin = hata_versin
        self.eksik_donsun = eksik_donsun
        #: Bu kadar chunk gönderildikten SONRA hata vermeye başla.
        #: "Koşunun ortasında bakiye bitti" senaryosunu taklit eder.
        self.hata_baslangici = hata_baslangici

    def embed_passages(self, texts):
        if (self.hata_baslangici is not None
                and self.gonderilen >= self.hata_baslangici):
            self.cagri += 1
            raise RuntimeError("429 RESOURCE_EXHAUSTED: kota/bakiye bitti")
        self.cagri += 1
        self.gonderilen += len(texts)
        if self.hata_versin:
            raise RuntimeError("API anahtarı geçersiz")
        n = len(texts) - 1 if self.eksik_donsun else len(texts)
        return [[0.0] * 8 for _ in range(n)]

    PROVIDER = "google"
    API_MODEL = "models/text-embedding-004"
    LOCAL_MODEL = "yok"
    EMBEDDING_DIM = 768


@pytest.fixture
def sahte_embed(monkeypatch):
    def _kur(bayat_adet: int, **kw):
        sayici = _EmbedSayaci(**kw)
        store = {f"e{i:05d}": ("temiz metin " * 20) for i in range(bayat_adet)}
        isaret = {k: R._BAYAT_ISARET for k in store}

        class _Cur:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def execute(self, sql, params=None):
                s2 = " ".join(sql.split())
                if s2.startswith("SELECT count(*), COALESCE"):
                    bayatlar = [k for k, v in isaret.items() if v == R._BAYAT_ISARET]
                    self._r = [(len(bayatlar), sum(len(store[k]) for k in bayatlar))]
                elif s2.startswith("SELECT chunk_id, document FROM rag_chunks WHERE embedding_model"):
                    lim = params[1]
                    ids = sorted(k for k, v in isaret.items() if v == R._BAYAT_ISARET)[:lim]
                    self._r = [(k, store[k]) for k in ids]
                else:
                    self._r = []
            def executemany(self, sql, seq):
                if "SET embedding = " in sql:
                    for _v, model, cid in seq:
                        isaret[cid] = model
            def fetchall(self): return self._r
            def fetchone(self): return self._r[0] if self._r else None

        class _Conn:
            def cursor(self, name=None): return _Cur()
            def commit(self): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False

        import sys, types
        import services
        pgm = types.ModuleType("services.pg"); pgm.connection = lambda: _Conn()
        monkeypatch.setitem(sys.modules, "services.pg", pgm)
        monkeypatch.setattr(services, "pg", pgm, raising=False)
        em = types.ModuleType("services.embeddings")
        for attr in ("PROVIDER", "API_MODEL", "LOCAL_MODEL", "EMBEDDING_DIM"):
            setattr(em, attr, getattr(_EmbedSayaci, attr))
        em.embed_passages = sayici.embed_passages
        monkeypatch.setitem(sys.modules, "services.embeddings", em)
        monkeypatch.setattr(services, "embeddings", em, raising=False)
        return sayici, isaret
    return _kur


def test_onay_yoksa_HICBIR_api_cagrisi_yapilmaz(sahte_embed):
    """EN KRİTİK GÜVENLİK: --onayla olmadan tek kuruş harcanmamalı."""
    sayici, _ = sahte_embed(5000)
    sonuc = R._yeniden_embed(onayla=False, max_embed=None)
    assert sayici.cagri == 0, "ONAYSIZ API ÇAĞRISI YAPILDI — para riski!"
    assert sonuc["embed_edilen"] == 0
    assert sonuc["kalan"] == 5000
    assert sonuc["onay_bekliyor"] is True


def test_max_embed_siniri_asilmaz(sahte_embed):
    sayici, _ = sahte_embed(1000)
    sonuc = R._yeniden_embed(onayla=True, max_embed=100)
    assert sonuc["embed_edilen"] == 100
    assert sayici.gonderilen == 100, f"sınır aşıldı: {sayici.gonderilen}"


def test_ardisik_api_hatasi_durdurur(sahte_embed):
    """Hatalı anahtarla binlerce başarısız istek atılmasın."""
    sayici, _ = sahte_embed(10000, hata_versin=True)
    R._yeniden_embed(onayla=True, max_embed=None)
    assert sayici.cagri <= R._MAX_ARDISIK_HATA, (
        f"{sayici.cagri} başarısız istek atıldı — fren tutmadı."
    )


def test_eksik_vektor_donerse_yazilmaz(sahte_embed):
    """Eşleşme kayması yanlış chunk'a yanlış vektör yazar — durmalı."""
    sayici, isaret = sahte_embed(200, eksik_donsun=True)
    sonuc = R._yeniden_embed(onayla=True, max_embed=None)
    assert sonuc["embed_edilen"] == 0
    assert all(v == R._BAYAT_ISARET for v in isaret.values())


def test_devam_ettirilebilir(sahte_embed):
    """Yarıda kesilirse ikinci koşu KALDIĞI YERDEN devam etmeli."""
    sayici, isaret = sahte_embed(300)
    R._yeniden_embed(onayla=True, max_embed=100)
    assert sum(1 for v in isaret.values() if v == R._BAYAT_ISARET) == 200

    R._yeniden_embed(onayla=True, max_embed=None)
    assert sum(1 for v in isaret.values() if v == R._BAYAT_ISARET) == 0
    assert sayici.gonderilen == 300, "aynı chunk iki kez embed edildi (çifte ödeme)"


def test_bayat_yoksa_api_cagrilmaz(sahte_embed):
    sayici, _ = sahte_embed(0)
    assert R._yeniden_embed(onayla=True, max_embed=None)["embed_edilen"] == 0
    assert sayici.cagri == 0


def test_temizlik_bayat_isareti_koyar(sahte_pg):
    """Embed aşamasının satırları bulabilmesi buna bağlı."""
    import inspect
    kaynak = inspect.getsource(R._yaz)
    assert "embedding_model = %s" in kaynak
    assert "_BAYAT_ISARET" in kaynak


def test_max_rows_siniri_uygulanir(sahte_pg):
    """Ölçüm modu: N satırdan fazlasına dokunmamalı."""
    store = {f"c{i:05d}": _KIRLI for i in range(3000)}
    sahte_pg(store)
    sonuc = R.onar_chunks(dry_run=False, max_rows=1000)
    # Parti sınırında durur → tam kat olmayabilir ama 1000'i az aşar, 3000 olmaz
    assert 1000 <= sonuc["incelenen"] < 1600, sonuc["incelenen"]
    assert sonuc["incelenen"] < 3000


def test_max_rows_yoksa_hepsi_islenir(sahte_pg):
    store = {f"c{i:05d}": _KIRLI for i in range(1200)}
    sahte_pg(store)
    assert R.onar_chunks(dry_run=False)["incelenen"] == 1200


def test_bakiye_ORTADA_biterse_kaldigi_yerden_devam_eder(sahte_embed):
    """KULLANICI SENARYOSU: koşunun ortasında API bakiyesi bitiyor.

    Beklenen davranış:
      1. O ana kadar embed edilenler KALICI (parti parti commit'leniyor).
      2. Geri kalanlar BAYAT işaretli KALIYOR — iş listesi DB'de tutuluyor.
      3. Bakiye yüklenip aynı komut çalıştırılınca BAŞTAN başlamıyor.
      4. Hiçbir chunk İKİ KEZ gönderilmiyor → çifte ödeme yok.
    """
    sayici, isaret = sahte_embed(300, hata_baslangici=128)   # 2 parti sonra kes

    R._yeniden_embed(onayla=True, max_embed=None)

    # 1) İlk iki parti kalıcı
    tamamlanan = sum(1 for v in isaret.values() if v != R._BAYAT_ISARET)
    assert tamamlanan == 128, f"commit edilen parti sayısı beklenmedik: {tamamlanan}"
    # 2) Kalanlar iş listesinde duruyor
    assert sum(1 for v in isaret.values() if v == R._BAYAT_ISARET) == 172
    # Fren tuttu: başarısız istek sayısı sınırlı
    assert sayici.cagri <= 2 + R._MAX_ARDISIK_HATA

    # 3) Bakiye yüklendi → ikinci koşu
    sayici.hata_baslangici = None
    R._yeniden_embed(onayla=True, max_embed=None)

    assert sum(1 for v in isaret.values() if v == R._BAYAT_ISARET) == 0
    # 4) Toplam gönderim = chunk sayısı; tek bir chunk bile iki kez gitmedi
    assert sayici.gonderilen == 300, (
        f"{sayici.gonderilen} chunk gönderildi ama 300 chunk var — ÇİFTE ÖDEME")


def test_kesinti_sonrasi_yeniden_embed_MALIYETI_dusurur(sahte_embed):
    """Kesintiden sonraki koşunun maliyet tahmini KALAN'ı göstermeli;
    baştan başlıyormuş gibi tüm külliyatı değil."""
    sayici, isaret = sahte_embed(300, hata_baslangici=64)
    R._yeniden_embed(onayla=True, max_embed=None)

    sayici.hata_baslangici = None
    sonuc = R._yeniden_embed(onayla=False, max_embed=None)
    assert sonuc["kalan"] == 236, "kalan iş sayısı yanlış raporlanıyor"
