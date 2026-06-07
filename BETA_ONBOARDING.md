# Hukuk Emsal — Beta Avukat Onboarding Rehberi

Hoş geldin! 👋

Sen ilk 10 beta avukattan birisin — bu nedenle ürünün şeklini doğrudan
etkileme gücün var. Bu rehber 15 dakikada platforma alışmana yardımcı olacak.

---

## 1. Hesabını Hazırla (2 dakika)

1. <https://hukukemsal.tr/kayit> → kayıt
2. E-mail doğrulama → gelen linke tıkla
3. `/app/ayarlar` → profilini tamamla
4. Bizden "Pro + UYAP plana yükseltildiniz" e-postası gelecek (otomatik değil — manuel yapıyoruz; gelmezse bana mesaj at)

---

## 2. İlk Emsal Aramayı Yap (3 dakika)

1. `/emsal-arama` sayfasına git
2. Şuna benzer doğal dilde bir soru yaz:
   - "İcra takibinde emekli maaşının haczi mümkün mü?"
   - "Çekin karşılıksız çıkması sonrası alacaklı hangi yola başvurur?"
3. **Sol panelde filtre** ile sadece "12. Hukuk Dairesi"yi seç
4. Sonuçlardan birine tıkla, tam karar metnini gör
5. Her sonuçta benzerlik skoru ve gerçek karar atıfları var

**Bizim için kritik geri bildirim:** Bulduğun emsal kararlar gerçekten konunla
ilgili miydi? Yanlış geleni var mı?

---

## 3. UYAP Dosyanı Yükle (3 dakika)

> ⚠️ **KVKK uyumu:** Yüklediğin tüm dosyalar AES-256 ile şifreli, sadece
> sana özel. Anthropic/Google AI bile kişisel verileri görmez (otomatik
> maskelenir).

1. UYAP avukat portalına gir → bir dosyanı PDF olarak indir
2. `/app/dosyalar` sayfasında "Dosya Yükle"
3. Yükleme → 10-30 saniyede `ready` olur
4. Dosyaya tıkla → karar metni + meta bilgi (esas no, mahkeme, tarih)

**Tavsiye:** İlk denemende **kritik bir dava değil**, daha basit bir dosya yükle.

---

## 4. Kendi Dosyanda AI Sorgu (3 dakika)

1. `/app/dosya/[id]` veya `/app/sorgu` sayfası
2. Bir soru yaz:
   - "Bu dosyada haciz konusu hangi madde altında?"
   - "Karşı tarafın itirazlarına emsal nasıl cevap verir?"
   - "Bu davada zamanaşımı süresi nedir?"
3. AI:
   - Önce **senin dosyanda** RAG araması yapar
   - Sonra **public emsal kararlarda** ek arama
   - PII (TC, IBAN vb.) maskeleyip LLM'e gönderir
   - Yanıtta orijinal değerleri geri koyar
   - Hangi kendi dosyandan, hangi emsalden kaynak gösterir

---

## 5. Hesaplayıcıları Dene (2 dakika)

Sınırsız kullanım — istediğin kadar:

- `/faiz-hesaplayici` — anapara + temerrüt → yasal/ticari faiz + İİK harçları + vekalet
- `/zamanasimi` — TBK/TTK/AATUHK referanslı süre + kalan gün
- `/ihtarname` — TBK 117, İİK 51 noter ihtarnamesi taslağı
- `/belge-denetim` — yazdığın dilekçenin hukuki risklerini AI denetimi

---

## 6. Bize Nasıl Geri Bildirim Verirsin?

### Yöntem 1: Geri Bildirim Widget'i (en hızlı)
Her sayfanın sağ alt köşesindeki 💬 ikonu → tip seç + mesaj.
2 dakika içinde okuruz.

### Yöntem 2: Haftalık 15dk Görüşme
Pazartesi sabahları 09:00-12:00 arası kurucu (sen) ile telefonla görüşürsün.
Takvim linki: _____________________________

### Yöntem 3: Acil Durum
Kritik bug veya güvenlik sorunu için: acil@hukukemsal.tr (24 saat içinde dönüş)

### Bize En Çok Değerli Geri Bildirimler
1. ✨ **Çalışan özellikler** hangileri günlük işine en çok değer kattı?
2. 🐛 **Hatalı sonuçlar** — yanlış emsal, yanlış dilekçe, yanlış hesap
3. 💡 **Eksik özellikler** — "Şunu da yapsa harika olur"
4. 😖 **Kullanım zorluğu** — "Bu butonu bulamadım", "Yavaş yüklendi"
5. 💰 **Fiyat geri bildirimi** — Pro+UYAP'ı ₺799'a ödemeye değer mi?

---

## 7. Senin Faydan

Sen beta avukat olarak:

- ✅ 180 gün **ücretsiz** Pro + UYAP (₺799/ay × 6 = ₺4.794 değer)
- ✅ Sonrasında **ömür boyu %50 indirim** (₺399/ay)
- ✅ Platform lansmanında **kurucu kullanıcı** rozeti + tanıtım (opsiyonel)
- ✅ Kurucu ekiple doğrudan iletişim
- ✅ Tüm yeni özellikler önce sende

---

## 8. Bizim Faydamız

Sen geri bildirim verdikçe biz:

- 🐛 Bug'ları hızla düzeltiriz
- ✨ Gerçek avukat ihtiyacına göre özellik geliştiriliriz
- 📈 Lansmanda "şu hukuk firmaları kullanıyor" referansı oluruz
- 💪 Türk hukuku için **gerçek değer üreten** AI yaparız

---

## 9. KVKK / Veri Güvenliği

- Verilerin **Türkiye'de** (Hetzner FRA veya Türk hosting)
- **AES-256-GCM şifreli**, sadece sana özel anahtarla
- **PII otomatik maskeleme** — Anthropic/Google görmez
- **Cryptographic deletion** — hesabı silersen veri matematiksel olarak yok
- KVKK haklarını `/app/ayarlar/kvkk` üzerinden kullanabilirsin

Detay: <https://hukukemsal.tr/gizlilik>

---

## 10. Sıkça Sorulan Sorular

**S: Tüm dava dosyalarımı yüklemeliyim mi?**
C: Hayır, sadece denemek istediklerini. İstersen tek bir dosyayla başla.

**S: Beni başka avukatlar görür mü?**
C: Asla. Veriler **per-tenant şifreli**, kimse senin verilerini göremez.

**S: 180 gün sonra ne olur?**
C: Pro+UYAP plana ömür boyu %50 indirimle devam edebilirsin. Mecbur değilsin.

**S: Verim güvenli mi?**
C: Evet, ama beta sürüm beklenmedik hata olabilir. Kritik veri için ek yedek al.

**S: Müvekkil verileri AI'ya gidiyor mu?**
C: TC, IBAN, telefon gibi PII'ler otomatik maskelenir. LLM sadece anonim
metin görür. Anlamı: müvekkil "Ahmet Yılmaz" ise LLM "<NAME_xyz>" görür,
yanıtta tekrar "Ahmet Yılmaz" olur.

**S: Lansman ne zaman?**
C: Beta'nın 4. ayında public launch planlıyoruz (Eylül 2026 hedefi).

---

## İletişim

- 📧 E-posta: kurucu@hukukemsal.tr
- 💬 Beta Telegram grubu: _____________________________
- 📅 Haftalık görüşme takvimi: _____________________________
- 🚨 Acil: acil@hukukemsal.tr

**Hoş geldin, ürünü birlikte inşa edelim.** 🚀
