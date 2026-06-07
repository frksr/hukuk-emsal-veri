"""Tarayıcıdan kopyalanan cURL komutunu parse edip scraper config'i üretir.

Kullanım:
  1. Chrome F12 -> Network -> XHR -> POST isteğine sağ tık
  2. Copy -> Copy as cURL (bash)
  3. Komutu bir dosyaya yapıştır (örn: curls/danistay.curl)
  4. python3 scripts/curl_to_config.py curls/danistay.curl
"""
import argparse
import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_curl(curl_text: str) -> dict:
    """cURL komutunu yapı taşlarına ayır."""
    # Çoklu satırı tek satıra getir (backslash + newline)
    t = re.sub(r"\\\s*\n", " ", curl_text.strip())
    t = re.sub(r"\s+", " ", t)

    # Shell parse
    parts = shlex.split(t)
    if not parts or parts[0] != "curl":
        raise ValueError("Komut 'curl' ile başlamıyor")

    method = "GET"
    url = None
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    body = None

    i = 1
    while i < len(parts):
        p = parts[i]
        if p in ("-X", "--request"):
            method = parts[i + 1]; i += 2
        elif p in ("-H", "--header"):
            line = parts[i + 1]
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
            i += 2
        elif p in ("-b", "--cookie"):
            for pair in parts[i + 1].split(";"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookies[k.strip()] = v.strip()
            i += 2
        elif p in ("--data-raw", "--data", "-d", "--data-binary"):
            body = parts[i + 1]
            if method == "GET":
                method = "POST"
            i += 2
        elif p.startswith("http"):
            url = p; i += 1
        elif p in ("--compressed", "--insecure", "-k", "-i", "-v"):
            i += 1
        else:
            i += 1

    # Body JSON mu?
    body_json = None
    if body:
        try:
            body_json = json.loads(body)
        except Exception:
            pass

    return {
        "method": method,
        "url": url,
        "headers": headers,
        "cookies": cookies,
        "body_raw": body,
        "body_json": body_json,
    }


def to_scraper_config(parsed: dict) -> str:
    """Parsed cURL'den scraper Python config snippet üret."""
    h = {k: v for k, v in parsed["headers"].items()
         if k.lower() not in ("host", "content-length", "connection")}

    # Body parametrelendir: arama metnini placeholder yap
    body = parsed["body_json"]
    if body:
        bj = json.dumps(body, ensure_ascii=False, indent=4)
        # arananKelime placeholder
        bj = re.sub(r'"arananKelime"\s*:\s*"[^"]+"',
                    '"arananKelime": KEYWORD_PLACEHOLDER', bj)
        # pageSize / pageNumber placeholder
        bj = re.sub(r'"pageSize"\s*:\s*\d+', '"pageSize": PAGE_SIZE_PLACEHOLDER', bj)
        bj = re.sub(r'"pageNumber"\s*:\s*\d+', '"pageNumber": PAGE_NUMBER_PLACEHOLDER', bj)
    else:
        bj = "None  # body parse edilemedi: " + (parsed["body_raw"] or "")[:120]

    snippet = f'''# AUTO-GENERATED from cURL — gözden geçir, sonra scraper'a yapıştır
URL = "{parsed["url"]}"
METHOD = "{parsed["method"]}"

# Önemli header'lar (tarayıcıdan alındı)
HEADERS = {json.dumps(h, ensure_ascii=False, indent=4)}

# Cookies (varsa otomatik gönderilmesi gerekebilir)
COOKIES = {json.dumps(parsed["cookies"], ensure_ascii=False, indent=4)}

# Payload — KEYWORD_PLACEHOLDER yerine arama metnini, page placeholder'larına
# gerçek değer koy
PAYLOAD_TEMPLATE = {bj}
'''
    return snippet


def main():
    p = argparse.ArgumentParser()
    p.add_argument("curl_file", help="cURL komutunu içeren dosya yolu")
    args = p.parse_args()

    raw = Path(args.curl_file).read_text(encoding="utf-8")
    parsed = parse_curl(raw)

    print("=" * 60)
    print("PARSED CURL")
    print("=" * 60)
    print(f"URL:    {parsed['url']}")
    print(f"Method: {parsed['method']}")
    print(f"Headers ({len(parsed['headers'])}):")
    for k, v in parsed["headers"].items():
        # Sensitive değerleri kısalt
        display = v[:60] + "..." if len(v) > 60 else v
        print(f"  {k}: {display}")
    print(f"Cookies ({len(parsed['cookies'])}):")
    for k, v in parsed["cookies"].items():
        display = v[:40] + "..." if len(v) > 40 else v
        print(f"  {k}={display}")
    print(f"\nBody (raw): {(parsed['body_raw'] or '')[:300]}")
    if parsed["body_json"]:
        print(f"\nBody JSON top-keys: {list(parsed['body_json'].keys())}")
        print(json.dumps(parsed["body_json"], ensure_ascii=False, indent=2)[:500])

    print("\n" + "=" * 60)
    print("GENERATED CONFIG")
    print("=" * 60)
    print(to_scraper_config(parsed))


if __name__ == "__main__":
    main()
