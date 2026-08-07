"""SQLite tabanlı resumable iş kuyruğu."""
import sqlite3
import json
import time
from pathlib import Path


#: Bir iş kaç kez denendikten sonra kalıcı olarak 'failed' sayılır.
DEFAULT_MAX_ATTEMPTS = 5


class JobQueue:
    def __init__(self, db_path: str | Path, max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        self.db_path = Path(db_path)
        self.max_attempts = max(1, int(max_attempts))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_schema(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(source, status);
            """)

    def add(self, job_id: str, source: str, payload: dict):
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO jobs(id, source, payload, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, source, json.dumps(payload), now, now),
            )

    def claim_batch(self, source: str, n: int = 10) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, payload FROM jobs WHERE source=? AND status='pending' "
                "ORDER BY created_at LIMIT ?",
                (source, n),
            ).fetchall()
            ids = [r["id"] for r in rows]
            if ids:
                c.executemany(
                    "UPDATE jobs SET status='in_progress', updated_at=? WHERE id=?",
                    [(time.time(), i) for i in ids],
                )
            return [{"id": r["id"], "payload": json.loads(r["payload"])} for r in rows]

    def mark_done(self, job_id: str):
        with self._conn() as c:
            c.execute(
                "UPDATE jobs SET status='done', updated_at=? WHERE id=?",
                (time.time(), job_id),
            )

    def mark_failed(self, job_id: str, error: str, retry: bool = True) -> str:
        """İşi başarısız işaretle. `retry=True` ise MAX_ATTEMPTS'e kadar
        yeniden kuyruğa alır, sonra kalıcı olarak 'failed' yapar.

        Üst sınır olmadan: kaynak site bir kayıt için kalıcı olarak boş/hatalı
        yanıt döndürdüğünde (içerik kaldırılmış olabilir) o iş sonsuza dek
        pending ↔ in_progress arasında dönüyor, kuyruk hiç boşalmıyordu.

        Returns: işin yeni durumu ("pending" | "failed").
        """
        with self._conn() as c:
            row = c.execute(
                "SELECT attempts FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            attempts = (row["attempts"] if row else 0) + 1
            exhausted = attempts >= self.max_attempts
            new_status = "pending" if (retry and not exhausted) else "failed"
            if retry and exhausted:
                error = f"[max_attempts={self.max_attempts} aşıldı] {error}"
            c.execute(
                "UPDATE jobs SET status=?, attempts=?, last_error=?, updated_at=? "
                "WHERE id=?",
                (new_status, attempts, error[:500], time.time(), job_id),
            )
            return new_status

    def reset_source(self, source: str):
        """Bir kaynağın tüm in_progress/failed job'larını pending'e döndür.

        Elle yapılan bir kurtarma işlemidir (ör. scraper düzeltildikten sonra):
        deneme sayacı da sıfırlanır, aksi halde max_attempts'i tüketmiş işler
        tek denemede tekrar 'failed' olurdu.
        """
        with self._conn() as c:
            c.execute(
                "UPDATE jobs SET status='pending', attempts=0, updated_at=? "
                "WHERE source=? AND status IN ('in_progress', 'failed')",
                (time.time(), source),
            )

    def clear_source(self, source: str):
        """Bir kaynağın tüm job'larını sil."""
        with self._conn() as c:
            c.execute("DELETE FROM jobs WHERE source=?", (source,))

    def stats(self, source: str | None = None) -> dict:
        with self._conn() as c:
            if source:
                rows = c.execute(
                    "SELECT status, COUNT(*) c FROM jobs WHERE source=? GROUP BY status",
                    (source,),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT source||':'||status k, COUNT(*) c FROM jobs GROUP BY k"
                ).fetchall()
            return {r[0]: r[1] for r in rows}
