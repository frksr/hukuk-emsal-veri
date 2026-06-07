# Hukuk Emsal — Local Development Setup

Tek bir terminalden tüm sistemi ayağa kaldırmak için adım adım rehber.

**Tahmini süre:** 15-20 dakika

---

## ✅ Otomatik üretilmiş ve hazır

Senin için bu turda hazırlanan:

| Dosya | İçerik |
|---|---|
| `docker-compose.yml` | Postgres 16 + Mailpit (SMTP) + Redis container'ları |
| `.env` | Backend env — keyler üretildi, iyzico sandbox key konuldu |
| `web/.env.local` | Frontend env — backend ile uyumlu |
| `scripts/setup_iyzico_plans.py` | iyzico'da 4 ürün/plan otomatik oluştur |
| `scripts/init_db.py` | Tüm migration'ları sırayla uygular |
| `scripts/create_admin.py` | Sana admin hesap açar |

**Üretilen keyler (.env'de hazır):**
- `MASTER_ENCRYPTION_KEY` = `PkzWD0P3DJJFy4rL6JBxooFR45sonYpD0rP0nQouyQE=`
- `NEXTAUTH_SECRET` = `wCHt67Bqf2BswRCrihdZv9a9q2k7qpY+MyQevuDon2o=`
- `POSTGRES_PASSWORD` = `wHV3ftf+g4+B6EXjASZaRIvBD9C0soGn`

---

## 🛠️ Adım 1 — Senin ekleyeceğin tek şey

`.env` dosyasını aç, **Anthropic ve Gemini API key'lerini** yapıştır:

```bash
ANTHROPIC_API_KEY=sk-ant-...   # ← sen ekleyeceksin
GOOGLE_API_KEY=AIza...          # ← sen ekleyeceksin
```

Geri kalan her şey hazır.

---

## 🐳 Adım 2 — Docker container'ları başlat

```bash
cd C:\Users\mnara\OneDrive\Desktop\project\ai-projects\hukuk-emsal-veri
docker compose up -d
```

Beklenen çıktı:
```
✓ Container hukuk-pg       Started
✓ Container hukuk-mailpit  Started
✓ Container hukuk-redis    Started
```

**Test:**
- Postgres: `docker compose ps postgres` → `healthy`
- Mailpit web UI: <http://localhost:8025> (e-mailleri buradan göreceksin)
- Postgres bağlantı: `docker exec -it hukuk-pg psql -U hukuk -d hukuk_emsal -c '\dt'`

---

## 📋 Adım 3 — Python bağımlılıklarını yükle

```bash
pip install -r requirements.txt
```

Yeni eklenenler: `asyncpg`, `pyjwt`, `bcrypt`, `cryptography`, `aiosmtplib`, `python-dotenv`

---

## 🗄️ Adım 4 — Database migration'ları uygula

```bash
python scripts/init_db.py
```

Beklenen çıktı:
```
✓ 01_init.sql
✓ 02_rls.sql
✓ 03_seed.sql
✓ 04_migration_002.sql
✓ 05_migration_003.sql
✓ 06_migration_004.sql
✓ 6/6 migration uygulandı.
```

**Sorun çıkarsa:** `python scripts/init_db.py --reset` (DİKKAT: tüm veri silinir)

---

## 👤 Adım 5 — Admin hesabı aç

```bash
python scripts/create_admin.py --email senin@email.com --password "GüçlüŞifre123" --name "Senin Adın"
```

Beklenen:
```
✓ Admin oluşturuldu: senin@email.com
  Tenant ID: ... (Enterprise plan)
```

---

## 💳 Adım 6 — iyzico ürün/plan kurulumu

```bash
python scripts/setup_iyzico_plans.py
```

Çıktı şuna benzer olacak:
```
→ 'Pro Solo' (₺499/ay)
  ✓ Ürün oluşturuldu: abc-123
  ✓ Pricing plan: def-456
...

.env DOSYASINA EKLENECEK:
IYZICO_PLAN_PRO_SOLO=def-456
IYZICO_PLAN_PRO_UYAP=...
IYZICO_PLAN_TEAM=...
IYZICO_PLAN_TEAM_UYAP=...
```

**Çıktıdaki 4 satırı `.env` dosyasındaki ilgili yerlere yapıştır.**

---

## 🚀 Adım 7 — Backend'i başlat

```bash
uvicorn api.main:app --reload --port 8000
```

Beklenen log:
```
INFO: API başlatılıyor...
INFO: Postgres pool hazır
INFO: RAG model + Chroma yüklendi
INFO: Uvicorn running on http://0.0.0.0:8000
```

**Test:** Tarayıcıda <http://localhost:8000/api/health> → JSON yanıt
**OpenAPI:** <http://localhost:8000/api/docs>

---

## 🎨 Adım 8 — Frontend'i başlat

Yeni terminal:

```bash
cd web
npm install
npm run dev
```

Beklenen:
```
✓ Ready in 3.2s
○ Local:   http://localhost:3000
```

---

## ✅ Adım 9 — End-to-End Smoke Test

Tarayıcıda sırayla:

1. <http://localhost:3000> → Anasayfa açılıyor mu? ✓
2. <http://localhost:3000/emsal-arama> → "icra takibi emekli maaşı" sorusu, 5 emsal gelmeli ✓
3. <http://localhost:3000/giris> → senin@email.com + şifren ile giriş
4. <http://localhost:3000/app> → dashboard açılır
5. <http://localhost:3000/app/admin> → admin panel (sadece sen)
6. <http://localhost:3000/app/dosyalar> → "Pro Plan gerekli" uyarısı (Enterprise tenant'ın olduğu için bu açılmalı)
7. Sağ altta 💬 widget → "Test feedback" gönder → <http://localhost:8025>'te email kontrolü değil ama `/app/admin/feedback`'te görmeli

---

## 🐛 Sık karşılaşılan sorunlar

### Backend "DATABASE_URL eksik"
.env dosyası okunmuyor. `pip install python-dotenv` ve `uvicorn` çağrısını proje root'unda çalıştır.

### Postgres bağlantı reddedildi
Docker container başlamamış: `docker compose up -d postgres`. Veya port çakışması: 5432 portu başka serviste mi?

### Next.js "Module not found: pg"
`cd web && npm install` çalıştır, `pg` ve `bcrypt` paketleri kurulu olmalı.

### iyzico "API key invalid"
.env'de IYZICO_API_KEY'e sandbox key doğru yapıştırıldı mı? Boşluk yok mu?

### LLM özelikleri "API key eksik"
.env'de ANTHROPIC_API_KEY veya GOOGLE_API_KEY ekledin mi?

---

## 📧 E-mailleri görme

Mailpit local SMTP çalışıyor — sistem e-mail gönderince (welcome, şifre sıfırlama, beta davet) burada görürsün:

**<http://localhost:8025>**

Production'da Resend/Postmark gibi gerçek SMTP servisine geçeceksin.

---

## 🎯 Sonraki adım — Beta avukat davet

1. <http://localhost:3000/app/admin> → Beta sekmesi
2. Bir avukatın e-postasını yaz → davetiye gönder
3. Mailpit'te (<http://localhost:8025>) maili gör
4. Production'a deploy ettiğinde gerçek e-postalar gönderilir

---

## 🛑 Container'ları durdurmak için

```bash
docker compose down          # durdur ama veriyi tut
docker compose down -v       # durdur ve TÜM VERİYİ SİL
```
