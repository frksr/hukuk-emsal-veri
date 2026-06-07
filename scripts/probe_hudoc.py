"""HUDOC API yanıt yapısını incele — sıfır sonuç sorununu teşhis et."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import httpx

API = "https://hudoc.echr.coe.int/app/query/results"


async def main():
    queries_to_try = [
        # 1. En basit: sadece Türkiye
        {
            "label": "Sadece Türkiye, filtre yok",
            "params": {
                "query": 'respondent:"TUR"',
                "select": "itemid,appno,docname,judgementdate,respondent",
                "sort": "kpdate Descending",
                "start": 0,
                "length": 5,
            },
        },
        # 2. Türkiye + Lucene full-text "execution"
        {
            "label": "Türkiye + execution",
            "params": {
                "query": 'respondent:"TUR" AND "execution"',
                "select": "itemid,appno,docname,judgementdate,respondent",
                "start": 0,
                "length": 5,
            },
        },
        # 3. Documentcollectionid2 ile
        {
            "label": "JUDGMENTS koleksiyonu + Türkiye",
            "params": {
                "query": '(documentcollectionid2:"JUDGMENTS") AND respondent:"TUR"',
                "select": "itemid,appno,docname,judgementdate,respondent",
                "start": 0,
                "length": 5,
            },
        },
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://hudoc.echr.coe.int/",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
        for q in queries_to_try:
            print(f"\n{'='*60}")
            print(f"TEST: {q['label']}")
            print(f"Query: {q['params']['query']}")
            print('-'*60)
            try:
                r = await client.get(API, params=q["params"])
                print(f"HTTP {r.status_code}")
                print(f"Content-Type: {r.headers.get('content-type')}")
                if r.status_code != 200:
                    print(f"Body (ilk 500): {r.text[:500]}")
                    continue
                try:
                    data = r.json()
                except Exception:
                    print(f"JSON parse edilemedi. Body (ilk 800):\n{r.text[:800]}")
                    continue

                print(f"Top-level keys: {list(data.keys())}")
                rc = data.get("ResultCount") or data.get("resultcount") or data.get("resultCount")
                print(f"ResultCount: {rc}")

                results = (data.get("Results") or data.get("results") or
                          data.get("ResultList") or [])
                print(f"Results sayısı: {len(results)}")

                if results:
                    first = results[0]
                    print(f"İlk sonuç keys: {list(first.keys())}")
                    cols = first.get("Columns") or first.get("columns") or {}
                    if cols:
                        print(f"Columns keys: {list(cols.keys())}")
                        print(f"Örnek itemid: {cols.get('itemid')}")
                        print(f"Örnek docname: {cols.get('docname')}")
                        print(f"Örnek date: {cols.get('judgementdate') or cols.get('kpdate')}")
                    else:
                        print(f"İlk sonuç ham: {json.dumps(first, ensure_ascii=False)[:400]}")
            except Exception as e:
                print(f"HATA: {type(e).__name__}: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
