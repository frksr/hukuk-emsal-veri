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

import logging
from typing import Literal

from services.rag import search
from llm.provider import generate, is_available

log = logging.getLogger(__name__)

# Kullanıcıya gösterilecek genel mesaj — API key/env gibi iç mimari detayları
# ASLA son kullanıcıya sızdırılmaz. Gerçek sebep yalnızca sunucu loguna yazılır
# (ops/Sentry görür), kullanıcı bunu görmemeli — onu ilgilendirmiyor.
_KULLANICI_DEMO_MESAJI = (
    "Yapay Zeka üretimi şu anda geçici olarak kullanılamıyor; aşağıda emsal "
    "kararlar ve dilekçe iskeleti sunuldu. Lütfen birkaç dakika sonra tekrar "
    "deneyin."
)


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
        # services.rag.search() 'court_chamber'/'case_no'/'decision_no'/
        # 'decision_date' döner (pgvector şeması); eski Türkçe anahtarlar
        # (mahkeme/daire/esas_no/karar_no) yalnızca geriye dönük uyumluluk için
        # fallback'te tutulur — bkz. api/routers/arama.py aynı desen.
        mahkeme = (
            meta.get("court_chamber")
            or meta.get("mahkeme")
            or meta.get("daire")
            or meta.get("source")
            or meta.get("kaynak")
            or "Mahkeme bilgisi yok"
        )
        esas = meta.get("case_no") or meta.get("esas_no") or meta.get("esas") or "—"
        karar = meta.get("decision_no") or meta.get("karar_no") or meta.get("karar") or "—"
        tarih = meta.get("decision_date") or meta.get("karar_tarihi") or meta.get("tarih") or "—"
        karar_id = meta.get("decision_id") or meta.get("id") or e.get("chunk_id", "")
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
        mahkeme_bilinmiyor = not (
            meta.get("court_chamber") or meta.get("mahkeme")
            or meta.get("daire") or meta.get("source") or meta.get("kaynak")
        )
        mahkeme = (
            meta.get("court_chamber")
            or meta.get("mahkeme")
            or meta.get("daire")
            or meta.get("source")
            or meta.get("kaynak")
            or "Mahkeme bilgisi yok"
        )
        esas = meta.get("case_no") or meta.get("esas_no") or meta.get("esas") or ""
        karar = meta.get("decision_no") or meta.get("karar_no") or meta.get("karar") or ""
        karar_id = (
            meta.get("decision_id")
            or meta.get("id")
            or e.get("chunk_id", "")
        )

        # Atıf cümlesi: Türk hukuki üslubuna uygun. Mahkeme bilinmiyorsa
        # iyelik eki ile bozuk bir cümle ("Mahkeme bilgisi yok'nin...")
        # kurmak yerine ayrı, dilbilgisel olarak doğru bir ifade kullanılır.
        if mahkeme_bilinmiyor:
            atif = "İlgili yerleşik içtihat (mahkeme bilgisi mevcut değil)"
        elif esas and karar:
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


def _dilekce_baslik(dilekce_turu: str, ozel_konu: str | None = None) -> str:
    """Dropdown'daki 5 sabit türe girmeyen davalar için kullanıcının serbest
    yazdığı konu varsa onu, yoksa standart tür etiketini döndürür."""
    ozel_konu = (ozel_konu or "").strip()
    if ozel_konu:
        return ozel_konu
    return DILEKCE_TURU_LABEL.get(dilekce_turu, "Hukuki Dilekçe")


def _stub_dilekce(
    durum: str,
    dilekce_turu: str,
    taraflar: dict | None,
    emsaller: list[dict],
    ozel_konu: str | None = None,
) -> str:
    """LLM yokken kullanılacak basit şablon — sadece iskelet."""
    taraflar = taraflar or {}
    alacakli = taraflar.get("alacakli", "[ALACAKLI / DAVACI]")
    borclu = taraflar.get("borclu", "[BORÇLU / DAVALI]")
    baslik = _dilekce_baslik(dilekce_turu, ozel_konu)
    dayanak = DILEKCE_TURU_HUKUKI_DAYANAK.get(dilekce_turu, "İlgili mevzuat.")

    atiflar = []
    for em in _kullanilan_emsaller_format(emsaller):
        atiflar.append(f"  - {em['atif_text']}")
    atif_blok = "\n".join(atiflar) if atiflar else "  (Emsal bulunamadı)"

    # NOT: Bu metin (demo/iskelet moduna düşüldüğünde) doğrudan kullanıcıya
    # gösterilir — iç mimari/altyapı detayı (API key, .env vb.) İÇERMEMELİDİR.
    # Kullanıcıya ayrıca gösterilen genel "şu an kullanılamıyor" uyarısı
    # (bkz. _KULLANICI_DEMO_MESAJI) yeterlidir; belgenin kendisi temiz kalır.
    return (
        f"SAYIN ... MAHKEMESİ'NE\n\n"
        f"DAVACI: {alacakli}\n"
        f"DAVALI: {borclu}\n\n"
        f"KONU: {baslik} talebimizi içerir.\n\n"
        f"AÇIKLAMALAR:\n"
        f"Somut Olay:\n{durum}\n\n"
        f"İlgili Emsal Kararlar:\n{atif_blok}\n\n"
        f"HUKUKİ NEDENLER: {dayanak}\n\n"
        f"DELİLLER: Her türlü yasal delil.\n\n"
        f"SONUÇ VE İSTEM: Yukarıda arz edilen nedenlerle talebimizin kabulüne "
        f"karar verilmesini saygılarımla arz ve talep ederim.\n"
    )


DILEKCE_TURU_TALEP = {
    "itirazin_iptali": (
        "Yukarıda açıklanan nedenlerle; davalı borçlunun icra takibine yönelik "
        "haksız ve kötüniyetli İTİRAZININ İPTALİNE, takibin devamına, alacağın "
        "%20'sinden az olmamak üzere icra inkâr tazminatına hükmedilmesine, "
        "yargılama giderleri ile vekâlet ücretinin davalıya yükletilmesine karar "
        "verilmesini saygıyla talep ederiz."
    ),
    "ihalenin_feshi": (
        "Yukarıda açıklanan nedenlerle; usulsüz gerçekleştirilen İHALENİN FESHİNE, "
        "yargılama giderleri ile vekâlet ücretinin karşı tarafa yükletilmesine "
        "karar verilmesini saygıyla talep ederiz."
    ),
    "menfi_tespit": (
        "Yukarıda açıklanan nedenlerle; müvekkilin davalıya BORÇLU OLMADIĞININ "
        "TESPİTİNE, yargılama giderleri ile vekâlet ücretinin davalıya "
        "yükletilmesine karar verilmesini saygıyla talep ederiz."
    ),
    "tahsilat": (
        "Yukarıda açıklanan nedenlerle; alacağımızın işleyecek faiziyle birlikte "
        "davalıdan TAHSİLİNE, yargılama giderleri ile vekâlet ücretinin davalıya "
        "yükletilmesine karar verilmesini saygıyla talep ederiz."
    ),
    "genel": (
        "Yukarıda açıklanan nedenlerle; talebimizin KABULÜNE, yargılama giderleri "
        "ile vekâlet ücretinin karşı tarafa yükletilmesine karar verilmesini "
        "saygıyla talep ederiz."
    ),
}

_TARAF_ROL = {
    "itirazin_iptali": ("DAVACI (Alacaklı)", "DAVALI (Borçlu)"),
    "ihalenin_feshi": ("DAVACI (Şikâyetçi)", "DAVALI"),
    "menfi_tespit": ("DAVACI (Borçlu)", "DAVALI (Alacaklı)"),
    "tahsilat": ("DAVACI (Alacaklı)", "DAVALI (Borçlu)"),
    "genel": ("DAVACI", "DAVALI"),
}


def generate_dilekce_template(
    durum: str,
    dilekce_turu: str = "genel",
    taraflar: dict | None = None,
    ozel_konu: str | None = None,
) -> dict:
    """LLM/RAG KULLANMADAN, form alanlarından yapılandırılmış dilekçe iskeleti üretir.

    Hızlı/ücretsiz mod: emsal kararlara atıf ve olaya özel hukuki argüman İÇERMEZ —
    bu kısımlar 'AI + Emsal' (Pro) modunun değer katan tarafıdır.

    `ozel_konu`: dropdown'daki 5 sabit türe girmeyen davalar için kullanıcının
    serbest yazdığı konu (örn. "Boşanma Davası", "Kira Tespiti"). Verilirse
    KONU başlığında standart tür etiketinin yerine kullanılır; HUKUKİ NEDENLER
    ve SONUÇ VE İSTEM yine de "genel" şablonundan gelir (bu mod LLM kullanmaz,
    olaya özel gerekçe üretemez — bunun için 'AI + Emsal' modu gerekir).
    """
    from datetime import date

    turu = dilekce_turu if dilekce_turu in DILEKCE_TURU_LABEL else "genel"
    taraflar = taraflar or {}
    davaci = (taraflar.get("alacakli") or "").strip() or "[DAVACI AD SOYAD / UNVAN]"
    davali = (taraflar.get("borclu") or "").strip() or "[DAVALI AD SOYAD / UNVAN]"
    davaci_rol, davali_rol = _TARAF_ROL.get(turu, _TARAF_ROL["genel"])
    baslik = _dilekce_baslik(turu, ozel_konu)

    olay = (durum or "").strip() or "[Olay anlatımı buraya yazılacaktır.]"
    paragraflar = [p.strip() for p in olay.split("\n") if p.strip()]
    if len(paragraflar) <= 1:
        aciklamalar = f"1. {olay}"
    else:
        aciklamalar = "\n".join(f"{i}. {p}" for i, p in enumerate(paragraflar, 1))

    bugun = date.today().strftime("%d.%m.%Y")
    metin = (
        f"SAYIN ( ) NÖBETÇİ MAHKEMESİ'NE\n\n"
        f"{davaci_rol} : {davaci}\n"
        f"{davali_rol} : {davali}\n"
        f"KONU : {baslik}\n\n"
        f"AÇIKLAMALAR :\n{aciklamalar}\n\n"
        f"HUKUKİ NEDENLER : {DILEKCE_TURU_HUKUKI_DAYANAK[turu]}\n\n"
        f"DELİLLER : İcra dosyası, ilgili sözleşme/senet/çek, ticari defterler, "
        f"tanık ve her türlü yasal delil.\n\n"
        f"SONUÇ VE İSTEM : {DILEKCE_TURU_TALEP[turu]}\n\n"
        f"{bugun}\n"
        f"Davacı / Vekili\n"
        f"{davaci}\n"
    )

    uyari = (
        "Bu taslak hazır şablondan üretildi; olayınıza özel emsal karar atfı ve "
        "gerekçeli hukuki argüman İÇERMEZ. Emsallere dayalı, olaya özel dilekçe "
        "için 'AI + Emsal' (Pro) modunu kullanın. Mahkemeye sunmadan önce mutlaka "
        "bir avukata danışın."
    )

    return {
        "dilekce_metni": metin,
        "kullanilan_emsaller": [],
        "uyari": uyari,
        "mode": "sablon",
    }


def generate_dilekce(
    durum: str,
    dilekce_turu: str = "genel",
    taraflar: dict | None = None,
    k: int = 5,
    ozel_konu: str | None = None,
) -> dict:
    """Emsal-bağlamlı dilekçe taslağı üret.

    Args:
        durum: Kullanıcının serbest metinle anlattığı somut olay.
        dilekce_turu: "itirazin_iptali" | "ihalenin_feshi" | "menfi_tespit"
                      | "tahsilat" | "genel"
        taraflar: {"alacakli": "...", "borclu": "..."} (opsiyonel)
        k: RAG için top-k.
        ozel_konu: Dropdown'daki 5 sabit türe girmeyen davalar için kullanıcının
                   serbest yazdığı konu (örn. "Boşanma Davası", "Miras Reddi").
                   Verilirse LLM, KONU başlığını ve hukuki gerekçeyi bu konuya
                   göre üretir — statik DILEKCE_TURU_HUKUKI_DAYANAK yalnızca
                   bir öneri/ipucu olarak kalır, LLM buna bağlı kalmak zorunda
                   değildir.

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
        log.warning(f"Dilekçe için RAG araması başarısız: {e}")

    kullanilan = _kullanilan_emsaller_format(emsaller)

    # 2) LLM kontrolü — yoksa demo modu.
    if not is_available():
        # Bu, prod ortamında ANTHROPIC_API_KEY/GOOGLE_API_KEY yapılandırma
        # hatası anlamına gelir — ücretli bir Pro özelliği sessizce şablona
        # düşüyor demektir. Ops/Sentry görsün diye ERROR seviyesinde logla;
        # kullanıcıya iç mimari detay (env değişkeni, .env) asla gösterilmez.
        log.error(
            "Dilekçe üretimi DEMO MODUNA düştü: LLM API key yok "
            "(ANTHROPIC_API_KEY / GOOGLE_API_KEY). Kullanıcıya yalnızca "
            "iskelet dilekçe döndürülüyor."
        )
        stub = _stub_dilekce(durum, dilekce_turu, taraflar, emsaller, ozel_konu)
        return {
            "dilekce_metni": stub,
            "kullanilan_emsaller": kullanilan,
            "uyari": _KULLANICI_DEMO_MESAJI,
        }

    # 3) Prompt hazırla.
    taraflar = taraflar or {}
    alacakli = (taraflar.get("alacakli") or "").strip() or "[ALACAKLI / DAVACI]"
    borclu = (taraflar.get("borclu") or "").strip() or "[BORÇLU / DAVALI]"
    baslik = _dilekce_baslik(dilekce_turu, ozel_konu)
    dayanak = DILEKCE_TURU_HUKUKI_DAYANAK.get(dilekce_turu, "İlgili mevzuat.")
    if ozel_konu and ozel_konu.strip():
        # Kullanıcı dropdown'da olmayan bir tür belirtmiş — statik dayanak
        # metnini bağlayıcı değil, yalnızca ipucu olarak sun.
        dayanak = (
            f"(Aşağıdaki '{DILEKCE_TURU_LABEL.get(dilekce_turu, 'genel')}' türü için genel "
            f"ipucu niteliğindedir, kullanıcının belirttiği '{ozel_konu.strip()}' konusuna göre "
            f"KENDİN en uygun kanun maddelerini ve içtihatları seç: {dayanak})"
        )
    emsal_blogu = _emsal_blogu_hazirla(emsaller)

    user_prompt = f"""DİLEKÇE TÜRÜ: {baslik}{f" ({dilekce_turu})" if not ozel_konu else ""}

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
        uyari = ""
    except Exception as e:
        # LLM çağrısı patladı — stub'a dön. Gerçek sebep (ki bazen API key/
        # kota/ağ hatası olur) yalnızca loglanır; kullanıcıya iç detay verilmez.
        log.error(f"Dilekçe için LLM çağrısı başarısız, iskelete düşüldü: {e}")
        metin = _stub_dilekce(durum, dilekce_turu, taraflar, emsaller, ozel_konu)
        uyari = _KULLANICI_DEMO_MESAJI

    return {
        "dilekce_metni": metin,
        "kullanilan_emsaller": kullanilan,
        "uyari": uyari,
    }


def generate_dilekce_stream(
    durum: str,
    dilekce_turu: str = "genel",
    taraflar: dict | None = None,
    k: int = 5,
    ozel_konu: str | None = None,
):
    """Streaming dilekçe üretimi — event dict'leri yield eder.

    Event'ler:
      {"type": "meta",  "kullanilan_emsaller": [...], "uyari": str, "demo": bool}
      {"type": "delta", "text": str}          # LLM'den gelen parça
      {"type": "done"}
    """
    from llm.provider import generate_stream

    durum = (durum or "").strip()
    if not durum:
        yield {"type": "meta", "kullanilan_emsaller": [],
               "uyari": "Olay anlatımı (durum) boş — dilekçe üretilemedi.",
               "demo": False}
        yield {"type": "done"}
        return

    if dilekce_turu not in DILEKCE_TURU_LABEL:
        dilekce_turu = "genel"

    # 1) RAG araması
    try:
        emsaller = search(durum, k=k)
    except Exception as e:
        emsaller = []
        log.warning(f"Dilekçe (stream) için RAG araması başarısız: {e}")

    kullanilan = _kullanilan_emsaller_format(emsaller)

    # 2) LLM yoksa demo modu — stub'ı tek seferde gönder. Gerçek sebep (env
    # yapılandırma hatası) yalnızca sunucu loguna yazılır, kullanıcıya
    # gösterilmez — bu onu ilgilendiren bir konu değil.
    if not is_available():
        log.error(
            "Dilekçe (stream) üretimi DEMO MODUNA düştü: LLM API key yok "
            "(ANTHROPIC_API_KEY / GOOGLE_API_KEY)."
        )
        yield {"type": "meta", "kullanilan_emsaller": kullanilan,
               "uyari": _KULLANICI_DEMO_MESAJI, "demo": False}
        yield {"type": "delta",
               "text": _stub_dilekce(durum, dilekce_turu, taraflar, emsaller, ozel_konu)}
        yield {"type": "done"}
        return

    # 3) Prompt (generate_dilekce ile aynı)
    taraflar = taraflar or {}
    alacakli = (taraflar.get("alacakli") or "").strip() or "[ALACAKLI / DAVACI]"
    borclu = (taraflar.get("borclu") or "").strip() or "[BORÇLU / DAVALI]"
    baslik = _dilekce_baslik(dilekce_turu, ozel_konu)
    dayanak = DILEKCE_TURU_HUKUKI_DAYANAK.get(dilekce_turu, "İlgili mevzuat.")
    if ozel_konu and ozel_konu.strip():
        dayanak = (
            f"(Aşağıdaki '{DILEKCE_TURU_LABEL.get(dilekce_turu, 'genel')}' türü için genel "
            f"ipucu niteliğindedir, kullanıcının belirttiği '{ozel_konu.strip()}' konusuna göre "
            f"KENDİN en uygun kanun maddelerini ve içtihatları seç: {dayanak})"
        )
    emsal_blogu = _emsal_blogu_hazirla(emsaller)

    user_prompt = f"""DİLEKÇE TÜRÜ: {baslik}{f" ({dilekce_turu})" if not ozel_konu else ""}

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

    # 4) Önce meta (frontend emsalleri hemen gösterebilsin), sonra delta'lar
    yield {"type": "meta", "kullanilan_emsaller": kullanilan,
           "uyari": "", "demo": False}

    try:
        for piece in generate_stream(
            system=SISTEM_PROMPT, user=user_prompt,
            max_tokens=2500, temperature=0.3,
        ):
            yield {"type": "delta", "text": piece}
    except Exception as e:
        log.error(f"Dilekçe (stream) LLM akışı kesildi: {e}")
        yield {"type": "error",
               "message": "Üretim sırasında bir sorun oluştu. Lütfen tekrar deneyin."}
        return
    yield {"type": "done"}
