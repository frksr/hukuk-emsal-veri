# Faz 2.5 — Beta Onboarding Paketi (Tamamlandı)

## Bu turda eklenenler — 17 dosya

### Backend (4 dosya + 1 migration)
- `infra/db/06_migration_004.sql` — feedback, scheduled_emails, admin_notes, user_milestones, beta_program kolonları
- `api/routers/admin.py` — 7 admin endpoint (dashboard, users, manual upgrade, audit, feedback CRUD, beta-invite)
- `api/routers/feedback.py` — Public feedback submit endpoint
- `services/welcome_series.py` — 4 e-postalı welcome serisi (day 0, 1, 3, 7) + cron worker

### Frontend (10 dosya)
- `web/app/app/admin/layout.tsx` — Admin role guard + 5 sekme
- `web/app/app/admin/page.tsx` + `dashboard.tsx` — KPI dashboard (DAU/MAU/MRR/tier/feedback)
- `web/app/app/admin/kullanicilar/` — User listesi + arama + plan upgrade + beta hediye
- `web/app/app/admin/feedback/` — Feedback yönetimi (filter, status update, admin note)
- `web/app/app/admin/beta/` — Beta davet formu
- `web/app/app/admin/audit/` — Audit log viewer
- `web/components/feedback-widget.tsx` — Sticky 💬 widget (her sayfada, /admin hariç)

### Dokümantasyon (3 dosya)
- `BETA_SOZLESMESI.md` — Beta avukatla imzalanacak sözleşme (KVKK + fikri mülkiyet + yükümlülükler)
- `BETA_ONBOARDING.md` — Beta avukat için onboarding rehberi (10 dakikalık tour)
- (bu dosya) `PHASE2_BETA.md`

## Admin yetkilerinin kapsamı

```
/app/admin                  Dashboard
  ├─ /app/admin/kullanicilar User CRUD + manuel plan upgrade
  ├─ /app/admin/feedback     Geri bildirim yönetimi
  ├─ /app/admin/audit        Tüm audit log
  └─ /app/admin/beta         Beta davet formu
```

Tüm `/app/admin/*` route'ları `role='admin'` user'lara açık. Diğerleri redirect.

## Beta avukat akışı

```
1. Sen → /app/admin/beta → davetiye e-postası gönder
2. Avukat → /kayit → Free hesap
3. Sen → /app/admin/kullanicilar → 🎁 ikonu → 180 gün Pro+UYAP
4. Avukat'a BETA_SOZLESMESI.md gönder, imzalat
5. Avukat'a BETA_ONBOARDING.md gönder (yol haritası)
6. Welcome e-mail serisi otomatik (day 0/1/3/7)
7. Avukat ürünü kullanır, feedback widget'ten bildirim
8. Sen /app/admin/feedback'te yönetirsin
9. Haftalık 15dk görüşme
10. Beta sonu → Pro+UYAP %50 indirim
```

## Welcome e-mail serisi

| Gün | E-mail | Konu |
|---|---|---|
| 0 | welcome_day_0 | 🎉 Hoş geldiniz + 3 başlangıç adımı |
| 1 | welcome_day_1 | 💡 5 ünlü özellik tanıtımı |
| 3 | welcome_day_3 | 🚀 UYAP Pro+ deneme önerisi |
| 7 | welcome_day_7 | 📊 Geri bildirim ricası |

**Cron setup (Railway/Fly.io scheduled task):**
```bash
# Her 15 dakikada bir
*/15 * * * * cd /app && python -m services.welcome_series
```

Veya FastAPI background task / Celery / GitHub Actions cron.

## Geri Bildirim Widget'i

Sağ alt köşede her sayfada (her zaman /admin hariç):
- Tip seç (bug/feature/praise/complaint/question)
- Konu + mesaj (anonim de olabilir)
- Sayfa URL'i + ekran çözünürlüğü otomatik
- Kritik feedback → admin@hukukemsal.tr'e otomatik bildirim

## ENV variables — yeni

```bash
# Admin'e kritik feedback bildirimi
SMTP_FROM=noreply@hukukemsal.tr
# admin email
SUPPORT_EMAIL=admin@hukukemsal.tr  # opsiyonel, default kullanılır
```

## Toplam proje istatistiği — şu an

| Metric | Değer |
|---|---|
| Backend dosya | 30+ |
| Frontend sayfa | 20+ |
| API endpoint | 70+ |
| DB tablo | 17 |
| Faz tamamlanma | Faz 0 (deploy bekliyor) + Faz 1 + Faz 2 + Faz 2.5 (beta hazır) |

## Sonraki adım önerim

### Önce sen:
1. **Faz 0 deploy'u tamamla** (yarım kalmış mı bilmiyorum — durumunu söyle)
2. **DB migration'ları uygula** (4 migration var)
3. **iyzico sandbox setup** + 4 ürün/plan
4. **SMTP servisi** (Resend / Postmark / Brevo) → ENV
5. **Master encryption key** üret + ENV
6. **Welcome series cron** kurulumu (Railway scheduled task)
7. **İlk beta avukat** davetiyesi → admin panel

### Sonra ben:
**Seçenek A:** Faz 3 — Yerel LLM deploy (Llama 3.1 70B veya Qwen 72B)
**Seçenek B:** UYAP Chrome Extension (manuel upload'dan otomatik çekime)
**Seçenek C:** Avukat dashboardunu zenginleştirme — milestones, recommendations
**Seçenek D:** Faz 5 başlangıç — Vault (multi-doc DD), Workflow Agents

Önerim: **Önce gerçek beta avukatlardan veri toplansın (2-3 hafta)**, sonra
hangi yöne gidileceğini onların geri bildirimine göre belirleyelim. Bu sürede
ben Faz 0 deploy fix'leriyle ilgilenebilirim.
