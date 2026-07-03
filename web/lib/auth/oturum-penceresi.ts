"use client";

/**
 * "Tarayıcı penceresi açık mı" işaretçisi.
 *
 * Bilinçli olarak Max-Age/Expires VERİLMEZ → bu, tarayıcının kendi native
 * "session cookie" (oturum çerezi) davranışını tetikler: sekme kapatma veya
 * sayfa yenilemede SİLİNMEZ, ama tarayıcı PROGRAMI tamamen kapatılınca
 * (işletim sistemi düzeyinde) otomatik silinir.
 *
 * middleware.ts her istekte bu çerezin varlığına bakar:
 *  - Varsa → aynı tarayıcı oturumundayız, dokunma.
 *  - Yoksa AMA NextAuth'un kalıcı (30 gün) oturum çerezi hâlâ duruyorsa →
 *    tarayıcı kapatılıp yeniden açılmış demektir → NextAuth oturum çerezi
 *    temizlenir ve kullanıcı /panel gibi korumalı bir alandaysa girişe
 *    yönlendirilir.
 *
 * ÖNEMLİ: Bu fonksiyon giriş/kayıt (auto-login) BAŞARILI olduktan hemen
 * sonra, yönlendirmeden ÖNCE çağrılmalıdır. Aksi halde middleware, henüz
 * işaretçi konmamış yeni oturumu da "eski/kalıcı çerez" sanıp anında
 * sonlandırabilir (yarış durumu).
 */
export function oturumPenceresiAc() {
  if (typeof document === "undefined") return;
  document.cookie = "oturum_penceresi=1; path=/; SameSite=Lax";
}
