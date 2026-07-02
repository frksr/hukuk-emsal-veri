"""Mevcut tenant belgelerini ANONİM embedding ile yeniden indeksle.

Neden: redact-before-embed (KVKK) devreye alınmadan önce indekslenen chunk'ların
embedding'leri, ham metin dış API'ye gönderilerek üretilmişti. Bu script tüm
tenant belgelerini pii_redaction.redact_for_embedding'den geçirerek yeniden
embed eder ve tenant_rag_chunks tablosunu günceller.

Kullanım:
    python -m scripts.reindex_tenant_docs            # tümü
    python -m scripts.reindex_tenant_docs --tenant <uuid>   # tek tenant
    python -m scripts.reindex_tenant_docs --dry-run  # sadece say

Not: cleaned_text DB'de durduğu için dosyaların yeniden parse edilmesi gerekmez.
"""
from __future__ import annotations
import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reindex_tenant_docs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", help="Yalnızca bu tenant_id (uuid)")
    parser.add_argument("--dry-run", action="store_true", help="Yazma, sadece say")
    args = parser.parse_args()

    from services import pg
    from services.tenant_rag import index_document

    where = "WHERE status = 'ready' AND cleaned_text IS NOT NULL"
    params: list = []
    if args.tenant:
        where += " AND tenant_id = %s"
        params.append(args.tenant)

    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT id, tenant_id, title, document_type, case_no, court, cleaned_text
                    FROM tenant_documents {where} ORDER BY created_at""",
                params,
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

    docs = [dict(zip(cols, r)) for r in rows]
    log.info("Yeniden indekslenecek belge: %d%s", len(docs), " (dry-run)" if args.dry_run else "")
    if args.dry_run:
        return 0

    hata = 0
    for i, d in enumerate(docs, 1):
        try:
            # index_document chunk_id'leri deterministik ürettiği (docid_cNNNN)
            # ve ON CONFLICT ... DO UPDATE kullandığı için eski satırlar yerinde
            # güncellenir; embedding'ler anonim metinden yeniden üretilir.
            n = index_document(
                str(d["tenant_id"]), str(d["id"]), d["cleaned_text"],
                metadata={
                    "title": d["title"] or "",
                    "doc_type": d["document_type"] or "",
                    "case_no": d["case_no"] or "",
                    "court": d["court"] or "",
                },
            )
            log.info("[%d/%d] %s → %d chunk", i, len(docs), d["id"], n)
        except Exception:
            hata += 1
            log.exception("[%d/%d] %s BAŞARISIZ", i, len(docs), d["id"])

    log.info("Bitti. Başarılı: %d, hatalı: %d", len(docs) - hata, hata)
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
