"""Modül bazlı kullanım kredileri (ek paketler).

- usage_credits: kullanıcı + modül başına güncel bakiye (süresiz).
- credit_transactions: hareket geçmişi (satın alma / kullanım / hediye).
- credit_orders: ek paket siparişi (ödeme onaylanınca krediler yüklenir).

Düşme/yükleme service_session (BYPASSRLS) ile yapılır; bakiye okuma RLS altında
db_session ile de yapılabilir. Atomik UPDATE ... WHERE balance >= n ile yarış
koşulu olmadan tek kredi düşülür.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Optional

from api.db import service_session

log = logging.getLogger("services.krediler")

# Modül (event_type) → kullanıcıya görünen etiket.
MODUL_ETIKET: dict[str, str] = {
    "arama": "Emsal Arama",
    "dilekce": "Dilekçe",
    "ihtarname": "İhtarname",
    "ozet": "Karar Özeti",
    "denetim": "Belge Denetimi",
    "karsi_argument": "Karşı Argüman",
    "sozlesme": "Sözleşme Analizi",
    "kvkk": "KVKK Asistanı",
    "sorgu": "UYAP Yapay Zeka Sorgu",
}


# ---------------------------------------------------------------------------
# Ek paket kataloğu. Her paket bir veya birden çok modüle kredi yükler.
# amount: TRY. Tek modüllük paketler + "bundle" (çok modüllü) paketler.
# ---------------------------------------------------------------------------
EK_PAKETLER: dict[str, dict] = {
    # — Tek modül paketleri —
    "arama_100": {
        "ad": "Emsal Arama — 100 arama",
        "aciklama": "100 ek emsal karar araması.",
        "modul": "arama",
        "krediler": {"arama": 100},
        "amount": Decimal("49.00"),
    },
    "dilekce_20": {
        "ad": "Dilekçe — 20 üretim",
        "aciklama": "20 ek Yapay Zeka dilekçe taslağı.",
        "modul": "dilekce",
        "krediler": {"dilekce": 20},
        "amount": Decimal("149.00"),
    },
    "ihtarname_20": {
        "ad": "İhtarname — 20 üretim",
        "aciklama": "20 ek Yapay Zeka ihtarname.",
        "modul": "ihtarname",
        "krediler": {"ihtarname": 20},
        "amount": Decimal("99.00"),
    },
    "ozet_50": {
        "ad": "Karar Özeti — 50 özet",
        "aciklama": "50 ek Yapay Zeka karar özeti.",
        "modul": "ozet",
        "krediler": {"ozet": 50},
        "amount": Decimal("99.00"),
    },
    "denetim_20": {
        "ad": "Belge Denetimi — 20 denetim",
        "aciklama": "20 ek belge denetimi.",
        "modul": "denetim",
        "krediler": {"denetim": 20},
        "amount": Decimal("99.00"),
    },
    "karsi_argument_20": {
        "ad": "Karşı Argüman — 20 analiz",
        "aciklama": "20 ek karşı argüman analizi.",
        "modul": "karsi_argument",
        "krediler": {"karsi_argument": 20},
        "amount": Decimal("99.00"),
    },
    "sozlesme_20": {
        "ad": "Sözleşme Analizi — 20 analiz",
        "aciklama": "20 ek sözleşme risk analizi.",
        "modul": "sozlesme",
        "krediler": {"sozlesme": 20},
        "amount": Decimal("149.00"),
    },
    "uyap_sorgu_100": {
        "ad": "UYAP Sorgu — 100 sorgu",
        "aciklama": "Kendi dosyalarınızda 100 ek Yapay Zeka sorgusu.",
        "modul": "sorgu",
        "krediler": {"sorgu": 100},
        "amount": Decimal("199.00"),
    },
    # — Bundle (çok modüllü) paketler —
    "ai_baslangic": {
        "ad": "Yapay Zeka Başlangıç Paketi",
        "aciklama": "Tüm Yapay Zeka araçlarından 20'şer kullanım.",
        "modul": None,
        "krediler": {
            "dilekce": 20, "ihtarname": 20, "ozet": 20,
            "denetim": 20, "karsi_argument": 20, "sozlesme": 20,
        },
        "amount": Decimal("399.00"),
    },
    "ai_pro": {
        "ad": "Yapay Zeka Pro Paketi",
        "aciklama": "Tüm Yapay Zeka araçlarından 50'şer kullanım.",
        "modul": None,
        "krediler": {
            "dilekce": 50, "ihtarname": 50, "ozet": 50,
            "denetim": 50, "karsi_argument": 50, "sozlesme": 50,
        },
        "amount": Decimal("799.00"),
    },
}


def paket_bilgi(pack_key: str) -> Optional[dict]:
    return EK_PAKETLER.get(pack_key)


def modul_paketleri(module: str) -> list[str]:
    """Bir modüle kredi veren paketlerin anahtarları (tek modül + bundle dahil)."""
    return [k for k, p in EK_PAKETLER.items() if module in p["krediler"]]


# ---------------------------------------------------------------------------
# Dinamik (DB-override'lı) katalog. Admin panelden düzenlenince yansır; DB
# override'ı yoksa yukarıdaki kod EK_PAKETLER'i (varsayılan) kullanılır.
# ---------------------------------------------------------------------------
def _normalize_pack(p: dict) -> dict:
    """DB'den gelen ham paketi normalize eder (amount → Decimal, krediler → int)."""
    out = dict(p)
    raw_amount = out.get("amount", 0)
    if not isinstance(raw_amount, Decimal):
        try:
            out["amount"] = Decimal(str(raw_amount))
        except Exception:
            out["amount"] = Decimal("0")
    krediler_map = out.get("krediler") or {}
    if isinstance(krediler_map, dict):
        temiz = {}
        for m, n in krediler_map.items():
            try:
                temiz[m] = int(n)
            except (TypeError, ValueError):
                continue
        out["krediler"] = temiz
    else:
        out["krediler"] = {}
    out.setdefault("ad", "")
    out.setdefault("aciklama", "")
    out.setdefault("modul", None)
    return out


async def aktif_paketler() -> dict:
    """Etkin ek paket kataloğu — DB override varsa o, yoksa kod EK_PAKETLER'i."""
    from services import app_config
    db = await app_config.get_credit_packs()
    if not db or not isinstance(db, dict):
        return EK_PAKETLER
    try:
        return {k: _normalize_pack(p) for k, p in db.items() if isinstance(p, dict)}
    except Exception as e:
        log.warning("ek paket kataloğu normalize hatası, koda düşülüyor: %s", e)
        return EK_PAKETLER


async def paket_bilgi_async(pack_key: str) -> Optional[dict]:
    """Tek paket bilgisi (dinamik katalog üzerinden)."""
    return (await aktif_paketler()).get(pack_key)


async def modul_paketleri_async(module: str) -> list[str]:
    """Bir modüle kredi veren paketlerin anahtarları (dinamik katalog)."""
    paketler = await aktif_paketler()
    return [k for k, p in paketler.items() if module in (p.get("krediler") or {})]


async def bakiye(user_id: str, module: str) -> int:
    """Tek modül için güncel bakiye (0 if yok)."""
    if not user_id:
        return 0
    async with service_session() as conn:
        val = await conn.fetchval(
            "SELECT balance FROM usage_credits WHERE user_id = $1 AND module = $2",
            user_id, module,
        )
    return int(val or 0)


async def tum_bakiyeler(user_id: str) -> dict[str, int]:
    """Kullanıcının tüm modül bakiyeleri {module: balance} (yalnızca >0)."""
    if not user_id:
        return {}
    async with service_session() as conn:
        rows = await conn.fetch(
            "SELECT module, balance FROM usage_credits WHERE user_id = $1 AND balance > 0",
            user_id,
        )
    return {r["module"]: int(r["balance"]) for r in rows}


async def dus(user_id: str, module: str, n: int = 1) -> bool:
    """Bakiyeden n kredi atomik olarak düşer. Yeterli bakiye varsa True döner.

    Yarış koşulu yok: UPDATE ... WHERE balance >= n RETURNING ile tek adımda.
    """
    if not user_id or n <= 0:
        return False
    try:
        async with service_session() as conn:
            async with conn.transaction():
                yeni = await conn.fetchval(
                    """UPDATE usage_credits SET balance = balance - $3, updated_at = NOW()
                       WHERE user_id = $1 AND module = $2 AND balance >= $3
                       RETURNING balance""",
                    user_id, module, n,
                )
                if yeni is None:
                    return False
                await conn.execute(
                    """INSERT INTO credit_transactions (user_id, module, delta, reason)
                       VALUES ($1, $2, $3, 'consume')""",
                    user_id, module, -n,
                )
        return True
    except Exception as e:
        log.warning("kredi düşme hatası (%s/%s): %s", module, user_id, e)
        return False


async def ekle(
    user_id: str,
    tenant_id: Optional[str],
    krediler: dict[str, int],
    reason: str = "purchase",
    ref: Optional[str] = None,
) -> None:
    """Bir veya çok modüle kredi yükler (upsert) + hareket kaydı yazar."""
    if not user_id or not krediler:
        return
    async with service_session() as conn:
        async with conn.transaction():
            for module, n in krediler.items():
                if not n:
                    continue
                await conn.execute(
                    """INSERT INTO usage_credits (user_id, tenant_id, module, balance)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (user_id, module)
                       DO UPDATE SET balance = usage_credits.balance + EXCLUDED.balance,
                                     updated_at = NOW()""",
                    user_id, tenant_id, module, int(n),
                )
                await conn.execute(
                    """INSERT INTO credit_transactions
                           (user_id, tenant_id, module, delta, reason, ref)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    user_id, tenant_id, module, int(n), reason, ref,
                )


async def hareketler(user_id: str, limit: int = 50) -> list[dict]:
    """Kredi hareket geçmişi (satın alma + kullanım)."""
    if not user_id:
        return []
    async with service_session() as conn:
        rows = await conn.fetch(
            """SELECT module, delta, reason, ref, created_at
               FROM credit_transactions WHERE user_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            user_id, min(int(limit), 200),
        )
    return [
        {
            "module": r["module"],
            "modul_etiket": MODUL_ETIKET.get(r["module"], r["module"]),
            "delta": int(r["delta"]),
            "reason": r["reason"],
            "ref": r["ref"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
