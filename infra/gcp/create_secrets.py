"""
Secret Manager'da 20 secret'i tek seferde olusturur (satir-sonu EKLEMEDEN).

KULLANIM (cmd):
    1) Asagidaki "DOLDUR" alanlarini kendi degerinle degistir.
    2) python infra\\gcp\\create_secrets.py

Not: Degerler stdin uzerinden gcloud'a verilir -> cmd tirnak/ozel-karakter derdi YOK.
     NEXTAUTH_SECRET / MASTER_ENCRYPTION_KEY bos birakilirsa otomatik uretilir.
     Bir secret zaten varsa yeni SURUM eklenir (mevcut bozulmaz).
"""
import subprocess, secrets, sys

# ---- Sabitler (loglardan dogrulandi; degistirmene gerek yok) ----------------
PROJECT = "project-ab3f52ab-045e-4f39-9f1"
CONN    = "project-ab3f52ab-045e-4f39-9f1:europe-west1:hukuk-emsal"
DB      = "hukuk-emsal-db"

# ---- DB kullanicilari + parolalari (DOLDUR) ---------------------------------
OWNER_USER = "hukuk"          # Cloud SQL owner rol adi
OWNER_PW   = "DOLDUR"         # <-- owner parolasi
APP_USER   = "app_user"       # request-scope rol
APP_PW     = "DOLDUR"         # <-- app_user parolasi

# ---- Secret degerleri -------------------------------------------------------
VALUES = {
    # DB DSN'leri (otomatik kurulur; parolalar yukaridan gelir)
    "DATABASE_URL":         f"postgresql://{APP_USER}:{APP_PW}@/{DB}?host=/cloudsql/{CONN}",
    "SERVICE_DATABASE_URL": f"postgresql://{OWNER_USER}:{OWNER_PW}@/{DB}?host=/cloudsql/{CONN}",
    "ADMIN_DATABASE_URL":   f"postgresql://{OWNER_USER}:{OWNER_PW}@/{DB}?host=/cloudsql/{CONN}",

    # Bos birak -> otomatik uretilir
    "NEXTAUTH_SECRET":       "",
    "MASTER_ENCRYPTION_KEY": "",

    # LLM (DOLDUR)
    "ANTHROPIC_API_KEY": "DOLDUR",
    "GOOGLE_API_KEY":    "DOLDUR",

    # iyzico (gercek degerin yoksa simdilik placeholder birak -> deploy dusmez)
    "IYZICO_API_KEY":        "placeholder",
    "IYZICO_SECRET_KEY":     "placeholder",
    "IYZICO_WEBHOOK_SECRET": "placeholder",
    "IYZICO_PLAN_PRO_SOLO":  "placeholder",
    "IYZICO_PLAN_PRO_UYAP":  "placeholder",
    "IYZICO_PLAN_TEAM":      "placeholder",
    "IYZICO_PLAN_TEAM_UYAP": "placeholder",

    # SMTP / e-posta
    "SMTP_HOST":  "placeholder",
    "SMTP_PORT":  "587",
    "SMTP_USER":  "placeholder",
    "SMTP_PASS":  "placeholder",
    "SMTP_FROM":  "no-reply@hukukcuyapayzekasi.com",
    "ADMIN_EMAIL": "admin@hukukcuyapayzekasi.com",
}

# ---- Otomatik uret ----------------------------------------------------------
for k in ("NEXTAUTH_SECRET", "MASTER_ENCRYPTION_KEY"):
    if not VALUES[k]:
        VALUES[k] = secrets.token_urlsafe(32)

# ---- DOLDUR kalmis mi kontrol ----------------------------------------------
eksik = [k for k, v in VALUES.items() if v == "DOLDUR" or "DOLDUR" in v]
if eksik:
    print("HATA: su alanlar hala DOLDUR:", ", ".join(eksik))
    print("Once script icindeki DOLDUR yerlerini doldur (en azindan DB parolalari + API anahtarlari).")
    sys.exit(1)

def exists(name):
    return subprocess.run(
        f'gcloud secrets describe {name} --project {PROJECT}',
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0

ok = 0
for name, val in VALUES.items():
    if exists(name):
        cmd = f'gcloud secrets versions add {name} --data-file=- --project {PROJECT}'
        action = "surum eklendi"
    else:
        cmd = f'gcloud secrets create {name} --data-file=- --project {PROJECT}'
        action = "olusturuldu"
    r = subprocess.run(cmd, shell=True, input=val.encode("utf-8"),
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode == 0:
        print(f"OK   {name} ({action})"); ok += 1
    else:
        print(f"HATA {name}: {r.stderr.decode(errors='ignore').strip()[:200]}")

print(f"\nBitti: {ok}/{len(VALUES)} secret hazir.")
