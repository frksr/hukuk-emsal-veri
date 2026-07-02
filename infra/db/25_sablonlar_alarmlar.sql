-- ============================================================================
-- Migration 25: Dilekçe şablon kütüphanesi
--
-- dilekce_sablonlari : user_id IS NULL → platform şablonu (herkese açık, salt
--                      okunur); user_id dolu → kullanıcının kendi şablonu
--                      (12_user_notes / 14_reminders RLS deseni).
--
-- NOT: Emsal alarmları için YENİ tablo YOK — 10_saved_decisions.sql'deki mevcut
-- saved_search_alerts tablosu kullanılır (api/routers/alarmlar.py +
-- scripts/emsal_alarm_job.py).
-- ============================================================================

CREATE TABLE IF NOT EXISTS dilekce_sablonlari (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE,   -- NULL = platform
    tenant_id    UUID REFERENCES tenants(id) ON DELETE SET NULL,
    baslik       TEXT NOT NULL,
    kategori     TEXT NOT NULL DEFAULT 'genel',
    icerik       TEXT NOT NULL,
    degiskenler  JSONB NOT NULL DEFAULT '[]',   -- ["mahkeme","dosya_no",...]
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS dilekce_sablonlari_user_idx ON dilekce_sablonlari(user_id);
CREATE INDEX IF NOT EXISTS dilekce_sablonlari_kategori_idx ON dilekce_sablonlari(kategori);

ALTER TABLE dilekce_sablonlari ENABLE ROW LEVEL SECURITY;

-- Platform şablonları (user_id IS NULL) herkese görünür; kişisel şablonlar
-- yalnız sahibine. Yazma yalnız kendi kayıtlarına.
DROP POLICY IF EXISTS sablon_okuma ON dilekce_sablonlari;
CREATE POLICY sablon_okuma ON dilekce_sablonlari FOR SELECT
    USING (
        user_id IS NULL
        OR user_id = current_setting('app.current_user_id', TRUE)::UUID
    );
DROP POLICY IF EXISTS sablon_yazma ON dilekce_sablonlari;
CREATE POLICY sablon_yazma ON dilekce_sablonlari
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

GRANT SELECT, INSERT, UPDATE, DELETE ON dilekce_sablonlari TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON dilekce_sablonlari TO app_service;

-- ---------------------------------------------------------------------------
-- Platform şablonları (seed) — sabit uuid'lerle idempotent
-- ---------------------------------------------------------------------------

INSERT INTO dilekce_sablonlari (id, user_id, baslik, kategori, icerik, degiskenler) VALUES
(
 'a1000000-0000-4000-8000-000000000001', NULL,
 'İcra Takibine İtiraz Dilekçesi', 'icra',
E'{{icra_dairesi}} İCRA DAİRESİ''NE\n\nDosya No: {{dosya_no}}\n\nİTİRAZ EDEN (BORÇLU): {{muvekkil}}\nVEKİLİ: {{vekil}}\nALACAKLI: {{alacakli}}\n\nKONU: {{dosya_no}} sayılı dosya ile aleyhimize başlatılan ilamsız icra takibine itirazlarımızın sunulmasıdır.\n\nAÇIKLAMALAR:\n\n1. Müvekkilimiz aleyhine yukarıda numarası yazılı dosya ile ilamsız icra takibi başlatılmış, ödeme emri {{teblig_tarihi}} tarihinde tebliğ edilmiştir.\n\n2. Müvekkilimizin alacaklıya herhangi bir borcu bulunmamaktadır. Takibe konu alacak, borcun tamamı, ferileri ve işlemiş faizi yönünden itiraz ediyoruz.\n\n3. {{itiraz_gerekce}}\n\nSONUÇ VE İSTEM: Yukarıda açıklanan nedenlerle; takibe, borca, faize ve tüm ferilerine itirazlarımızın kabulü ile takibin DURDURULMASINA karar verilmesini saygıyla arz ve talep ederiz.\n\n{{tarih}}\n\nİtiraz Eden Vekili\n{{vekil}}',
 '["icra_dairesi","dosya_no","muvekkil","vekil","alacakli","teblig_tarihi","itiraz_gerekce","tarih"]'
),
(
 'a1000000-0000-4000-8000-000000000002', NULL,
 'Cevap Dilekçesi', 'hukuk',
E'{{mahkeme}}''NE\n\nDosya No: {{dosya_no}}\n\nCEVAP VEREN (DAVALI): {{muvekkil}}\nVEKİLİ: {{vekil}}\nDAVACI: {{davaci}}\n\nKONU: Dava dilekçesine karşı cevaplarımızın sunulmasıdır.\n\nAÇIKLAMALAR:\n\n1. Davacı tarafından müvekkilimiz aleyhine açılan davaya ilişkin dava dilekçesi tarafımıza {{teblig_tarihi}} tarihinde tebliğ edilmiş olup yasal süresi içinde cevaplarımızı sunuyoruz.\n\n2. Davacının iddiaları haksız ve hukuki dayanaktan yoksundur. {{savunma}}\n\n3. İspat yükü davacı üzerindedir; davacı iddialarını usulüne uygun delillerle ispat edememektedir.\n\nHUKUKİ NEDENLER: HMK, TBK, TMK ve ilgili sair mevzuat.\n\nDELİLLER: {{deliller}}\n\nSONUÇ VE İSTEM: Açıklanan nedenlerle haksız ve mesnetsiz davanın REDDİNE, yargılama giderleri ile vekâlet ücretinin davacı üzerinde bırakılmasına karar verilmesini saygıyla arz ve talep ederiz.\n\n{{tarih}}\n\nDavalı Vekili\n{{vekil}}',
 '["mahkeme","dosya_no","muvekkil","vekil","davaci","teblig_tarihi","savunma","deliller","tarih"]'
),
(
 'a1000000-0000-4000-8000-000000000003', NULL,
 'İstinaf Başvuru Dilekçesi', 'istinaf',
E'{{bam}} BÖLGE ADLİYE MAHKEMESİ İLGİLİ HUKUK DAİRESİ''NE\nGönderilmek Üzere\n{{mahkeme}}''NE\n\nDosya No: {{dosya_no}}\nKarar No: {{karar_no}}\n\nİSTİNAF EDEN: {{muvekkil}}\nVEKİLİ: {{vekil}}\nKARŞI TARAF: {{karsi_taraf}}\n\nKONU: {{mahkeme}}''nin {{karar_tarihi}} tarih ve {{karar_no}} sayılı kararının istinaf incelemesi sonucunda KALDIRILMASI istemidir.\n\nAÇIKLAMALAR:\n\n1. Yerel mahkemece verilen karar usul ve yasaya aykırıdır. Karar tarafımıza {{teblig_tarihi}} tarihinde tebliğ edilmiş olup istinaf başvurumuz yasal süresi içindedir.\n\n2. {{istinaf_gerekce}}\n\n3. Mahkemece deliller hatalı değerlendirilmiş, emsal içtihatlara aykırı hüküm kurulmuştur.\n\nSONUÇ VE İSTEM: Açıklanan nedenlerle istinaf başvurumuzun KABULÜ ile yerel mahkeme kararının KALDIRILMASINA ve davanın yeniden görülmesine karar verilmesini saygıyla arz ve talep ederiz.\n\n{{tarih}}\n\nİstinaf Eden Vekili\n{{vekil}}',
 '["bam","mahkeme","dosya_no","karar_no","karar_tarihi","muvekkil","vekil","karsi_taraf","teblig_tarihi","istinaf_gerekce","tarih"]'
),
(
 'a1000000-0000-4000-8000-000000000004', NULL,
 'Tanık Listesi Bildirimi', 'hukuk',
E'{{mahkeme}}''NE\n\nDosya No: {{dosya_no}}\n\nTANIK LİSTESİ SUNAN: {{muvekkil}}\nVEKİLİ: {{vekil}}\n\nKONU: Tanık listemizin sunulmasıdır.\n\nAÇIKLAMALAR:\n\nMahkemenizin {{ara_karar_tarihi}} tarihli ara kararı uyarınca, dinlenmesini talep ettiğimiz tanıkların isim ve adresleri aşağıda sunulmuştur:\n\n1. {{tanik_1}}\n2. {{tanik_2}}\n\nHer bir tanık, {{tanik_konusu}} hususlarında bilgi ve görgüye sahiptir.\n\nSONUÇ VE İSTEM: Yukarıda kimlik bilgileri yazılı tanıkların duruşmada dinlenmesine karar verilmesini saygıyla arz ve talep ederiz.\n\n{{tarih}}\n\n{{muvekkil}} Vekili\n{{vekil}}',
 '["mahkeme","dosya_no","muvekkil","vekil","ara_karar_tarihi","tanik_1","tanik_2","tanik_konusu","tarih"]'
),
(
 'a1000000-0000-4000-8000-000000000005', NULL,
 'Duruşma Erteleme (Mazeret) Talebi', 'hukuk',
E'{{mahkeme}}''NE\n\nDosya No: {{dosya_no}}\nDuruşma Günü: {{durusma_tarihi}}\n\nMAZERET BİLDİREN: {{muvekkil}} Vekili {{vekil}}\n\nKONU: {{durusma_tarihi}} tarihli duruşma için mazeretimizin bildirilmesi ve duruşmanın ertelenmesi istemidir.\n\nAÇIKLAMALAR:\n\n1. Mahkemenizde görülmekte olan davanın duruşması {{durusma_tarihi}} tarihine bırakılmıştır.\n\n2. {{mazeret}} nedeniyle anılan tarihte duruşmaya katılmamız mümkün olamayacaktır. Mazeretimizi tevsik eden belge ekte sunulmuştur.\n\nSONUÇ VE İSTEM: Mazeretimizin kabulü ile duruşmanın ileri bir tarihe ERTELENMESİNE, duruşma gününün tarafımıza tebliğine karar verilmesini saygıyla arz ve talep ederiz.\n\n{{tarih}}\n\n{{muvekkil}} Vekili\n{{vekil}}',
 '["mahkeme","dosya_no","durusma_tarihi","muvekkil","vekil","mazeret","tarih"]'
)
ON CONFLICT (id) DO NOTHING;
