/**
 * GEÇİCİ LANSMAN MODU
 * false → panel abonelik + ek paket satın alma butonları "Bekleme Listesine Katıl"
 *         olarak gösterilir ve /bekleme-listesi sayfasına yönlendirir.
 * true  → normal satın alma / ödeme akışı geri gelir.
 *
 * Satışı açmak için tek yapmanız gereken bu değeri true yapmak.
 * (Fiyatlandırma sayfasındaki PlanCta bileşeni de satış açılınca eski akışa döndürülmeli.)
 */
export const SATIS_ACIK = false;
