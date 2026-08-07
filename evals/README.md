# RAG Kalite Değerlendirmesi (eval)

Bu klasör, emsal arama motorunun **doğruluğunu ölçen** altın standart setini ve
koşucusunu barındırır.

## Neden var?

Bir hukuk ürününde yanlış emsal sunmak, yavaş yanıt vermekten çok daha ağır bir
hatadır. Ancak retrieval kalitesini ölçen hiçbir mekanizma yoktu: bir prompt
değişikliği, yeni bir embedding modeli veya chunk boyutu ayarı sonuçları
kötüleştirse bunu **hiç kimse fark etmeyecekti**. Bu klasör o boşluğu kapatır.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `altin_set.jsonl` | Soru → beklenen karar kimlikleri (elle küratörlü) |
| `../scripts/rag_eval.py` | Koşucu: recall@k, precision@k, MRR, eşik analizi |

## Altın set formatı

Her satır bir JSON nesnesi:

```jsonc
{
  "id": "icra-001",
  "soru": "Ödeme emrine itirazın iptali davasında icra inkar tazminatı",
  "beklenen_decision_ids": ["yargitay_12hd_2024_e2023-1234_k2024-5678"],
  "beklenen_anahtar_kelimeler": ["icra inkar tazminatı", "itirazın iptali"],
  "kategori": "icra",
  "not": "İİK 67/2 — tazminat oranı"
}
```

- `beklenen_decision_ids` — **en az bir tanesi** ilk k sonuçta çıkmalı.
  Boş bırakılabilir; o zaman yalnızca anahtar kelime kontrolü yapılır.
- `beklenen_anahtar_kelimeler` — dönen chunk metinlerinde geçmesi beklenen
  ifadeler (decision_id bilinmiyorsa daha kolay küratörlenir).
- `kategori` — rapor kategori bazında kırılır; kapsam boşluklarını gösterir
  (ör. "is_hukuku" kategorisinde recall %0 ise veri kümesi o alanı içermiyordur).

## Nasıl küratörlenir?

1. Gerçek kullanıcı sorgularından (veya `usage_events` tablosundan) 50–100 soru seç.
2. Her soru için doğru cevabı **elle** bul (arama arayüzünden veya kaynaktan).
3. Karar kimliğini `beklenen_decision_ids`'e yaz.
4. Emin olmadığın soruları sete **koyma** — kirli altın set, ölçüm olmamasından
   daha kötüdür.

## Koşturma

```bash
# Canlı DB gerekir (DATABASE_URL / pgvector şeması + embed edilmiş veri)
python -m scripts.rag_eval

# Farklı k ve eşik dene
python -m scripts.rag_eval --k 10 --esik 0.3

# Eşik taraması: hangi eşik en iyi F1'i veriyor?
python -m scripts.rag_eval --esik-tara

# CI/regresyon kapısı: recall@5 %70'in altına düşerse çıkış kodu 1
python -m scripts.rag_eval --min-recall 0.70
```

## Metrikler

| Metrik | Anlamı |
|---|---|
| **recall@k** | Beklenen kararlardan en az biri ilk k sonuçta mı? (asıl metrik) |
| **precision@k** | Dönen sonuçların ne kadarı beklenenler arasında |
| **MRR** | İlk doğru sonucun sırası (1/sıra ortalaması) — üstte mi çıkıyor? |
| **bos_yanit_orani** | Eşik yüzünden hiç sonuç dönmeyen sorgular. Yüksekse eşik fazla katı. |

## Ne zaman koşulur?

- Embedding modeli / boyutu değişince (**zorunlu**)
- Chunk boyutu veya örtüşmesi değişince (**zorunlu**)
- `RAG_MIN_SIMILARITY` ayarlanmadan önce ve sonra
- Yeni veri kaynağı eklendikten sonra
- Arama SQL'i (hibrit birleştirme, çeşitlilik) değiştirilince
