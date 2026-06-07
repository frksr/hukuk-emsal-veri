"""Mevcut data/raw/{source}/*.html dosyalarından temiz JSONL'i yeniden üret.

Mevcut jsonl'lerde JavaScript kodu vs. garbage olabilir. Bu script raw HTML'leri
clean_html_to_text ile yeniden parse eder ve jsonl'i overwrite eder.

Çalıştır:
  python scripts/reextract.py                    # tüm kaynaklar
  python scripts/reextract.py --source danistay  # sadece danistay
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import orjson
from selectolax.parser import HTMLParser
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.normalize import (
    normalize_text, clean_html_to_text,
    extract_case_no, extract_decision_no, extract_decision_date,
    detect_keywords,
)
from common.anonymize import audit

KEYWORDS = [
    "icra", "tahsilat", "ihtar", "haciz", "ödeme emri", "ihtarname",
    "icra takibi", "icra emri", "amme alacağı", "vergi tahsilatı",
    "execution", "enforcement", "writ", "seizure", "non-enforcement",
]


def _extract_from_jsonl(jsonl_path: Path) -> dict[str, dict]:
    """Mevcut jsonl'den ID -> metadata haritası çıkar."""
    if not jsonl_path.exists():
        return {}
    items = {}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            iid = r.get("id", "")
            # source prefix'i kaldır: yargitay_123 → 123
            for prefix in ("yargitay_", "danistay_", "hudoc_", "aym_"):
                if iid.startswith(prefix):
                    raw_id = iid[len(prefix):]
                    items[raw_id] = r
                    break
    return items


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def process_html(source: str, raw_path: Path, meta: dict) -> dict | None:
    """Tek raw HTML dosyasını temiz JSONL kaydına dönüştür."""
    try:
        raw = raw_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    if not raw or len(raw) < 200:
        return None

    # JSON wrapper olabilir
    if raw.lstrip().startswith("{"):
        try:
            j = json.loads(raw)
            d = j.get("data") if isinstance(j, dict) else None
            if isinstance(d, str):
                text = clean_html_to_text(d)
            elif isinstance(d, dict):
                # data dict'inden html key bul
                candidate = None
                for k in ("kararHtml", "html", "icerik", "kararIcerigi",
                          "metin", "dokuman"):
                    v = d.get(k)
                    if v and isinstance(v, str) and len(v) > 50:
                        candidate = v
                        break
                text = clean_html_to_text(candidate or "")
            else:
                text = ""
        except Exception:
            text = clean_html_to_text(raw)
    else:
        text = clean_html_to_text(raw)

    if not text or len(text) < 100:
        return None

    raw_id = raw_path.stem

    # Mevcut metadata'yı kullan, eksikleri text'ten çıkar
    return {
        "id": meta.get("id") or f"{source}_{raw_id}",
        "source": source,
        "court_chamber": meta.get("court_chamber"),
        "court_level": meta.get("court_level") or "yuksek_mahkeme",
        "case_no": meta.get("case_no") or extract_case_no(text),
        "decision_no": meta.get("decision_no") or extract_decision_no(text),
        "decision_date": meta.get("decision_date") or extract_decision_date(text),
        "subject_keywords_query": meta.get("subject_keywords_query") or [],
        "topic_tags": detect_keywords(text, KEYWORDS),
        "referenced_laws": meta.get("referenced_laws") or [],
        "raw_html_path": str(raw_path),
        "raw_text": text,
        "cleaned_text": text,
        "anonymization_check": audit(text),
        "scraped_at": meta.get("scraped_at") or _now(),
        "scraper_version": meta.get("scraper_version", "1.0.0"),
        "source_url": meta.get("source_url"),
        "language": meta.get("language", "tr"),
        "char_count": len(text),
        "metadata": meta.get("metadata") or {},
    }


def reextract_source(source: str):
    raw_dir = ROOT / "data" / "raw" / source
    cleaned_path = ROOT / "data" / "cleaned" / f"{source}.jsonl"

    if not raw_dir.exists():
        print(f"[REX] {source}: raw dizini yok", file=sys.stderr)
        return

    # Mevcut metadata
    meta_map = _extract_from_jsonl(cleaned_path)
    print(f"[REX] {source}: {len(meta_map)} eski jsonl kaydı meta için yüklendi",
          file=sys.stderr)

    files = list(raw_dir.glob("*.html"))
    if not files:
        print(f"[REX] {source}: raw HTML yok", file=sys.stderr)
        return

    print(f"[REX] {source}: {len(files)} raw HTML dosyası", file=sys.stderr)

    # Yeniden yaz
    backup = cleaned_path.with_suffix(".jsonl.before-reextract")
    if cleaned_path.exists() and not backup.exists():
        cleaned_path.rename(backup)
        print(f"[REX] {source}: yedek alındı → {backup.name}", file=sys.stderr)
    elif cleaned_path.exists():
        cleaned_path.unlink()

    written = 0
    rejected = 0
    with cleaned_path.open("ab") as out:
        for raw_path in tqdm(files, desc=source):
            raw_id = raw_path.stem
            meta = meta_map.get(raw_id, {})
            rec = process_html(source, raw_path, meta)
            if rec:
                out.write(orjson.dumps(rec))
                out.write(b"\n")
                written += 1
            else:
                rejected += 1

    print(f"[REX] {source}: tamamlandı — yazılan {written}, atılan {rejected}",
          file=sys.stderr)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["yargitay", "danistay", "hudoc", "aym"],
                   default=None, help="Sadece bu kaynağı reextract et")
    args = p.parse_args()

    sources = [args.source] if args.source else ["yargitay", "danistay", "hudoc", "aym"]
    for s in sources:
        reextract_source(s)


if __name__ == "__main__":
    main()
