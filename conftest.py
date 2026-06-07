"""Pytest global yapılandırma.

- Proje kökünü sys.path'e ekler.
- Şifreleme testleri için sabit bir test master key set eder (gerçek bir sır
  DEĞİLDİR; yalnızca testlerde kullanılır). encryption modülü master key'i import
  anında okuduğu için bu, herhangi bir test importundan ÖNCE yapılmalıdır —
  conftest.py pytest tarafından en önce yüklenir.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 32 byte ("0"*32) base64 — yalnızca test amaçlı.
os.environ.setdefault(
    "MASTER_ENCRYPTION_KEY",
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
)
