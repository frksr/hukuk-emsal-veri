"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuthUser } from "@/components/auth-context";

/** Ücretli (AI özellikleri açık) plan tier'ları. "free"/null → ücretsiz. */
const PAID_TIERS = new Set([
  "pro_solo",
  "pro_solo_uyap",
  "team",
  "team_uyap",
  "enterprise",
]);

export interface PlanState {
  loading: boolean;
  isLoggedIn: boolean;
  isPaid: boolean;
  /** Admin (sistemi izleyen ana kullanıcı) → her şey açık, upsell yok. */
  isAdmin: boolean;
  plan: string | null;
  name: string | null;
  email: string | null;
  /** E-posta doğrulandı mı (AI/ödeme için gerekli). */
  emailVerified: boolean;
  /** Modül bazlı ek-paket kredi bakiyeleri {module: adet}. */
  krediler: Record<string, number>;
}

const BOS: PlanState = {
  loading: false, isLoggedIn: false, isPaid: false, isAdmin: false,
  plan: null, name: null, email: null, emailVerified: false, krediler: {},
};

/**
 * Bir aracı KULLANMAYI DENEYEBİLİR mi? Giriş yapan her kullanıcı deneyebilir:
 * ücretsiz planda küçük günlük deneme hakkı vardır, Pro'da sınırsız, ayrıca o modülde
 * ek-paket kredisi olabilir. Günlük hak + kredi biterse backend 402 döner ve form bunu
 * yükseltme daveti olarak gösterir. Giriş yoksa kullanım için kayıt gerekir.
 */
export function modulKullanabilir(plan: PlanState, module: string): boolean {
  return plan.isLoggedIn || plan.isPaid || (plan.krediler?.[module] ?? 0) > 0;
}

/**
 * Aksiyon kapısı. Bir özelliği KULLANMAK için yönlendirme gerekiyorsa hedefi döndürür,
 * izin varsa null.
 *  - Giriş yoksa → "/kayit" (önce ücretsiz kayıt; tüm araçlar kayıt ister)
 *  - Pro gerekiyor ve plan ücretsizse → "/fiyatlandirma"
 * Plan henüz yükleniyorsa null döner (buton zaten devre dışı tutulmalı).
 */
export function actionGateHref(plan: PlanState, requirePro: boolean): string | null {
  if (plan.loading) return null;
  if (!plan.isLoggedIn) return "/kayit";
  if (requirePro && !plan.isPaid) return "/fiyatlandirma";
  return null;
}

// Modül seviyesi cache — ilk çekimden sonra plan bilinir; sonraki sayfalarda
// usePlan bu değerle ANINDA başlar → "önce form, sonra kilit" flash'ı olmaz.
// SPA oturumu boyunca yaşar, tam sayfa yenilemede sıfırlanır.
let cachedPlan: PlanState | null = null;

/**
 * Planı her yerde (sidebar, header, banner…) ANINDA tazeler. Abonelik/kredi
 * değişiminden sonra çağrılır → tüm usePlan örnekleri /me'yi yeniden çeker.
 */
export function refreshPlan() {
  cachedPlan = null;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("plan:refresh"));
  }
}

/**
 * Kullanıcının abonelik planını + ek-paket kredilerini çeker.
 * Proxy, NextAuth oturumundan JWT üretip backend'e iletir; giriş yoksa 401 döner.
 */
export function usePlan(): PlanState {
  const pathname = usePathname();
  // Sunucudan gelen oturum (Header ile aynı kaynak) → ilk render'da isLoggedIn
  // doğru; plan/kredi/doğrulama bilgisi arka planda /me ile dolar.
  const seed = useAuthUser();
  // Admin bilgisini de SSR oturumundan tohumla → sidebar ilk render'da doğru menüyü
  // gösterir (önce müşteri menüsü görünüp sonra admin'e dönmez).
  const seedAdmin = seed?.role === "admin";
  const [state, setState] = useState<PlanState>(
    cachedPlan ??
      (seed
        ? {
            ...BOS, loading: true, isLoggedIn: true,
            name: seed.name, email: seed.email,
            isAdmin: seedAdmin,
            isPaid: seedAdmin,
            plan: seedAdmin ? "enterprise" : null,
          }
        : { ...BOS, loading: true })
  );
  // "plan:refresh" olayında yeniden çek (gezinme beklemeden).
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    const h = () => setNonce((n) => n + 1);
    window.addEventListener("plan:refresh", h);
    return () => window.removeEventListener("plan:refresh", h);
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/proxy/me", { cache: "no-store" });
        if (!r.ok) {
          cachedPlan = { ...BOS };
          if (alive) setState(cachedPlan);
          return;
        }
        const body = await r.json();
        const data = body?.data ?? body;
        // Admin → her şey açık: enterprise gibi davran (tüm kilitler/upsell kalkar).
        const isAdmin = (data?.user?.role ?? null) === "admin";
        const plan: string | null = isAdmin ? "enterprise" : (data?.tenant?.plan ?? null);

        // Kredi bakiyelerini de çek (giriş yapılmışsa); hata olursa boş geç.
        let krediler: Record<string, number> = {};
        try {
          const kr = await fetch("/api/proxy/me/krediler", { cache: "no-store" });
          if (kr.ok) {
            const kb = await kr.json();
            const liste = (kb?.data ?? kb)?.bakiyeler ?? [];
            for (const b of liste) krediler[b.module] = b.balance;
          }
        } catch { /* yok say */ }

        const next: PlanState = {
          loading: false,
          isLoggedIn: true,
          isAdmin,
          isPaid: isAdmin || (!!plan && PAID_TIERS.has(plan)),
          plan,
          name: data?.user?.name ?? null,
          email: data?.user?.email ?? null,
          emailVerified: isAdmin || !!data?.user?.email_verified,
          krediler,
        };
        cachedPlan = next;
        if (alive) setState(next);
      } catch {
        if (alive) setState({ ...BOS });
      }
    })();
    return () => {
      alive = false;
    };
    // Rota değişince veya "plan:refresh" olayında yeniden doğrula.
  }, [pathname, nonce]);

  return state;
}
