"""common/job_queue.py — retry üst sınırı.

Eskiden `mark_failed(retry=True)` attempts sayacını artırıyor ama hiçbir yerde
üst sınır kontrol edilmiyordu. Kaynak site bir kayıt için kalıcı olarak boş
yanıt döndürdüğünde (içerik kaldırılmış) o iş sonsuza dek pending ↔ in_progress
arasında dönüyor, kuyruk hiç boşalmıyordu.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from common.job_queue import DEFAULT_MAX_ATTEMPTS, JobQueue


def _kuyruk(tmp: str, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> JobQueue:
    return JobQueue(Path(tmp) / "jobs.db", max_attempts=max_attempts)


def test_max_attempts_asilinca_kalici_failed():
    with tempfile.TemporaryDirectory() as tmp:
        q = _kuyruk(tmp, max_attempts=3)
        q.add("j1", "yargitay", {"url": "x"})

        assert q.claim_batch("yargitay", 5)
        assert q.mark_failed("j1", "bos yanit", retry=True) == "pending"
        assert q.claim_batch("yargitay", 5)
        assert q.mark_failed("j1", "bos yanit", retry=True) == "pending"
        assert q.claim_batch("yargitay", 5)
        # 3. deneme → sınır doldu
        assert q.mark_failed("j1", "bos yanit", retry=True) == "failed"

        # Artık claim edilmiyor: kuyruk sonsuz döngüye girmez.
        assert q.claim_batch("yargitay", 5) == []


def test_retry_false_hemen_failed():
    with tempfile.TemporaryDirectory() as tmp:
        q = _kuyruk(tmp)
        q.add("j1", "aym", {})
        q.claim_batch("aym", 1)
        assert q.mark_failed("j1", "kalici hata", retry=False) == "failed"
        assert q.claim_batch("aym", 1) == []


def test_sinir_altinda_yeniden_denenebilir():
    with tempfile.TemporaryDirectory() as tmp:
        q = _kuyruk(tmp, max_attempts=5)
        q.add("j1", "danistay", {})
        for _ in range(4):
            q.claim_batch("danistay", 1)
            assert q.mark_failed("j1", "429", retry=True) == "pending"
        assert len(q.claim_batch("danistay", 1)) == 1


def test_son_hata_mesaji_sinir_bilgisini_icerir():
    with tempfile.TemporaryDirectory() as tmp:
        q = _kuyruk(tmp, max_attempts=1)
        q.add("j1", "hudoc", {})
        q.claim_batch("hudoc", 1)
        q.mark_failed("j1", "bos", retry=True)
        with q._conn() as c:
            row = c.execute("SELECT last_error, attempts FROM jobs WHERE id='j1'").fetchone()
        assert "max_attempts" in row["last_error"]
        assert row["attempts"] == 1


def test_reset_source_sayaci_sifirlar():
    """Scraper düzeltildikten sonra elle kurtarma: tükenmiş işler yeniden
    denenebilmeli, yoksa tek denemede tekrar 'failed' olurlardı."""
    with tempfile.TemporaryDirectory() as tmp:
        q = _kuyruk(tmp, max_attempts=2)
        q.add("j1", "yargitay", {})
        q.claim_batch("yargitay", 1)
        q.mark_failed("j1", "e", retry=True)
        q.claim_batch("yargitay", 1)
        assert q.mark_failed("j1", "e", retry=True) == "failed"

        q.reset_source("yargitay")
        assert len(q.claim_batch("yargitay", 1)) == 1
        with q._conn() as c:
            assert c.execute("SELECT attempts FROM jobs WHERE id='j1'").fetchone()[0] == 0


def test_max_attempts_en_az_bir():
    with tempfile.TemporaryDirectory() as tmp:
        assert _kuyruk(tmp, max_attempts=0).max_attempts == 1
