# Hukuk Emsal — Detaylı Test Planı

Bu doküman, local development ortamında sistemin **tamamının** end-to-end test edilmesi için adım adım yapılması gerekenleri içerir. Her bölüm bağımsız çalıştırılabilir — bir alanda sorun çıkarsa o alana odaklan, diğerleri etkilenmez.

**Test ortamı:** Local Docker Compose (Postgres + Mailpit) + Python backend + Next.js frontend
**Tahmini toplam süre:** 60–90 dakika (ilk turda)
**Risk seviyeleri:** 🟢 Düşük | 🟡 Orta | 🔴 Kritik (release-blocker)

---

## 0. Ön Hazırlık (5 dk)

### 0.1 Dosya kontrolü
| Kontrol | Beklenen | Komut |
|---|---|---|
| `.env` mevcut | ✓ | `Test-Path .env` |
| `ANTHROPIC_API_KEY` dolu | ✓ | `Select-String "ANTHROPIC_API_KEY=sk-" .env` |
| `GOOGLE_API_KEY` dolu | ✓ | `Select-String "GOOGLE_API_KEY=AIza" .env` |
| Docker Desktop açık | ✓ | `docker version` |
| Python 3.11+ | ✓ | `python --version` |
| Node 18+ | ✓ | `node --version` |

### 0.2 Port çakışma kontrolü
Aşağıdaki portlar boş olmalı (process listeniyor olmamalı):
- **5432** → Postgres
- **1026** → Mailpit SMTP (host)
- **8025** → Mailpit Web UI
- **8000** → Backend (FastAPI)
- **3000** → Frontend (Next.js)

```powershell
netstat -ano | findstr ":5432 :1026 :8025 :8000 :3000"
```

---

## 1. Altyapı (Infrastructure) Testleri 🔴

### 1.1 Docker container'ları başlat
```bash
docker compose down
docker compose up -d
docker compose ps
```

**Beklenen:**
- `hukuk-pg` → `running (healthy)`
- `hukuk-mailpit` → `running`
- Hata satırı yok.

**Negatif kontrol:** Yanlış env ile başlat → fail beklenir.

### 1.2 Postgres bağlanılabilirlik
```bash
docker exec -it hukuk-pg psql -U hukuk -d hukuk_emsal -c "SELECT version();"
```
**Beklenen:** `PostgreSQL 16.x ...` satırı.

### 1.3 Mailpit Web UI
- Tarayıcı → http://localhost:8025
- **Beklenen:** Mailpit arayüzü, boş inbox.

### 1.4 Healthcheck periyodik kontrol
```bash
docker inspect --format='{{.State.Health.Status}}' hukuk-pg
```
**Beklenen:** `healthy` (30 sn içinde).

---

## 2. Database & Migration Testleri 🔴

### 2.1 Migration uygulama
```bash
python scripts/init_db.py
```
**Beklenen çıktı:** 6/6 migration ✓.

**Kontroller:**
| Tablo | Var olmalı | Satır sayısı (fresh install) |
|---|---|---|
| `users` | ✓ | 0 |
| `tenants` | ✓ | 0 |
| `tenant_members` | ✓ | 0 |
| `subscriptions` | ✓ | 0 |
| `payments` | ✓ | 0 |
| `usage_events` | ✓ | 0 |
| `user_searches` | ✓ | 0 |
| `tenant_documents` | ✓ | 0 |
| `audit_log` | ✓ | 0 |
| `feedback` | ✓ | 0 |
| `beta_program` | ✓ | 0 |
| `scheduled_emails` | ✓ | 0 |
| `webhook_events` | ✓ | 0 |
| `accounts`, `sessions` (NextAuth) | ✓ | 0 |

### 2.2 RLS (Row-Level Security) aktif mi?
```sql
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = true;
```
**Beklenen:** `tenant_documents`, `tenant_members`, `tenant_queries`, `usage_events` listede.

### 2.3 Migration idempotency
```bash
python scripts/init_db.py
```
**Beklenen:** Hata yok, sadece "atlandı" mesajları. Tekrar çalıştırılması veriye zarar VERMEMELİ.

### 2.4 Reset testi (opsiyonel, dikkatli)
```bash
python scripts/init_db.py --reset
```
"SIL" yazılırsa → tüm tablolar yeniden kurulmalı.

---

## 3. Admin Kullanıcı & Tenant Testleri 🔴

### 3.1 Admin oluşturma
```bash
python scripts/create_admin.py --email admin@hukukemsal.local --password "Test1234!" --name "Test Admin"
```
**Beklenen:**
- `✓ Admin oluşturuldu: admin@hukukemsal.local`
- User ID + Tenant ID (Enterprise plan) ekrana basılır.

### 3.2 DB'de doğrulama
```sql
SELECT id, email, role, is_active FROM users WHERE email='admin@hukukemsal.local';
SELECT t.name, t.plan_tier, tm.role FROM tenants t
  JOIN tenant_members tm ON tm.tenant_id = t.id
  WHERE tm.user_id = (SELECT id FROM users WHERE email='admin@hukukemsal.local');
```
**Beklenen:** `role=admin`, `plan_tier=enterprise`, `tm.role=owner`.

### 3.3 Şifre doğrulama
- bcrypt hash uzunluğu ~60 karakter olmalı.
- Aynı password'ü tekrar hash'lemek farklı hash üretmeli (salt).

### 3.4 Promote akışı
```bash
python scripts/create_admin.py --promote some-existing@email.com
```
**Beklenen:** Var olan user için `role='admin'` set edilmeli, olmayanlar için "bulunamadı" mesajı.

---

## 4. iyzico Setup Testleri 🟡

### 4.1 Sandbox ürün/plan oluşturma
```bash
python scripts/setup_iyzico_plans.py
```
**Beklenen:** 4 ürün + 4 plan oluşturulmuş, çıktı:
```
IYZICO_PLAN_PRO_SOLO=<uuid>
IYZICO_PLAN_PRO_UYAP=<uuid>
IYZICO_PLAN_TEAM=<uuid>
IYZICO_PLAN_TEAM_UYAP=<uuid>
```

### 4.2 .env güncelleme
Yukarıdaki 4 satır `.env`'ye yapıştırılmalı.

### 4.3 iyzico Sandbox panelinde görsel doğrulama
- https://sandbox-merchant.iyzipay.com'a girip ürünleri gör.

### 4.4 Hata senaryoları
- Yanlış API key → 401 dönmeli, script anlamlı hata vermeli.
- Network kopukluğu → timeout handling çalışmalı.

---

## 5. Backend API Testleri 🔴

### 5.1 Başlatma
```bash
uvicorn api.main:app --reload --port 8000
```
**Beklenen log:**
```
INFO: Postgres pool hazır
INFO: RAG model + Chroma yüklendi (xxx chunks)
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 5.2 Health endpoint
```bash
curl http://localhost:8000/api/health
```
**Beklenen:** `{"status":"ok","db":"ok","chroma":"ok"}`

### 5.3 OpenAPI docs
- http://localhost:8000/api/docs → Swagger UI tüm endpointleri göstermeli.

### 5.4 Endpoint coverage (her birinin 200/auth doğru çalışıyor mu)

| Router | Endpoint | Method | Auth Gerekli | Test |
|---|---|---|---|---|
| `arama` | `/api/arama` | POST | Hayır (rate-limit) | "icra takibi emekli maaşı" → ≥5 sonuç |
| `dilekce` | `/api/dilekce/generate` | POST | Evet (free: 3/ay) | "Borçluya icra emri" prompt |
| `ozet` | `/api/ozet` | POST | Evet | URL ya da metin → özet |
| `faiz` | `/api/faiz/calc` | POST | Hayır | TL 10000, 2023-01-01 → 2025-01-01 |
| `zamanasimi` | `/api/zamanasimi/check` | POST | Hayır | Olay tarihi + kategori |
| `ihtarname` | `/api/ihtarname` | POST | Evet | Şablondan ihtarname üret |
| `trend` | `/api/trend` | GET | Hayır | Karar trendleri JSON |
| `karsi_argument` | `/api/karsi-argument` | POST | Evet | Argüman → karşıt argüman |
| `kvkk` | `/api/kvkk/check` | POST | Evet | Metinde PII tespiti |
| `sozlesme` | `/api/sozlesme/analiz` | POST | Evet (Pro) | Sözleşme metni → risk raporu |
| `denetim` | `/api/denetim` | POST | Evet (Pro) | Belge denetimi |
| `me` | `/api/me` | GET | Evet | Kullanıcı bilgisi |
| `auth_actions` | `/api/auth/register` | POST | Hayır | Yeni hesap |
| `auth_actions` | `/api/auth/login` | POST | Hayır | JWT döner |
| `auth_actions` | `/api/auth/forgot-password` | POST | Hayır | Mailpit'e e-mail |
| `billing` | `/api/billing/subscribe` | POST | Evet | iyzico checkout URL |
| `billing` | `/api/billing/webhook` | POST | Hayır (sign) | iyzico imzalı webhook |
| `uyap` | `/api/uyap/upload` | POST | Evet (Pro UYAP) | UYAP dosyası |
| `admin` | `/api/admin/users` | GET | Evet (admin) | Tüm kullanıcılar |
| `feedback` | `/api/feedback` | POST | Evet | Geri bildirim |

### 5.5 Auth zorlaması
- Auth gerektiren endpoint'i token'sız çağır → **401**.
- Yanlış token → **401**.
- Süresi dolmuş token → **401**.
- Doğru token ama yetkisiz endpoint → **403**.

### 5.6 Rate limit
```bash
# 25 kez ardışık emsal arama (free tier 20/ay)
for i in {1..25}; do curl -X POST .../api/arama; done
```
**Beklenen:** 21. istekten itibaren `429 Too Many Requests`.

### 5.7 Hata yönetimi
- Boş body → 422
- Geçersiz tarih formatı → 400 + anlamlı mesaj
- DB down → 503 (graceful)

---

## 6. Frontend Testleri 🔴

### 6.1 Başlatma
```bash
cd web && npm install && npm run dev
```
**Beklenen:** `Ready in <5s`, `Local: http://localhost:3000`

### 6.2 Public sayfalar (auth gerektirmeyen) 🟢
| URL | Beklenen |
|---|---|
| `/` | Hero + CTA + 6 modül kartı |
| `/emsal-arama` | Arama kutusu çalışır, sonuçlar gelir |
| `/dilekce` | Login gate görünür |
| `/karar-ozet` | URL/metin girişi |
| `/faiz-hesaplayici` | Hesaplama çalışır |
| `/zamanasimi` | Sorgu + sonuç |
| `/ihtarname` | Login gate |
| `/trend` | Grafik render olur |
| `/karsi-argument` | Login gate |
| `/kvkk` | Genel bilgi sayfası |
| `/sozlesme-analizi` | Pro plan gate |
| `/belge-denetim` | Pro plan gate |
| `/giris` | Login formu |
| `/kayit` | Kayıt formu + KVKK onayı |
| `/sifre-sifirla` | Şifre sıfırlama formu |

### 6.3 SEO meta kontrolü 🟡
Her public sayfada:
- `<title>` 30–60 karakter, unique
- `<meta description>` 120–160 karakter
- Open Graph tags
- `lang="tr"`
- Canonical URL

```bash
curl -s http://localhost:3000/emsal-arama | grep -E '<title>|description|og:'
```

### 6.4 Lighthouse skorları 🟡
Hedef:
- **Performance** ≥ 85
- **Accessibility** ≥ 90
- **SEO** ≥ 95
- **Best Practices** ≥ 90

### 6.5 Responsive (mobil/tablet/desktop)
- 375px (iPhone SE)
- 768px (iPad)
- 1440px (desktop)

Navigasyon, formlar, tablolar bozulmamalı.

---

## 7. Authentication & Onboarding Akışı 🔴

### 7.1 Kayıt akışı
1. `/kayit` → form doldur (email, ad, şifre, KVKK onayı)
2. Submit → success mesajı
3. Mailpit (`http://localhost:8025`) → doğrulama e-postası
4. E-postadaki link → tıkla → `email_verified` set olmalı
5. Hoşgeldin sayfasına yönlendirme

### 7.2 Login akışı
1. `/giris` → admin@hukukemsal.local + şifre
2. NextAuth session cookie oluşmalı
3. `/app` dashboard açılmalı
4. Üst barda kullanıcı adı görünmeli

### 7.3 Logout
- Çıkış → cookie temizlenir, `/giris`'e yönlendirme.

### 7.4 Şifre sıfırlama
1. `/sifre-sifirla` → e-mail gir
2. Mailpit → reset link e-postası
3. Link → yeni şifre formu
4. Yeni şifre → login test

### 7.5 Session expiration
- Cookie süresi dolduktan sonra `/app` → `/giris`'e redirect.

### 7.6 Çoklu cihaz / çoklu sekme
- Aynı kullanıcı iki sekmede açık → session paylaşılır.
- Birinde logout → diğeri de etkilenmeli (refresh sonrası).

---

## 8. Modül Bazlı Fonksiyonel Testler 🔴

### 8.1 Emsal arama
| Test | Input | Beklenen |
|---|---|---|
| Basit arama | "icra takibi" | ≥5 sonuç, ilgili kararlar |
| Türkçe karakter | "İstanbul ihtiyati haciz" | Doğru eşleşme |
| Boş sorgu | "" | 400 ya da boş sonuç |
| Çok uzun (1000+ karakter) | lorem ipsum | Truncate edilip işlenmeli |
| Tarih filtresi | 2020-2022 | Sadece bu aralık |
| Daire filtresi | "12. Hukuk Dairesi" | Sadece o daire |
| Favori ekleme | sonucu favorile | `is_favorite=true` |
| Tag ekleme | tag ekle | `tags` array güncellenir |

### 8.2 Dilekçe üretimi
- Pro plan gate doğru çalışıyor mu?
- Free tier limit (3/ay) zorlanıyor mu?
- LLM cevabı 1000+ karakter, Türkçe, hukuk dili
- Word formatında indirilebilir mi?

### 8.3 Karar özetleme
- URL → fetch → özet
- Metin → özet
- 500'den uzun karar → kısaltma
- LLM provider fallback (Anthropic down → Gemini)

### 8.4 Faiz hesaplayıcı
| Test | Input | Beklenen |
|---|---|---|
| Yasal faiz | 10000 TL, 2023-01-01 → 2025-01-01 | Doğru hesap |
| Avans faizi | tutar + tarihler | Mevzuata uygun |
| Negatif tarih | bitiş < başlangıç | 400 |
| Sıfır tutar | 0 TL | 0 sonucu |

### 8.5 Zamanaşımı
- 10 yıllık icra zamanaşımı doğru
- 5 yıllık alacak doğru
- Kesilme/duraklama parametreleri

### 8.6 İhtarname
- Şablon seçimi (alacak, fesih, gecikme)
- Değişken alanlar (borçlu, alacaklı, tutar)
- PDF çıktısı

### 8.7 KVKK PII redaction
| Input | Beklenen |
|---|---|
| "TC: 12345678901" | `[TCKN]` |
| "IBAN: TR12 0006 ..." | `[IBAN]` |
| "0532 123 45 67" | `[PHONE]` |
| "test@example.com" | `[EMAIL]` |
| "Ali Veli adlı kişi" | İsim TESPİT edilmeli mi? (policy) |

### 8.8 Sözleşme analizi (Pro)
- Risk kategorileri (cezai şart, fesih, gizlilik)
- Maddeler arası çelişki tespiti
- Önerilen düzeltmeler

### 8.9 UYAP belge yükleme (Pro UYAP)
- .pdf, .docx, .uyap formatları
- Parser çalışıyor mu (tarafları, daire, tarih çıkarıyor mu)
- Per-tenant şifreleme: dosya disk'te encrypted olmalı

### 8.10 Karşı argüman
- Verilen argümana zıt 3 farklı yaklaşım
- Emsal karar referansı

### 8.11 Belge denetimi (Pro)
- Format kontrolü
- Eksik alan tespiti
- Önerilen iyileştirmeler

---

## 9. Multi-Tenancy & İzolasyon Testleri 🔴

### 9.1 İki tenant oluştur
```bash
python scripts/create_admin.py --email t1@test.local --password X --name "T1"
python scripts/create_admin.py --email t2@test.local --password X --name "T2"
```

### 9.2 İzolasyon kontrolleri
- T1 olarak login → belge yükle
- T2 olarak login → T1'in belgesi GÖRÜNMEMELİ
- T1'in query'si T2'ye sızmamalı
- Per-tenant Chroma collection'lar ayrı olmalı

### 9.3 RLS bypass testi
```sql
SET app.current_tenant_id = '<t1-id>';
SELECT * FROM tenant_documents;
-- Sadece T1 belgeleri gelmeli
```

### 9.4 Tenant_id leak audit
- API response'larında başka tenant'ın UUID'si yer almamalı
- Error mesajlarında tenant_id sızıntısı yok

---

## 10. Encryption & Security Testleri 🔴

### 10.1 Per-tenant encryption
- Belge yükle → disk'te ham metin GÖRÜNMEMELİ
- DB'de encrypted blob + nonce + tag
- Doğru key ile decrypt çalışır
- Yanlış key → AEAD doğrulama hatası

### 10.2 Master key rotation simülasyonu (manuel)
- MASTER_ENCRYPTION_KEY değiştir → eski verilere erişim DUR (beklenen davranış)

### 10.3 Cryptographic deletion (KVKK silme)
- Kullanıcı "tüm verilerimi sil" → tenant key silinir
- Encrypted veriler artık decrypt EDİLEMEZ
- Audit log kaydı kalır (tarih, kullanıcı, talep)

### 10.4 Password güvenliği
- bcrypt cost ≥ 12
- DB'de plain password YOK
- Login response'unda password_hash YOK

### 10.5 JWT güvenliği
- Token kısa ömürlü (≤24sa)
- HMAC imzası
- `alg=none` reddedilir
- Refresh token akışı (varsa)

### 10.6 SQL injection
```bash
curl -X POST .../api/arama -d '{"query": "test' OR 1=1--"}'
```
**Beklenen:** Hata değil, parametrize edilmiş — extra sonuç dönmemeli.

### 10.7 XSS
- `<script>alert(1)</script>` form'a yapıştır
- Render'da kaçırılmış (escaped) olmalı

### 10.8 CSRF
- Cross-origin POST → reddedilmeli (NextAuth + same-site)

### 10.9 CORS
- `ALLOWED_ORIGINS` listesi dışından origin → reddedilmeli

### 10.10 Audit log
Her hassas işlem (login, belge yükleme, silme, plan değişikliği) `audit_log` tablosuna işlenmeli.

---

## 11. Billing & iyzico Testleri 🔴

### 11.1 Plan satın alma (sandbox)
1. Free user olarak login
2. `/app/ayarlar/plan` → "Pro Solo" seç
3. iyzico checkout sayfasına yönlendir
4. **Sandbox test kartı:** `5528790000000008` / `12/30` / `123`
5. Ödeme tamamla → callback
6. DB'de `subscriptions` kaydı oluşmalı, `status=active`

### 11.2 Webhook doğrulama
- iyzico webhook geldiğinde HMAC imza doğrulanmalı
- Yanlış imza → 401
- Replay attack (aynı event 2x) → idempotency

### 11.3 Plan upgrade/downgrade
- Solo → Team upgrade çalışmalı
- Pro → Free downgrade (period end'de aktif)

### 11.4 İptal akışı
- Cancel → period end'e kadar çalışır, sonra free
- Anında iptal seçeneği (refund) çalışıyor mu

### 11.5 Failed payment
- Geçersiz kart → 400 + user-friendly mesaj
- Yetersiz limit → fail
- DB'de `payments` kaydı `status=failed`

### 11.6 Fatura kayıtları
- Her başarılı ödeme `payments` tablosunda
- Tarih, tutar, plan, KDV doğru

---

## 12. E-mail Akışları (Mailpit) 🟡

| Akış | Tetik | Mailpit'te görünmesi gereken |
|---|---|---|
| Welcome | Yeni kayıt | "Hoşgeldin {ad}" |
| E-mail verify | Kayıt | Doğrulama linki |
| Password reset | Sıfırla butonu | Reset linki (1sa geçerli) |
| Beta davet | Admin → davet | Onboarding linki |
| Plan upgrade | Subscribe | Fatura + hoşgeldin |
| Plan cancel | Cancel | Onay + son tarih |
| Welcome series | 1, 3, 7. gün | Drip campaign |
| Geri bildirim cevabı | Admin reply | User'a e-posta |

**Kontrol:** Her e-mail HTML render olmalı, Türkçe karakterler bozulmamalı.

---

## 13. RAG / Emsal Arama Doğruluk Testi 🟡

### 13.1 Benchmark sorguları (5 örnek)
| Sorgu | Beklenen ilk 5'te |
|---|---|
| "icra takibi emekli maaşı haczi" | İİK 83/a ilgili karar |
| "ihtiyati haciz kefil" | Kefil haczi kararları |
| "tahsilat ihtarname zamanaşımı" | İlgili 12. HD kararı |
| "menfi tespit alacaklı" | Menfi tespit kararları |
| "kambiyo senetlerine özgü icra takibi" | Bono/poliçe kararları |

### 13.2 Embedding kalitesi
- "icra hukuku" ve "icra ve iflas hukuku" sorguları benzer sonuç vermeli
- "ihtar" ve "ihtarname" yakın sonuçlar
- Tamamen alakasız sorgu ("yemek tarifi") → 0 ya da çok düşük skor

### 13.3 Latency
- p50 < 800ms
- p95 < 2000ms

### 13.4 Chunk sayısı doğrulama
```python
# chroma client
collection.count()
```
**Beklenen:** ~187K (öncesinde ne kadar embed edildiyse).

---

## 14. Admin Panel Testleri 🟡

| Sayfa | Test |
|---|---|
| `/app/admin` | Sadece admin role erişebilir |
| `/app/admin/users` | Kullanıcı listesi, arama, filtreleme |
| `/app/admin/users/[id]` | Detay, plan değiştirme, ban |
| `/app/admin/tenants` | Tenant listesi, kullanım metrikleri |
| `/app/admin/feedback` | Feedback listesi + reply |
| `/app/admin/beta` | Davetiye gönderme |
| `/app/admin/metrics` | DAU/MAU, query count, revenue |
| `/app/admin/audit` | Audit log filtreleme |

**Negatif:** Non-admin user `/app/admin`'e gitmeye çalışırsa → 403 ya da `/app` redirect.

---

## 15. Kullanıcı Dashboard 🟢

| Sayfa | Test |
|---|---|
| `/app` | Quick action kartları, son sorgular |
| `/app/dosyalar` | Belge listesi, yükleme, indirme |
| `/app/dosya/[id]` | Belge detay, analiz |
| `/app/sorgu` | Sorgu geçmişi |
| `/app/raporlar` | Aylık kullanım raporu |
| `/app/ayarlar/profil` | Ad, e-mail, şifre değiştirme |
| `/app/ayarlar/plan` | Plan + ödeme yönetimi |
| `/app/ayarlar/uyelik` | Üyelik bilgileri |

---

## 16. Performans Testleri 🟡

### 16.1 Backend yük testi (k6 / locust)
```bash
# 50 eşzamanlı kullanıcı, 5 dk arama
k6 run loadtest.js
```
**Hedef:**
- p95 latency < 2s
- Error rate < 1%
- CPU < 80%

### 16.2 DB query analizi
```sql
EXPLAIN ANALYZE SELECT ... FROM user_searches WHERE ...;
```
- N+1 query yok
- Kullanılan tüm filtre kolonlarında index var

### 16.3 Frontend bundle size
```bash
cd web && npm run build
```
**Hedef:**
- First Load JS < 200kb
- Largest page < 500kb

### 16.4 Memory leak
- 30 dk boyunca sürekli istek → memory büyümemeli

---

## 17. KVKK / Yasal Uyumluluk Testleri 🔴

- [ ] Kayıt formunda KVKK metni linki çalışıyor
- [ ] KVKK onay zorunlu (boş gönderim reddedilir)
- [ ] `/kvkk` sayfası aydınlatma metni içeriyor
- [ ] Cookie banner var ve seçim kayda alınıyor
- [ ] "Verilerimi sil" akışı → 30 gün içinde tamamlanır
- [ ] PII redaction LLM'e gitmeden önce çalışıyor
- [ ] Audit log immutable (UPDATE/DELETE kısıtlanmış)
- [ ] Veri saklama süreleri policy'ye uygun
- [ ] Türkiye'de hosting (production'da)
- [ ] Sözleşmeler (kullanım, gizlilik) erişilebilir

---

## 18. Error Handling & UX Testleri 🟢

- [ ] 404 sayfası özelleştirilmiş
- [ ] 500 sayfası özelleştirilmiş + error ID
- [ ] Network kopukluğu → user-friendly mesaj
- [ ] Form validation hataları açık ve Türkçe
- [ ] Loading state'leri tüm async işlemlerde
- [ ] Empty state'ler (boş liste vb.) bilgilendirici
- [ ] Toast/notification sistemi tutarlı

---

## 19. Browser / Cihaz Kombinasyonu Testleri 🟢

| Browser | Versiyon | Test |
|---|---|---|
| Chrome | Son 2 versiyon | Tüm akışlar |
| Firefox | Son 2 versiyon | Tüm akışlar |
| Safari | Son 2 versiyon | Login, arama, dilekçe |
| Edge | Son 2 versiyon | Login, arama |
| Mobile Safari | iOS 16+ | Responsive |
| Chrome Android | Son | Responsive |

---

## 20. Smoke Test — Hızlı Doğrulama (10 dk) ✅

Bu sırayla çalıştır, hepsi yeşil olmalı:

1. `docker compose ps` → 2 container running
2. `curl http://localhost:8000/api/health` → ok
3. `curl http://localhost:3000` → 200, HTML
4. `/giris` → admin login başarılı
5. `/emsal-arama` → "icra" → ≥3 sonuç
6. `/faiz-hesaplayici` → hesap çalışır
7. `/app` → dashboard yüklenir
8. `/app/admin` → admin paneli (sen olarak)
9. `/kayit` → yeni hesap aç → Mailpit'te e-mail görür
10. `/app/ayarlar/plan` → iyzico checkout açılır

**Hepsi yeşilse → MVP local'de çalışıyor demektir.**

---

## 21. Production'a Geçmeden Önce Ek Testler (sonra)

- [ ] SSL sertifikası (Let's Encrypt)
- [ ] Backup stratejisi test edildi (pg_dump + restore)
- [ ] DR planı (felaket kurtarma)
- [ ] Monitoring (Sentry, uptime)
- [ ] Log aggregation (production logs)
- [ ] Rate limit production değerleri
- [ ] iyzico **production** key'leri
- [ ] Gerçek SMTP (Resend/Postmark)
- [ ] CDN / static asset cache
- [ ] Database read replica (gerekirse)
- [ ] Domain + DNS propagation
- [ ] robots.txt + sitemap.xml
- [ ] Google Search Console doğrulama
- [ ] Penetration test (en azından OWASP Top 10)

---

## 📋 Bug Tracking Şablonu

Test sırasında bulduğun her sorunu şu formda not et:

```
ID: BUG-001
Şiddet: 🔴 Kritik / 🟡 Orta / 🟢 Düşük
Modül: <emsal-arama / billing / ...>
Adımlar: 1. ... 2. ... 3. ...
Beklenen: ...
Gerçekleşen: ...
Console log / screenshot: ...
```

---

## ✅ Test başarı kriteri

- **MVP launch için:** Tüm 🔴 testler PASS, 🟡 testlerin %80'i PASS
- **Beta launch için:** Tüm 🔴 + 🟡 PASS, 🟢 testlerin %70'i PASS
- **Production için:** Tüm testler PASS + Bölüm 21'deki ek kontroller PASS
