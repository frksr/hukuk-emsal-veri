"""HuggingFace + GitHub'da Türk hukuk veri setleri envanteri."""
import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "external" / "INVENTORY.md"
JSON_OUT = ROOT / "data" / "external" / "inventory.json"

HF_QUERIES = [
    "turkish legal",
    "turkish law",
    "yargitay",
    "danistay",
    "turkish court",
    "turkce hukuk",
    "anayasa mahkemesi",
    "uyap",
    "kvkk",
    "icra",
]

GITHUB_QUERIES = [
    "yargitay scraper",
    "danistay scraper",
    "turkish legal dataset",
    "uyap kararlar",
    "emsal karar",
    "turkish law nlp",
]


async def search_huggingface(client: httpx.AsyncClient, query: str) -> list[dict]:
    url = "https://huggingface.co/api/datasets"
    r = await client.get(url, params={"search": query, "limit": 30})
    if r.status_code != 200:
        return []
    return r.json()


async def search_github(client: httpx.AsyncClient, query: str) -> list[dict]:
    url = "https://api.github.com/search/repositories"
    headers = {"Accept": "application/vnd.github+json"}
    r = await client.get(url, params={"q": query, "per_page": 30}, headers=headers)
    if r.status_code != 200:
        return []
    return r.json().get("items", [])


async def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    hf_results: dict[str, dict] = {}
    gh_results: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for q in HF_QUERIES:
            try:
                items = await search_huggingface(client, q)
                for it in items:
                    rid = it.get("id") or it.get("modelId")
                    if not rid:
                        continue
                    hf_results[rid] = {
                        "id": rid,
                        "downloads": it.get("downloads", 0),
                        "likes": it.get("likes", 0),
                        "tags": it.get("tags", []),
                        "found_via": q,
                        "url": f"https://huggingface.co/datasets/{rid}",
                    }
                print(f"[HF] '{q}' -> {len(items)} sonuç", file=sys.stderr)
            except Exception as e:
                print(f"[HF] '{q}' hata: {e}", file=sys.stderr)
            await asyncio.sleep(1)

        for q in GITHUB_QUERIES:
            try:
                items = await search_github(client, q)
                for it in items:
                    full = it.get("full_name")
                    if not full:
                        continue
                    gh_results[full] = {
                        "id": full,
                        "stars": it.get("stargazers_count", 0),
                        "description": (it.get("description") or "")[:200],
                        "language": it.get("language"),
                        "updated_at": it.get("updated_at"),
                        "found_via": q,
                        "url": it.get("html_url"),
                    }
                print(f"[GH] '{q}' -> {len(items)} sonuç", file=sys.stderr)
            except Exception as e:
                print(f"[GH] '{q}' hata: {e}", file=sys.stderr)
            await asyncio.sleep(2)  # GitHub anonim rate limit: 10/dk

    # Türkçe ilgisini filtrele
    keywords = ["turk", "türk", "yarg", "danı", "dani", "uyap", "anayasa",
                "emsal", "hukuk", "kvkk", "mahkeme", "icra", "tahsilat", "ihtar"]

    def is_relevant(text: str) -> bool:
        t = text.lower()
        return any(k in t for k in keywords)

    hf_relevant = {
        k: v for k, v in hf_results.items()
        if is_relevant(k) or any(is_relevant(t) for t in v.get("tags") or [])
    }
    gh_relevant = {
        k: v for k, v in gh_results.items()
        if is_relevant(k) or is_relevant(v.get("description") or "")
    }

    # Sırala: download/star desc
    hf_sorted = sorted(hf_relevant.values(), key=lambda x: -x["downloads"])
    gh_sorted = sorted(gh_relevant.values(), key=lambda x: -x["stars"])

    # JSON export
    JSON_OUT.write_text(json.dumps({
        "huggingface": hf_sorted,
        "github": gh_sorted,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown rapor
    lines = ["# Türk Hukuk Veri Seti Envanteri\n",
             f"_Otomatik üretildi. HF sonuç: {len(hf_sorted)}, GH sonuç: {len(gh_sorted)}_\n"]

    lines.append("\n## HuggingFace Datasets\n")
    lines.append("| ID | Downloads | Likes | URL |\n|---|---|---|---|")
    for v in hf_sorted[:50]:
        lines.append(f"| `{v['id']}` | {v['downloads']} | {v['likes']} | <{v['url']}> |")

    lines.append("\n## GitHub Repositories\n")
    lines.append("| Repo | Stars | Dil | Açıklama | URL |\n|---|---|---|---|---|")
    for v in gh_sorted[:50]:
        desc = (v["description"] or "").replace("|", "\\|")
        lines.append(f"| `{v['id']}` | {v['stars']} | {v['language'] or '-'} | {desc} | <{v['url']}> |")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[DONE] HF ilgili: {len(hf_sorted)}, GH ilgili: {len(gh_sorted)}", file=sys.stderr)
    print(f"Rapor: {OUT}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
