"""Kalıcı volume'u public vektör DB (+ opsiyonel parquet) ile seed et.

Cloud kurulumu: kod git'ten gelir, BÜYÜK veri (data/chroma_db ~2GB) ise kalıcı
volume'a bir KEZ seed edilir. Bu script o tek seferlik kopyalamayı yapar ve
idempotenttir (zaten doluysa atlar).

Hedef yol CHROMA_DIR env'inden okunur (rag.py ile aynı). Volume'u oraya
mount edin, ör. /data/chroma_db.

Kaynak (--source) üç biçimde olabilir:
  * dizin            → içeriği hedefe kopyalanır
  * .tgz/.tar.gz/.tar→ hedefin ÜST dizinine açılır (tarball `chroma_db/...`
                       içermeli: `tar czf chroma_db.tgz -C data chroma_db`)
  * http(s) URL      → indirilip açılır (tek seferlik transfer; veri yine
                       volume'da kalır)

Örnekler:
  # Fly: önce tarball'ı volume'a yükle (fly sftp put), sonra makinede:
  CHROMA_DIR=/data/chroma_db python -m scripts.seed_volume --source /data/chroma_db.tgz

  # Herhangi bir platform: bir URL'den (presigned S3/R2 vb.) tek seferlik:
  CHROMA_DIR=/data/chroma_db python -m scripts.seed_volume --source https://.../chroma_db.tgz

  # Lokal: mount edilmiş volume'a dizinden kopyala
  CHROMA_DIR=/mnt/vol/chroma_db python -m scripts.seed_volume --source ./data/chroma_db
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_TARGET = os.environ.get("CHROMA_DIR", "data/chroma_db")


def _is_seeded(target: Path) -> bool:
    # Chroma persist dizini chroma.sqlite3 içerir.
    return (target / "chroma.sqlite3").exists()


def _download(url: str, dest: Path) -> None:
    print(f"[seed] indiriliyor: {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _extract_tar(archive: Path, target: Path) -> None:
    # Tarball `chroma_db/...` içerdiği için hedefin ÜST dizinine açıyoruz.
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    print(f"[seed] açılıyor: {archive} → {parent}", file=sys.stderr)
    with tarfile.open(archive) as tf:
        # Path traversal koruması
        for m in tf.getmembers():
            mp = (parent / m.name).resolve()
            if not str(mp).startswith(str(parent.resolve())):
                raise RuntimeError(f"Güvensiz tar girdisi: {m.name}")
        tf.extractall(parent)


def seed(source: str, target: Path, force: bool) -> int:
    if _is_seeded(target) and not force:
        print(f"[seed] hedef zaten dolu, atlanıyor: {target} (--force ile üzerine yaz)")
        return 0

    if force and target.exists():
        shutil.rmtree(target)

    tmp = None
    try:
        src_path = Path(source)
        is_url = source.startswith("http://") or source.startswith("https://")
        is_tar = source.endswith((".tgz", ".tar.gz", ".tar"))

        if is_url:
            tmp = Path(tempfile.mkdtemp()) / "archive.tgz"
            _download(source, tmp)
            _extract_tar(tmp, target)
        elif is_tar:
            _extract_tar(src_path, target)
        elif src_path.is_dir():
            print(f"[seed] kopyalanıyor: {src_path} → {target}", file=sys.stderr)
            shutil.copytree(src_path, target, dirs_exist_ok=True)
        else:
            print(f"[seed] HATA: kaynak bulunamadı/desteklenmiyor: {source}", file=sys.stderr)
            return 2
    finally:
        if tmp and tmp.parent.exists():
            shutil.rmtree(tmp.parent, ignore_errors=True)

    if not _is_seeded(target):
        print(f"[seed] HATA: seed sonrası {target}/chroma.sqlite3 yok — kaynağı kontrol edin.",
              file=sys.stderr)
        return 3
    print(f"[seed] OK tamam: {target}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Volume'u public vektör DB ile seed et")
    p.add_argument("--source", required=True, help="dizin | .tgz | http(s) URL")
    p.add_argument("--target", default=DEFAULT_TARGET, help="hedef (varsayılan: CHROMA_DIR)")
    p.add_argument("--force", action="store_true", help="hedef doluysa üzerine yaz")
    args = p.parse_args()
    raise SystemExit(seed(args.source, Path(args.target), args.force))


if __name__ == "__main__":
    main()
