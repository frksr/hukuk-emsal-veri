# Hukuk Emsal — SEO Stratejisi ve Yol Haritası

**Tarih:** 2026-06-09
**Kapsam:** hukukemsal.tr (Next.js frontend)
**Durum:** Teknik temel düzeltildi (bkz. Bölüm 1) · İçerik stratejisi uygulanmayı bekliyor

---

## 1. Teknik denetim — bulunan ve düzeltilen sorunlar

| # | Sorun | Etki | Durum |
|---|---|---|---|
| 1 | `sitemap.xml`'deki 6 URL gerçek route'larla uyuşmuyordu (`/faiz-hesaplama`→`/faiz-hesaplayici`, `/kvkk-uyum`→`/kvkk`, `/trendler`→`/trend`, `/kullanim-kosullari`→`/kullanim-sartlari`; `/hakkimizda` ve `/iletisim` hiç yok) | Google sitemap'te 404 görür → crawl bütçesi ve güven kaybı | ✅ Düzeltildi |
| 2 | `/karar-ozet`, `/belge-denetim`, `/yasal-uyari` sitemap'te yoktu | İndekslenme gecikmesi | ✅ Eklendi |
| 3 | JSON-LD'lerde yanlış domain (`hukuk-emsal.tr` ≠ `hukukemsal.tr`) | Schema sinyalleri yanlış siteye işaret ediyordu | ✅ `SITE_URL` env'den |
| 4 | JSON-LD `next/script afterInteractive` ile basılıyordu | İlk HTML'de yok → crawler'lar kaçırabilir | ✅ Server-render `<script>` |
| 5 | `public/` klasörü tamamen boştu — og-default.png, favicon, logo, manifest 404 | Sosyal paylaşım kartı yok, marka sinyali yok | ✅ Tüm asset'ler üretildi |
| 6 | `generateOgImageUrl()` var olmayan `/api/og`'a işaret ediyordu | Tüm sayfaların `og:image`'ı 404 | ✅ Edge `/api/og` route'u eklendi |
| 7 | `/giris`, `/kayit`, `/sifre-sifirla`, `/hosgeldin` indekslenebilirdi | İnce içerik (thin content) indekslenmesi | ✅ `noindex` + robots disallow |
| 8 | GSC verification alanı boştu | Search Console doğrulanamaz | ✅ `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` env desteği |

### Kalan teknik işler (deploy sonrası, kod dışı)
1. Google Search Console'a domain ekle, env'e verification token'ı koy, sitemap'i gönder.
2. Bing Webmaster Tools (Türkiye'de ~%3-5 pay ama bedava).
3. Core Web Vitals ölçümü (PageSpeed Insights) — özellikle LCP; ana sayfada hero görseli yok, metin ağırlıklı olduğundan iyi olması beklenir.
4. Vercel Analytics / GA4 kurulumu (çerez onayı CookieConsent'e bağlanmalı).
5. `robots.ts`'te GPTBot/CCBot engeli mevcut — AI arama görünürlüğü (ChatGPT, Perplexity) isteniyorsa bu kararı yeniden değerlendirin; trafik kaynağı olarak büyüyor.

---

## 2. Rekabet görünümü

İki ayrı yarış var; ikisini ayrı stratejiyle oynamak gerekir.

**a) Karar arama (head terimler: "yargıtay karar arama", "emsal karar")**
Resmî ve köklü oyuncular domine ediyor: karararama.yargitay.gov.tr, emsal.uyap.gov.tr, Yargıtay İçtihat Merkezi. Ücretli arşivler: Lexpera (~2,5M karar), Kazancı (~4,2M içtihat), Sinerji. AI tarafında doğrudan rakip: **emsal.ai** ("11M+ içtihat, anlamsal arama" iddiasıyla zaten "yargıtay karar arama" için sayfa açmış durumda). Bu head terimlerde kısa vadede ilk sayfa gerçekçi değil — burada hedef, **long-tail karar sorguları** ve "AI + emsal" kesişimi.

**b) Araç/şablon sorguları ("ihtarname örneği", "dilekçe örneği", "faiz hesaplama", "zamanaşımı hesaplama")**
Burayı avukat büro blogları (mihci.av.tr, buken.av.tr, demirbas.av.tr vb.) ve şablon siteleri (ornekbelge.com.tr, karacanhukuk.com) tutuyor. Çoğu statik Word şablonu sunuyor. **Sizin farkınız: etkileşimli, hesaplayan, emsal kararla gerekçelendiren araçlar.** Bu segment kazanılabilir ve dönüşüm (kayıt) potansiyeli en yüksek segment.

---

## 3. Anahtar kelime stratejisi

Hacim rakamları araç olmadan doğrulanamaz; aşağıdaki öncelik sırası rekabet/niyet dengesine göredir. Lansman sonrası GSC + (tercihen) Ahrefs/SEMrush TR verisiyle kalibre edin.

### Küme A — Araç sayfaları (yüksek niyet, kazanılabilir) → mevcut sayfalara map'li
| Hedef sorgu ailesi | Sayfa | Not |
|---|---|---|
| icra faiz hesaplama, temerrüt faizi hesaplama, ticari faiz hesaplama, yasal faiz oranı 2026 | `/faiz-hesaplayici` | "2026" varyantı her yıl güncellenmeli; oran tablosu sayfada görünür metin olmalı (sadece JS değil) |
| zamanaşımı hesaplama, alacak zamanaşımı, çek zamanaşımı süresi, kira alacağı zamanaşımı | `/zamanasimi` | Her kategori için sayfada SSS bloğu + FAQPage schema |
| ihtarname örneği, kira ihtarname örneği, alacak ihtarnamesi, işçi ihtarname örneği | `/ihtarname` | En rekabetçi ama en yüksek hacimli aile — alt sayfalara bölünmeli (bkz. Küme C) |
| dilekçe örneği, icra takip talebi örneği, itirazın iptali dilekçesi | `/dilekce` | Aynı şekilde alt türlere bölünmeli |
| sözleşme risk analizi, sözleşme inceleme | `/sozlesme-analizi` | Düşük hacim, düşük rekabet, yüksek B2B değeri |
| kvkk uyum kontrol listesi, kvkk checklist | `/kvkk` | KOBİ trafiği; lead-magnet |

### Küme B — Bilgi içeriği (blog; orta niyet, otorite inşası)
"emsal karar nedir", "ihtarname nasıl çekilir", "icra takibi nasıl başlatılır", "itirazın iptali davası", "TBK 88 yasal faiz", "İİK 39 zamanaşımı", "tahliye davası süreleri", "karşı vekalet ücreti hesaplama". Her makale ilgili araca CTA ile bağlanır (makale → araç → kayıt hunisi).

### Küme C — Programatik long-tail (en büyük fırsat)
Elinizde 10.022 anonimleştirilmiş karar + yapılandırılmış metadata var. Rakiplerin çoğu bunu login arkasında tutuyor; **karar özet sayfalarını public yapmak** uzun kuyrukta binlerce sorgu yakalar:

- URL şablonu: `/karar/yargitay-12-hd-2023-1234` (daire + esas/karar no slug)
- Sayfa içeriği: AI özet (~200 kelime) + anahtar hukuki kavramlar + ilgili emsaller + "bu konuda dilekçe oluştur" CTA. Tam metin değil özet → ücretli arşivlerle telif/TOS sürtüşmesini azaltır, thin content riskine karşı her sayfada özgün özet şart.
- Schema: `Article` (mevcut `buildArticleJsonLd` hazır).
- Sitemap: ayrı `sitemap-kararlar.xml` (Next.js `generateSitemaps` ile 10K URL'i parçala).
- Riskler: (1) KVKK — anonimleştirme pipeline'ı zaten var, yayın öncesi `anonymization_check` alanı zorunlu tutulmalı; (2) aşamalı açın — önce 500 sayfa, indekslenme ve kalite sinyali görüldükten sonra ölçekleyin.

Kademeli alt sayfa örnekleri (Küme A'yı C ile birleştiren):
`/ihtarname/kira-tahliye`, `/ihtarname/alacak`, `/ihtarname/iscilik-alacagi`, `/zamanasimi/cek`, `/zamanasimi/kira` — her biri kendi başlığı, SSS'i ve aracın ön-doldurulmuş haliyle.

---

## 4. İçerik takvimi (ilk 3 ay)

**Ay 1 — temel:** 4 makale (emsal karar nedir / ihtarname nasıl çekilir / icra takibi adım adım / yasal faiz 2026 rehberi) + ihtarname ve zamanaşımı alt sayfalarının ilk 4'ü.
**Ay 2 — programatik pilot:** 500 karar özet sayfası + iç linkleme (araç sayfaları ↔ ilgili kararlar) + 4 makale.
**Ay 3 — ölçekleme:** karar sayfalarını 5K'ya çıkar, GSC verisine göre kazanan kümelere içerik ekle, kaybedenleri birleştir.

Yazım standardı: her sayfa tek H1, hedef sorgu title'ın başında, 150-160 karakter description (`lib/seo.ts` zaten uyarıyor), her makalede en az 3 iç link, yazar kutusu (E-E-A-T için hukukçu danışman adı — hukuki inceleme zaten P0 checklist'inizde).

---

## 5. Otorite / backlink

Hukuk dikeyi YMYL (Your Money Your Life) — Google kalite eşiği yüksek. Pratik kanallar: barolar ve hukuk fakültesi kariyer sayfalarına ücretsiz araç tanıtımı, hukuk bloglarına "faiz hesaplayıcı embed" widget'ı, akademik kullanım için dataset citation (10K karar dataseti araştırmacılar için çekici), LinkedIn'de avukatlara yönelik haftalık "emsal trend" paylaşımları (mevcut `/trend` sayfası içerik kaynağı).

---

## 6. KPI ve ölçüm

| Metrik | 3 ay | 6 ay |
|---|---|---|
| İndekslenen sayfa | 500+ | 5.000+ |
| GSC tıklama/ay | 1.000 | 10.000 |
| Araç sayfası → kayıt dönüşümü | %2 | %4 |
| Küme A sorgularında ilk 10 | 5 sorgu | 20 sorgu |

Aylık rutin: GSC coverage raporu (404/soft-404 kontrolü), top 20 sorgu CTR'ı (düşükse title/description revizyonu), karar sayfalarında "indexed but not ranking" oranı.

---

## Kaynaklar

- [Lexpera — Yargıtay Kararları](https://www.lexpera.com.tr/ictihat/yargitay-kararlari)
- [Yargıtay Karar Arama (resmî)](https://karararama.yargitay.gov.tr/)
- [Adalet Bakanlığı UYAP Emsal](https://emsal.uyap.gov.tr/)
- [Emsal AI — Yargıtay Karar Arama](https://emsal.ai/yargitay-karar-arama)
- [Kazancı İçtihat Bilgi Bankası](https://lib.kazanci.com.tr/kho3/ibb/anaindex.html)
- [Koç Üniv. Türk Hukuk Kaynakları rehberi](https://libguides.ku.edu.tr/TurkHukuku/ictihat)
- [ÖrnekBelge — ihtarname şablonu](https://ornekbelge.com.tr/belge/hukuk/ihtarname/genel-ihtarname-ornegi)
- [Mıhcı Hukuk — ihtarname örneği](https://mihci.av.tr/iscinin-hakli-nedenle-fesih-ihtarname-ornegi/)
