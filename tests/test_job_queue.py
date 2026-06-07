"""job_queue.py birim testleri."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.job_queue import JobQueue


def test_add_and_claim():
    with tempfile.TemporaryDirectory() as d:
        q = JobQueue(Path(d) / "q.db")
        q.add("a", "test", {"k": 1})
        q.add("b", "test", {"k": 2})

        batch = q.claim_batch("test", n=5)
        assert len(batch) == 2
        ids = {b["id"] for b in batch}
        assert ids == {"a", "b"}


def test_idempotent_add():
    with tempfile.TemporaryDirectory() as d:
        q = JobQueue(Path(d) / "q.db")
        q.add("a", "test", {"k": 1})
        q.add("a", "test", {"k": 999})  # aynı id
        s = q.stats("test")
        assert s.get("pending") == 1


def test_mark_done():
    with tempfile.TemporaryDirectory() as d:
        q = JobQueue(Path(d) / "q.db")
        q.add("a", "test", {})
        q.claim_batch("test")
        q.mark_done("a")
        s = q.stats("test")
        assert s.get("done") == 1


def test_mark_failed_retry():
    with tempfile.TemporaryDirectory() as d:
        q = JobQueue(Path(d) / "q.db")
        q.add("a", "test", {})
        q.claim_batch("test")
        q.mark_failed("a", "boom", retry=True)
        s = q.stats("test")
        assert s.get("pending") == 1


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
