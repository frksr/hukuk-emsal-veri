"""Ortak Pydantic şemaları — request/response type safety."""
from __future__ import annotations
from decimal import Decimal
from datetime import date
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class APIResponse(BaseModel):
    """Tüm endpoint'lerin ortak zarfı."""
    model_config = ConfigDict(extra="allow")
    ok: bool = True
    data: Any = None
    error: str | None = None
    message: str | None = None


# ---- Arama (RAG) ----
class AramaIstegi(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    k: int = Field(5, ge=1, le=20)
    source: str | None = None
    court_chamber: str | None = None


class EmsalKarar(BaseModel):
    chunk_id: str
    text: str
    similarity: float
    decision_id: str | None = None
    source: str | None = None
    court_chamber: str | None = None
    case_no: str | None = None
    decision_no: str | None = None
    decision_date: str | None = None
    topic_tags: str | None = None
    source_url: str | None = None


# ---- Dilekçe ----
class DilekceIstegi(BaseModel):
    durum: str = Field(..., min_length=10, max_length=4000)
    dilekce_turu: str = "genel"
    taraflar: dict[str, str] | None = None
    k: int = Field(5, ge=3, le=10)
    # Dropdown'daki 5 sabit türe girmeyen davalar için: kullanıcının serbest
    # yazdığı konu ("Boşanma Davası", "Kira Tespiti" vb.) — LLM bunu KONU
    # başlığı ve gerekçe üretiminde kullanır; dilekce_turu yine de "genel"
    # (veya en yakın tür) olarak gönderilmelidir.
    ozel_konu: str | None = Field(default=None, max_length=200)


# ---- Karar Özet ----
class OzetIstegi(BaseModel):
    karar_metni: str = Field(..., min_length=100)
    uzunluk: str = "orta"  # kisa | orta | detayli


class OzetIstegiID(BaseModel):
    decision_id: str
    uzunluk: str = "orta"


# ---- Faiz ----
class FaizIstegi(BaseModel):
    anapara: Decimal
    temerrut_tarihi: date
    vade_tarihi: date | None = None
    faiz_turu: str = "yasal"


# ---- Zamanaşımı ----
class ZamanasimiIstegi(BaseModel):
    kategori: str
    alt_tip: str
    olay_tarihi: date
    kesilme_tarihleri: list[date] | None = None


# ---- İhtarname ----
class IhtarnameIstegi(BaseModel):
    tur: str
    taraflar: dict[str, str]
    alacak_detay: dict[str, Any]
    ek_talepler: list[str] | None = None


# ---- Trend ----
class TrendFiltre(BaseModel):
    konu_filtresi: str | None = None
    kaynak: str | None = None
    daire: str | None = None
    yil_baslangic: int | None = None
    yil_bitis: int | None = None


# ---- Karşı Argüman ----
class KarsiArgumentIstegi(BaseModel):
    kendi_tezi: str = Field(..., min_length=10, max_length=3000)
    dava_turu: str | None = None
    k: int = Field(5, ge=3, le=10)


# ---- KVKK ----
class KVKKIstegi(BaseModel):
    sektor: str
    veri_turleri: list[str]
    sirket_buyuklugu: str = "kucuk"
    llm_ek: bool = True


# ---- Sözleşme ----
class SozlesmeIstegi(BaseModel):
    sozlesme_turu: str = "genel"
