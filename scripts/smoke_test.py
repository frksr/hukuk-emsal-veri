"""Tüm scraper modüllerinin import edilebildiğini ve sözdizimsel olarak
sağlam olduğunu doğrular. Network gerektirmez."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

modules = [
    "common.normalize",
    "common.anonymize",
    "common.http_client",
    "common.job_queue",
    "scrapers.base",
    "scrapers.hudoc",
    "scrapers.aym",
    "scrapers.danistay",
    "scrapers.yargitay",
    "pipelines.export_final",
]

failed = 0
for m in modules:
    try:
        __import__(m)
        print(f"  OK   {m}")
    except Exception as e:
        print(f"  FAIL {m}: {e}")
        failed += 1

# Class instantiation test — Windows'ta SQLite file lock için ignore_cleanup_errors
try:
    from scrapers.hudoc import HudocScraper
    from scrapers.aym import AymScraper
    from scrapers.danistay import DanistayScraper
    from scrapers.yargitay import YargitayScraper

    # Python 3.10+ ignore_cleanup_errors destekler — Windows file lock için kritik
    kwargs = {}
    if sys.version_info >= (3, 10):
        kwargs["ignore_cleanup_errors"] = True

    with tempfile.TemporaryDirectory(**kwargs) as d:
        for cls in (HudocScraper, AymScraper, DanistayScraper, YargitayScraper):
            inst = cls(root=d)
            # JobQueue varsa SQLite bağlantısını serbest bırakmak için del
            if hasattr(inst, "queue"):
                del inst.queue
            del inst
        print(f"  OK   scraper instantiation ({d})")

    # Windows'ta SQLite handle release için kısa pause + garbage collection
    import gc
    gc.collect()

except Exception as e:
    print(f"  FAIL scraper instantiation: {e}")
    failed += 1

print(f"\n{'-'*40}")
print(f"{'PASSED' if failed == 0 else f'{failed} FAILED'}")
sys.exit(0 if failed == 0 else 1)
