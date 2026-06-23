# Abonelik Yönetimi — Admin Panelden Tek Kaynak + iyzico Senkron (PLAN)

> Durum: **Sonraya bırakıldı** — önce site canlıya alınacak, sonra bu özellik eklenecek.
> Bu not, kararlaştırılan tasarımı saklar; build zamanı buradan devam ederiz.

## Amaç
Plan **fiyatları, adları, özellik listeleri ve deneme süreleri** tek yerden (sistem
yöneticisi paneli) düzenlenebilsin. Fiyat/ad/trial değişiklikleri **iyzico'ya da**
yansısın. `/fiyatlandirma` ve abonelik ekranı da bu tek kaynaktan beslensin (artık
sabit kodlu olmasın).

## Kritik iyzico kısıtı (dokümandan doğrulandı)
iyzico'da bir **pricing plan'ın fiyatı GÜNCELLENEMEZ**. Update metodu yalnızca
`name` ve `trialPeriodDays` değiştirir. Bu yüzden:

- **Fiyat değişince** → iyzico'da **yeni pricing plan** oluştur (aynı product altında,
  benzersiz isimle), uygulamanın o tier için sakladığı `pricing_plan_ref`'i yenisiyle
  değiştir. **Mevcut aboneler eski fiyatta kalır**, yeni aboneler yeni fiyata geçer.
  (Kullanıcı onayı: bu yaklaşım seçildi.)
- **Sadece ad/trial değişince** → mevcut planı `POST /v2/subscription/pricing-plans/{ref}`
  ile güncelle (yeni plan açma).
- Eski plan üzerinde aktif abonelik/güncelleme kaydı varsa **silinemez** → bırakılır
  (pasif referans olarak durur).

### İlgili iyzico uçları
- Ürün oluştur: `POST /v2/subscription/products`
- Ürünleri listele: `GET /v2/subscription/products?page=1&count=100`
- Plan oluştur: `POST /v2/subscription/products/{productRef}/pricing-plans`
  (zorunlu: name, price, currencyCode, paymentInterval, planPaymentType=RECURRING)
- Plan güncelle (name/trial): `POST /v2/subscription/pricing-plans/{planRef}`
- Plan detay: `GET /v2/subscription/pricing-plans/{planRef}`
- Plan sil: `DELETE /v2/subscription/pricing-plans/{planRef}` (aktif abonelik varsa olmaz)

Mevcut kod tabanında `services/billing.py` içinde `_post`/`_get` + auth zaten var;
`scripts/setup_iyzico_plans.py` ürün+plan oluşturmayı zaten yapıyor → yeniden kullan.

## Veri modeli — `app_config` anahtarı: `plans`
Mevcut `app_config` tablosuna yeni bir key (`plans`). Tek kaynak:

```jsonc
{
  "pro_solo": {
    "name": "Pro Solo",
    "price": 499.00,
    "currency": "TRY",
    "trial_days": 0,
    "features": ["Sınırsız genel araçlar", "AI dilekçe + denetim sınırsız", "..."],
    "iyzico_product_ref": "....",        // ilk senkronda doldurulur
    "iyzico_pricing_plan_ref": "....",   // fiyat değişince güncellenir
    "visible": true,                      // public sayfada görünsün mü
    "order": 1
  },
  "pro_solo_uyap": { ... },
  "team": { ... },
  "team_uyap": { ... }
  // free ve enterprise: fiyatsız/özel — iyzico'ya gitmez, sadece görünüm
}
```

- `services/billing.py PLAN_PRICING` → env yerine bu DB kaydından okunsun (env fallback).
- `services/app_config.py` → `get_plans()` / `set_plans()` (mevcut `get_value`/`set_value`
  deseniyle, ~30 sn cache TTL zaten var).

## Backend uçları (admin router)
- `GET /api/admin/config/plans` → mevcut planlar (DB; yoksa koddan tohum).
- `PUT /api/admin/config/plans` → kaydet + iyzico senkron. Mantık (her ücretli tier için):
  1. `iyzico_product_ref` yoksa → ürün oluştur, ref'i sakla.
  2. Fiyat değiştiyse (veya `pricing_plan_ref` yoksa) → yeni pricing plan oluştur,
     `iyzico_pricing_plan_ref`'i güncelle.
  3. Sadece ad/trial değiştiyse → pricing plan update (name/trial).
  4. DB'ye yaz, `audit` kaydı bırak.
  - Senkron hatalarında: DB'yi yine de kaydet ama yanıtonta tier bazında
    `iyzico_sync: ok|error+mesaj` döndür (admin görsün).
- Idempotent + dry-run opsiyonu (önizleme) faydalı.

## Frontend
- **Admin**: `web/app/app/admin/paketler/paketler-panel.tsx` içine "Planlar & Fiyatlar"
  sekmesi: tier başına ad, fiyat, para birimi, trial, özellik listesi (ekle/çıkar/sırala),
  görünürlük. Kaydet → `PUT /config/plans`. iyzico senkron sonucu satır bazında gösterilsin.
- **Public**: `abonelik-panel.tsx` ve `app/fiyatlandirma/page.tsx` içindeki sabit `PLANS`
  → API'den çek (`GET /api/.../plans` public-safe alanlar: name, price, features, visible).
  Sabit kodlu `PLANS` kaldırılır; SSR/ISR ile cache'lenebilir.

## Yapılacaklar (build zamanı sırası)
1. Migration gerekmez (app_config var). İsteğe bağlı: ilk `plans` tohumu için küçük script.
2. `services/app_config.py`: get_plans/set_plans.
3. `services/billing.py`: PLAN_PRICING'i DB'den oku (env fallback) + iyzico senkron
   yardımcıları (create_product_if_missing, create_pricing_plan, update_pricing_plan).
4. `api/routers/admin.py`: GET/PUT `/config/plans`.
5. Frontend admin sekmesi + public sayfaların API'den beslenmesi.
6. Test: fiyat değişimi → yeni iyzico plan ref; ad değişimi → update; mevcut abone
   etkilenmiyor.

## Riskler / notlar
- Plan **adı benzersiz** olmalı (iyzico). Yeni plan açarken ada sürüm/zaman ekle
  (ör. "Pro Solo - Aylık v2025-06") ama görünen ad ayrı tutulabilir.
- `free`/`enterprise` iyzico'ya gönderilmez.
- iyzico sandbox vs prod: `IYZICO_BASE_URL` ile kontrol ediliyor; senkronu önce
  sandbox'ta dene.
