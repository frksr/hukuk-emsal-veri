"""Emsal-bağlamlı dilekçe üretici servis.

Kullanıcı bir dava durumunu serbest metinle anlatır, sistem:
  1. RAG ile top-k emsal kararı bulur (services.rag.search).
  2. LLM ile bu emsallere atıflı bir dilekçe taslağı üretir.
  3. Kullanılan emsallerin listesi ile birlikte döndürür.

Kullanım:
  from services.dilekce_emsalli import generate_dilekce

  result = generate_dilekce(
      durum="Borçlu çekin karşılıksız çıktığını ileri sürerek itiraz etti...",
      dilekce_turu="itirazin_iptali",
      taraflar={"alacakli": "ABC Ltd. Şti.", "borclu": "XYZ A.Ş."},
      k=5,
  )
  print(result["dilekce_metni"])
  for e in result["kullanilan_emsaller"]:
      print(e["atif_text"])
"""
from __future__ import annotations

from typing import Literal

from services.rag import search
from llm.provider import generate, is_available


DilekceTuru = Literal[
    "itirazin_iptali",
    "ihalenin_feshi",
    "menfi_tespit",
    "tahsilat",
    "genel",
]


DILEKCE_TURU_LABEL = {
    "itirazin_iptali": "İtirazın İptali Davası Dilekçesi",
    "ihalenin_feshi": "İhalenin Feshi Talebi Dilekçesi",
    "menfi_tespit": "Menfi Tespit Davası Dilekçesi",
    "tahsilat": "Alacak / Tahsilat Davası Dilekçesi",
    "genel": "Genel Hukuki Dilekçe",
}


DILEKCE_TURU_HUKUKI_DAYANAK = {
    "itirazin_iptali": (
        "İcra ve İflas Kanunu (İİK) m. 67 vd., 6098 sayılı TBK ile "
        "ilgili özel hükümler ve yerleşik Yargıtay 12. Hukuk Dairesi içtihatları."
    ),
    "ihalenin_feshi": (
        "İİK m. 134 (ihalenin feshi), m. 126 vd. (ihale prosedürü) ve "
        "Yargıtay 12. Hukuk Dairesi'nin yerleşik içtihatları."
    ),
    "menfi_tespit": (
        "İİK m. 72 (menfi tespit ve istirdat davası), 6098 sayılı TBK genel "
        "hükümleri ve ilgili Yargıtay içtihatları."
    ),
    "tahsilat": (
        "6098 sayılı TBK alacak hükümleri, 6102 sayılı TTK (kambiyo senetleri "
        "söz konusu ise) ve ilgili Yargıtay içtihatları."
    ),
    "genel": (
        "İlgili kanun maddeleri ve yerleşik Yargıtay/Danıştay/AYM içtihatları."
    ),
}


SISTEM_PROMPT = """Sen, Türk hukuku alanında uzman, deneyimli bir avukatsın.
Görevin: Kullanıcının anlattığı somut olaya uygun, emsal kararlara atıflı,
mahkemeye sunulabilir nitelikte bir dilekçe taslağı hazırlamak.

KURALLAR:
1. Resmî, ölçülü ve hukuki Türkçe kullan. Slang, samimi dil, emoji KULLANMA.
2. Dilekçe standart başlık-gövde-sonuç-talep yapısında olsun:
   - SAYIN ... MAHKEMESİ'NE
   - DAVACI / DAVALI / KONU / AÇIKLAMALAR / HUKUKİ NEDENLER / DELİLLER / SONUÇ VE İSTEM
3. Sağlanan emsal kararları "AÇIKLAMALAR" bölümünde, mutlaka somut metadata
   (mahkeme + esas no + karar no) ile atıfla. Örnek atıf kalıpları:
     - "Nitekim Yargıtay 12. Hukuk Dairesi'nin 2024/123 E., 2024/456 K. sayılı kararında..."
     - "Danıştay 4. Dairesi'nin 2023/789 E., 2023/1011 K. sayılı içtihadında..."
     - "Avrupa İnsan Hakları Mahkemesi'nin X / Türkiye davasında (Başvuru No: ...)"
4. Emsal kararın metnindeki ilkeyi/ratio decidendi'sini 1-2 cümleyle özetle,
   sonra somut olaya uyarla. Karar metnini KOPYALAMA, gerekçeyi aktarımla yaz.
5. Eğer sağlanan emsal kararın metadata'sı eksikse (esas no yoksa), o emsali
   atıfta GENEL bir ifadeyle (örn. "Yüksek Mahkemenin yerleşik içtihadı") an,
   uydurma esas/karar numarası ÜRETME.
6. Sonunda mutlaka "SONUÇ VE İSTEM" bölümü olsun, talep net ifade edilsin.
7. Dilekçenin sonuna şu uyarıyı EKLEME — uyarı UI tarafında ayrıca gösterilir.
8. Çıktıyı düz metin olarak ver (Markdown başlık/ # gibi işaretler kullanma).
"""


def _emsal_blogu_hazirla(emsaller: list[dict]) -> str:
    """LLM prompt'una verilecek emsal kararların özet bloğunu hazırla."""
    if not emsaller:
        return "(Sağlanan emsal karar yok — genel hukuki bilgiyle dilekçe hazırla.)"

    satirlar: list[str] = []
    for i, e in enumerate(emsaller, start=1):
        meta = e.get("meta") or {}
        mahkeme = (
            meta.get("mahkeme")
            or meta.get("daire")
            or meta.get("kaynak")
            or "Mahkeme bilgisi yok"
        )
        esas = meta.get("esas_no") or meta.get("esas") or "—"
        karar = meta.get("karar_no") or meta.get("karar") or "—"
        tarih = meta.get("karar_tarihi") or meta.get("tarih") or "—"
        karar_id = meta.get("id") or meta.get("decision_id") or e.get("chunk_id", "")
        ozet = (e.get("text") or "").strip().replace("\n", " ")
        if len(ozet) > 900:
            ozet = ozet[:900] + "..."

        satirlar.append(
            f"[EMSAL {i}]\n"
            f"  Mahkeme/Daire: {mahkeme}\n"
            f"  Esas No: {esas}\n"
            f"  Karar No: {karar}\n"
            f"  Tarih: {tarih}\n"
            f"  Karar ID: {karar_id}\n"
            f"  İlgili Bölüm:\n  \"\"\"{ozet}\"\"\""
        )
    return "\n\n".join(satirlar)


def _kullanilan_emsaller_format(emsaller: list[dict]) -> list[dict]:
    """Dönüş yapısı için emsal listesini sadeleştir."""
    out: list[dict] = []
    for e in emsaller:
        meta = e.get("meta") or {}
        mahkeme = (
            meta.get("mahkeme")
            or meta.get("daire")
            or meta.get("kaynak")
            or "Mahkeme bilgisi yok"
        )
        esas = meta.get("esas_no") or meta.get("esas") or ""
        karar = meta.get("karar_no") or meta.get("karar") or ""
        karar_id = (
            meta.get("id")
            or meta.get("decision_id")
            or e.get("chunk_id", "")
        )

        # Atıf cümlesi: Türk hukuki üslubuna uygun.
        if esas and karar:
            atif = f"{mahkeme}'nin {esas} E., {karar} K. sayılı kararı"
        elif esas:
            atif = f"{mahkeme}'nin {esas} E. sayılı kararı"
        else:
            atif = f"{mahkeme}'nin yerleşik içtihadı"

        ilgili = (e.get("text") or "").strip()
        if len(ilgili) > 500:
            ilgili = ilgili[:500] + "..."

        out.append({
            "karar_id": str(karar_id),
            "atif_text": atif,
            "ilgili_bolum": ilgili,
        })
    return out


def _stub_dilekce(
    durum: str,
    dilekce_turu: str,
    taraflar: dict | None,
    emsaller: list[dict],
) -> str:
    """LLM yokken kullanılacak basit şablon — sadece iskelet."""
    taraflar = taraflar or {}
    alacakli = taraflar.get("alacakli", "[ALACAKLI / DAVACI]")
    borclu = taraflar.get("borclu", "[BORÇLU / DAVALI]")
    baslik = DILEKCE_TURU_LABEL.get(dilekce_turu, "Hukuki Dilekçe")
    dayanak = DILEKCE_TURU_HUKUKI_DAYANAK.get(dilekce_turu, "İlgili mevzuat.")

    atiflar = []
    for em in _kullanilan_emsaller_format(emsaller):
        atiflar.append(f"  - {em['atif_text']}")
    atif_blok = "\n".join(atiflar) if atiflar else "  (Emsal bulunamadı)"

    return (
        f"SAYIN ... MAHKEMESİ'NE\n\n"
        f"DAVACI: {alacakli}\n"
        f"DAVALI: {borclu}\n\n"
        f"KONU: {baslik} talebimizi içerir.\n\n"
        f"AÇIKLAMALAR:\n"
        f"[DEMO MODU — LLM API key bulunamadı. Aşağıdaki olay anlatımı ve "
        f"emsallere göre tam dilekçe metni LLM ile üretilecektir.]\n\n"
        f"Somut Olay:\n{durum}\n\n"
        f"İlgili Emsal Kararlar:\n{atif_blok}\n\n"
        f"HUKUKİ NEDENLER: {dayanak}\n\n"
        f"DELİLLER: Her türlü yasal delil.\n\n"
        f"SONUÇ VE İSTEM: Yukarıda arz edilen nedenlerle talebimizin kabulüne "
        f"karar verilmesini saygılarımla arz ve talep ederim.\n"
    )


def generate_dilekce(
    durum: str,
    dilekce_turu: str = "genel",
    taraflar: dict | None = None,
    k: int = 5,
) -> dict:
    """Emsal-bağlamlı dilekçe taslağı üret.

    Args:
        durum: Kullanıcının serbest metinle anlattığı somut olay.
        dilekce_turu: "itirazin_iptali" | "ihalenin_feshi" | "menfi_tespit"
                      | "tahsilat" | "genel"
        taraflar: {"alacakli": "...", "borclu": "..."} (opsiyonel)
        k: RAG için top-k.

    Returns:
        {
            "dilekce_metni": str,
            "kullanilan_emsaller": [
                {"karar_id": str, "atif_text": str, "ilgili_bolum": str}, ...
            ],
            "uyari": str,
        }
    """
    durum = (durum or "").strip()
    if not durum:
        return {
            "dilekce_metni": "",
            "kullanilan_emsaller": [],
            "uyari": "Olay anlatımı (durum) boş — dilekçe üretilemedi.",
        }

    if dilekce_turu not in DILEKCE_TURU_LABEL:
        dilekce_turu = "genel"

    # 1) RAG araması.
    try:
        emsaller = search(durum, k=k)
    except Exception as e:
        emsaller = []
        rag_hatasi = f"RAG araması başarısız: {e}"
    else:
        rag_hatasi = ""

    kullanilan = _kullanilan_emsaller_format(emsaller)

    # 2) LLM kontrolü — yoksa demo modu.
    if not is_available():
        stub = _stub_dilekce(durum, dilekce_turu, taraflar, emsaller)
        uyari = (
            "DEMO MODU: LLM API key bulunamadı (ANTHROPIC_API_KEY veya "
            "GOOGLE_API_KEY). Sadece emsaller listelendi, dilekçe iskeleti "
            "verildi. Tam üretim için .env dosyasına API key ekleyin."
        )
        if rag_hatasi:
            uyari = rag_hatasi + " | " + uyari
        return {
            "dilekce_metni": stub,
            "kullanilan_emsaller": kullanilan,
            "uyari": uyari,
        }

    # 3) Prompt hazırla.
    taraflar = taraflar or {}
    alacakli = (taraflar.get("alacakli") or "").strip() or "[ALACAKLI / DAVACI]"
    borclu = (taraflar.get("borclu") or "").strip() or "[BORÇLU / DAVALI]"
    baslik = DILEKCE_TURU_LABEL.get(dilekce_turu, "Hukuki Dilekçe")
    dayanak = DILEKCE_TURU_HUKUKI_DAYANAK.get(dilekce_turu, "İlgili mevzuat.")
    emsal_blogu = _emsal_blogu_hazirla(emsaller)

    user_prompt = f"""DİLEKÇE TÜRÜ: {baslik} ({dilekce_turu})

TARAFLAR:
  - Davacı / Alacaklı: {alacakli}
  - Davalı / Borçlu : {borclu}

SOMUT OLAY (kullanıcının anlatımı):
\"\"\"
{durum}
\"\"\"

İLGİLİ EMSAL KARARLAR (RAG ile çekildi — atıflarda METADATA'yı kullan):
{emsal_blogu}

HUKUKİ DAYANAK ÖNERİSİ:
{dayanak}

GÖREV:
Yukarıdaki olaya ve emsallere dayanarak, "{baslik}" formatında, mahkemeye
sunulabilir nitelikte bir dilekçe taslağı yaz. Emsal kararları AÇIKLAMALAR
bölümünde mutlaka esas/karar no ile atıfla. Çıktıyı düz metin olarak ver.
"""

    # 4) LLM çağrısı.
    try:
        metin = generate(
            system=SISTEM_PROMPT,
            user=user_prompt,
            max_tokens=2500,
            temperature=0.3,
        )
        uyari = rag_hatasi or ""
    except Exception as e:
        # LLM çağrısı patladı — stub'a dön.
        metin = _stub_dilekce(durum, dilekce_turu, taraflar, emsaller)
        uyari = (
            f"LLM çağrısı başarısız oldu ({e}). Demo iskelet döndürüldü. "
            "API key'i ve provider ayarlarını kontrol edin."
        )

    return {
        "dilekce_metni": metin,
        "kullanilan_emsaller": kullanilan,
        "uyari": uyari,
    }
