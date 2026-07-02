"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { SATIS_ACIK } from "@/lib/satis-modu";
import { CheckCircle2, ArrowRight, Loader2, Crown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { BasariModal } from "@/components/basari-modal";
import { Portal } from "@/components/portal";
import { Switch } from "@/components/ui/switch";
import { ShieldCheck } from "lucide-react";
import { refreshPlan } from "@/lib/use-plan";

const PLANS = [
  { key: "free", name: "Free", price: "₺0", desc: "Bireysel deneme",
    features: ["40 emsal arama/gün", "6 dilekçe/gün", "Hesaplayıcılar sınırsız", "Geçmiş kayıt"] },
  { key: "pro_solo", name: "Pro Solo", price: "₺499/ay", desc: "Bireysel avukat",
    features: ["Sınırsız genel araçlar", "Yapay Zeka dilekçe + denetim sınırsız", "Geçmiş tam metin arama"] },
  { key: "pro_solo_uyap", name: "Pro + UYAP", price: "₺799/ay", desc: "UYAP eklentili",
    features: ["Pro Solo'nun her şeyi", "50 UYAP dosyası", "200 Yapay Zeka sorgu/ay", "Kendi dosyalarınızda RAG"],
    popular: true },
  { key: "team", name: "Team", price: "₺1.499/ay", desc: "5 kullanıcı",
    features: ["5 kullanıcı", "Rol bazlı erişim", "Ortak dosyalar", "Beyaz etiket"] },
  { key: "team_uyap", name: "Team + UYAP", price: "₺1.999/ay", desc: "Büro + UYAP",
    features: ["Team'in her şeyi", "250 UYAP dosyası", "1.000 sorgu/ay"] },
  { key: "enterprise", name: "Enterprise", price: "Görüşelim", desc: "Büyük büro",
    features: ["Sınırsız UYAP", "SSO", "Self-hosted opsiyonu", "SLA"] },
];

// Pakete göre hover efekti — üst paketler daha belirgin/etkileyici. PLANS sırası
// (free→enterprise) doğrudan efekt şiddetini verir. Yalnızca hover'da tetiklenir.
const EFEKT: string[] = [
  // free — en sade
  "hover:-translate-y-0.5 hover:shadow-md",
  // pro_solo
  "hover:-translate-y-1 hover:shadow-lg hover:border-primary/50",
  // pro_solo_uyap
  "hover:-translate-y-1 hover:shadow-xl hover:border-primary/60 hover:ring-1 hover:ring-primary/30",
  // team
  "hover:-translate-y-1.5 hover:shadow-xl hover:border-accent/50 hover:ring-1 hover:ring-accent/40",
  // team_uyap
  "hover:-translate-y-1.5 hover:shadow-2xl hover:border-accent/60 hover:ring-2 hover:ring-accent/50",
  // enterprise — en etkileyici: altın ışıma + degrade
  "hover:-translate-y-2 hover:shadow-2xl hover:border-amber-400/60 hover:ring-2 hover:ring-amber-400/50 hover:bg-gradient-to-br hover:from-amber-50/70 hover:to-transparent dark:hover:from-amber-950/20",
];

type Current = { plan: string; status: string; period_end: string | null; cancel_at_period_end: boolean };

// Callback token başına sonuç (Promise). StrictMode efekti 2 kez çalışsa da
// /billing/callback YALNIZCA bir kez çağrılır → ikinci çağrı tüketilmiş token'la
// gidip aboneliği 'failed'e çevirmez ve yanlış "Ödeme onaylanamadı" göstermez.
const _subTokenSonuc = new Map<string, Promise<{ ok: boolean; message?: string }>>();

export function AbonelikPanel() {
  const router = useRouter();
  const sp = useSearchParams();
  const [current, setCurrent] = useState<Current | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [basari, setBasari] = useState<string | null>(null);

  // Ödeme (fatura) modalı — iyzico canlı modda TC/adres/şehir gerekli.
  const [secilenPlan, setSecilenPlan] = useState<string | null>(null);
  const [fatura, setFatura] = useState({ tc: "", telefon: "", adres: "", sehir: "", posta: "" });
  const [kayitliAdresVar, setKayitliAdresVar] = useState(false);
  const [kayitliTelefonVar, setKayitliTelefonVar] = useState(false);
  const [farkliGir, setFarkliGir] = useState(false);
  const [adresKaydet, setAdresKaydet] = useState(false);
  const [modalHata, setModalHata] = useState<string | null>(null);
  const [eksik, setEksik] = useState<Set<string>>(new Set());
  // iyzico gömülü ödeme formu (checkoutFormContent) — temiz bir popup içinde gösterilir.
  const [iyzicoForm, setIyzicoForm] = useState<string | null>(null);

  // Fiyatlandırma sayfasından "?plan=<key>" ile gelindiyse o planı öne çıkar.
  const hedefPlan = sp.get("plan");

  // Profilde kayıtlı fatura bilgilerini modal'a ön-doldur.
  useEffect(() => {
    fetch("/api/proxy/me", { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => {
        const b = j?.data?.user?.billing;
        if (b && typeof b === "object") {
          setFatura((f) => ({
            tc: f.tc || b.vergi_no || "",
            telefon: f.telefon || b.telefon || "",
            adres: f.adres || b.adres || "",
            sehir: f.sehir || b.sehir || "",
            posta: f.posta || b.posta || "",
          }));
          if (b.adres && b.sehir) setKayitliAdresVar(true);
          if (b.telefon) setKayitliTelefonVar(true);
        }
      })
      .catch(() => {});
  }, []);

  function alanGuncelle(key: "tc" | "telefon" | "adres" | "sehir" | "posta", value: string) {
    setFatura((f) => ({ ...f, [key]: value }));
    setEksik((s) => {
      if (!s.has(key)) return s;
      const n = new Set(s); n.delete(key); return n;
    });
  }

  useEffect(() => {
    // /current kendi kendine onarır (tenant planı + ödeme kaydı); tamamlanınca
    // sidebar/header plan rozetini tazele.
    loadCurrent().then(() => refreshPlan());
    // Callback handling
    const callback = sp.get("callback");
    const token = sp.get("token");
    if (callback && token) handleCallback(token);
    if (sp.get("mock") === "1") {
      setSuccess("DEV MODE — Mock checkout başarılı görünür. Production'da iyzico'ya yönlendirilir.");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Hedef plana kaydır + ücretli plansa ödeme modalını otomatik aç (kayıt/abonelik
  // akışından "?plan=" ile gelindiğinde kullanıcı doğrudan ödemeye yönlendirilir).
  useEffect(() => {
    if (loading || !hedefPlan) return;
    const el = document.getElementById(`plan-${hedefPlan}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    const odenebilir = ["pro_solo", "pro_solo_uyap", "team", "team_uyap"].includes(hedefPlan);
    if (SATIS_ACIK && odenebilir && hedefPlan !== (current?.plan || "free")) {
      setSecilenPlan(hedefPlan);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, hedefPlan]);

  async function loadCurrent() {
    try {
      const r = await fetch("/api/proxy/billing/current");
      const j = await r.json();
      if (r.ok) setCurrent(j.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }

  async function handleCallback(token: string) {
    // POST'u token başına yalnızca bir kez yap; iki mount da aynı promise'i bekler.
    let p = _subTokenSonuc.get(token);
    if (!p) {
      p = (async () => {
        try {
          const r = await fetch("/api/proxy/billing/callback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
          });
          const j = await r.json();
          return { ok: r.ok && j?.ok, message: j?.message };
        } catch (err) {
          return { ok: false, message: err instanceof Error ? err.message : "Bağlantı hatası." };
        }
      })();
      _subTokenSonuc.set(token, p);
    }
    const sonuc = await p;
    if (sonuc.ok) {
      setError(null);
      setBasari(sonuc.message || "Aboneliğiniz aktif! Tüm Pro özellikler açıldı.");
      await loadCurrent();
      refreshPlan(); // sidebar/header plan rozetini anında tazele
      router.replace("/panel/ayarlar/abonelik");
    } else {
      setError(sonuc.message || "Ödeme onaylanamadı.");
    }
  }

  // "Bu Plana Geç" → fatura bilgisi modalını aç.
  function planSec(planKey: string) {
    setError(null); setModalHata(null); setFarkliGir(false);
    setSecilenPlan(planKey);
  }

  // Modal "Öde" → fatura bilgileriyle abonelik checkout başlat.
  async function startCheckout() {
    const planKey = secilenPlan;
    if (!planKey) return;
    const eks = new Set<string>();
    if (fatura.tc.trim().length !== 11) eks.add("tc");
    if (!fatura.telefon.trim()) eks.add("telefon");
    if (!fatura.adres.trim()) eks.add("adres");
    if (!fatura.sehir.trim()) eks.add("sehir");
    if (eks.size > 0) {
      setEksik(eks);
      setModalHata("Lütfen yıldız (*) işaretli zorunlu alanları doldurun.");
      return;
    }
    setEksik(new Set()); setModalHata(null); setCheckingOut(planKey);
    try {
      const r = await fetch("/api/proxy/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_tier: planKey,
          identity_no: fatura.tc.trim() || null,
          phone: fatura.telefon.trim() || null,
          address: fatura.adres.trim() || null,
          city: fatura.sehir.trim() || null,
          zip_code: fatura.posta.trim() || null,
        }),
      });
      const j = await r.json();
      if (!r.ok) {
        setModalHata(j?.message || j?.detail || "Checkout başlatılamadı.");
        return;
      }
      // Telefonu her zaman kaydet (bir kez girilince bir daha sorma).
      // Adres de kaydet checkbox'ı işaretliyse veya zaten kayıtlı değilse adresi de yaz.
      const telefonuKaydet = fatura.telefon.trim() && !kayitliTelefonVar;
      const adresiKaydet = adresKaydet && !kayitliAdresVar;
      if (telefonuKaydet || adresiKaydet) {
        try {
          const billing: Record<string, string> = { telefon: fatura.telefon.trim() };
          if (adresiKaydet) {
            billing.adres = fatura.adres.trim();
            billing.sehir = fatura.sehir.trim();
            billing.posta = fatura.posta.trim();
          }
          await fetch("/api/proxy/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ billing }),
          });
          if (adresiKaydet) setKayitliAdresVar(true);
          if (telefonuKaydet) setKayitliTelefonVar(true);
        } catch { /* kayıt başarısızsa engelleme */ }
      }
      const d = j?.data ?? j;
      setSecilenPlan(null);
      if (d?.payment_page_url) {
        // (Tek seferlik akış) hosted sayfa → yönlendir.
        window.location.href = d.payment_page_url;
      } else if (d?.checkout_form_content) {
        // Abonelik → gömülü iyzico formu, TEMİZ BİR POPUP içinde gösterilir.
        // Ödeme tamamlanınca iyzico callbackUrl'e döner → handleCallback çalışır.
        setIyzicoForm(d.checkout_form_content);
      } else {
        setError("Ödeme formu alınamadı.");
      }
    } catch {
      setModalHata("Checkout sırasında hata oluştu.");
    } finally { setCheckingOut(null); }
  }

  // iyzico formu popup açıldığında script'i konteynere enjekte et. Konteyner
  // Portal içinde olduğundan DOM'a gelene kadar kısa aralıklarla yeniden dene.
  useEffect(() => {
    if (!iyzicoForm) return;
    let durduruldu = false;
    let deneme = 0;
    const enjekteEt = () => {
      if (durduruldu) return;
      const c = document.getElementById("iyzipay-checkout-form");
      if (!c) {
        if (deneme++ < 20) setTimeout(enjekteEt, 50);
        return;
      }
      c.innerHTML = "";
      const temp = document.createElement("div");
      temp.innerHTML = iyzicoForm;
      Array.from(temp.querySelectorAll("script")).forEach((old) => {
        const s = document.createElement("script");
        if (old.src) s.src = old.src;
        else s.textContent = old.textContent;
        s.async = false;
        document.body.appendChild(s);
      });
    };
    enjekteEt();
    return () => { durduruldu = true; };
  }, [iyzicoForm]);

  async function cancelSub() {
    if (!confirm("Aboneliğiniz dönem sonunda iptal edilecek. Onaylıyor musunuz?")) return;
    try {
      const r = await fetch("/api/proxy/billing/cancel", { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "İptal edilemedi");
      setSuccess(j.message || "Abonelik iptal edildi.");
      await loadCurrent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    }
  }

  const activePlan = current?.plan || "free";

  return (
    <>
      <BasariModal
        open={!!basari}
        baslik="Aboneliğiniz aktif 🎉"
        aciklama={basari ?? undefined}
        onKapat={() => setBasari(null)}
        ctaHref="/panel"
        ctaLabel="Panele git"
      />

      {/* Ödeme bilgisi modalı — abonelik için (iyzico TC/adres gerektirir) */}
      {secilenPlan && (() => {
        const sp2 = PLANS.find((p) => p.key === secilenPlan);
        const yukleniyor = checkingOut === secilenPlan;
        return (
          <Portal>
            <div
              className="fixed inset-0 z-[100] flex items-center justify-center bg-foreground/25 backdrop-blur-sm p-4 animate-fade-in"
              onClick={() => !yukleniyor && setSecilenPlan(null)}
              role="dialog"
              aria-modal="true"
            >
              <div
                className="w-full max-w-md rounded-xl border bg-background p-6 shadow-2xl max-h-[90vh] overflow-auto"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="text-lg font-semibold">Ödeme bilgileri</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  <strong>{sp2?.name}</strong> — {sp2?.price}
                </p>
                <div className="mt-3 flex items-start gap-2 rounded-md border border-primary/30 bg-primary/5 p-3 text-xs text-muted-foreground">
                  <ShieldCheck className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                  <span>
                    TC Kimlik No yalnızca ödeme kuruluşu <strong>iyzico</strong> tarafından yasal
                    zorunluluk (MASAK) gereği istenir; <strong>tarafımızda saklanmaz</strong>,
                    yalnızca ödeme anında güvenli şekilde iletilir.
                  </span>
                </div>

                <div className="mt-4 space-y-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">
                      TC Kimlik No <span className="text-destructive">*</span>
                    </label>
                    <input
                      inputMode="numeric" maxLength={11} value={fatura.tc}
                      onChange={(e) => alanGuncelle("tc", e.target.value.replace(/\D/g, ""))}
                      placeholder="11 haneli TC Kimlik No"
                      className={`mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${eksik.has("tc") ? "border-destructive ring-1 ring-destructive" : ""}`}
                    />
                  </div>

                  {/* Telefon — her zaman göster, bir kez girilince kaydedilir */}
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">
                      Cep telefonu <span className="text-destructive">*</span>
                    </label>
                    <input
                      inputMode="tel" value={fatura.telefon}
                      onChange={(e) => alanGuncelle("telefon", e.target.value)}
                      placeholder="05XXXXXXXXX"
                      className={`mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${eksik.has("telefon") ? "border-destructive ring-1 ring-destructive" : ""}`}
                    />
                  </div>

                  {kayitliAdresVar && !farkliGir ? (
                    <div className="rounded-md border bg-secondary/40 p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">Kayıtlı fatura adresi</span>
                        <button type="button" onClick={() => setFarkliGir(true)} className="text-xs text-primary hover:underline shrink-0">
                          Farklı adres gir
                        </button>
                      </div>
                      <p className="mt-1 text-muted-foreground">
                        {fatura.adres}, {fatura.sehir}
                        {fatura.posta ? ` ${fatura.posta}` : ""}
                        {fatura.telefon ? ` · ${fatura.telefon}` : ""}
                      </p>
                    </div>
                  ) : (
                    <>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">
                          Fatura adresi <span className="text-destructive">*</span>
                        </label>
                        <input
                          value={fatura.adres}
                          onChange={(e) => alanGuncelle("adres", e.target.value)}
                          placeholder="Adres"
                          className={`mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${eksik.has("adres") ? "border-destructive ring-1 ring-destructive" : ""}`}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs font-medium text-muted-foreground">
                            Şehir <span className="text-destructive">*</span>
                          </label>
                          <input
                            value={fatura.sehir}
                            onChange={(e) => alanGuncelle("sehir", e.target.value)}
                            placeholder="İstanbul"
                            className={`mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${eksik.has("sehir") ? "border-destructive ring-1 ring-destructive" : ""}`}
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-muted-foreground">
                            Posta kodu <span className="text-muted-foreground/60">(opsiyonel)</span>
                          </label>
                          <input
                            inputMode="numeric" value={fatura.posta}
                            onChange={(e) => alanGuncelle("posta", e.target.value)}
                            placeholder="34000"
                            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          />
                        </div>
                      </div>

                      {!kayitliAdresVar ? (
                        <Switch
                          checked={adresKaydet}
                          onChange={setAdresKaydet}
                          label="Bu fatura adresimi sonraki alımlar için kaydet"
                          className="pt-1"
                        />
                      ) : (
                        <button type="button" onClick={() => setFarkliGir(false)} className="text-xs text-primary hover:underline pt-1">
                          ← Kayıtlı adresimi kullan
                        </button>
                      )}
                    </>
                  )}
                </div>

                {modalHata && (
                  <div className="mt-3 rounded-md border border-destructive/50 bg-destructive/10 p-2.5 text-sm text-destructive">
                    ⚠️ {modalHata}
                  </div>
                )}

                <div className="mt-5 flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setSecilenPlan(null)} disabled={yukleniyor}>
                    İptal
                  </Button>
                  <Button onClick={startCheckout} disabled={yukleniyor}>
                    {yukleniyor ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : null}
                    {yukleniyor ? "Yönlendiriliyor…" : "Ödemeye geç"}
                  </Button>
                </div>
              </div>
            </div>
          </Portal>
        );
      })()}

      {/* iyzico ödeme formu — temiz popup (forma gömülü değil) */}
      {iyzicoForm && (
        <Portal>
          <div
            className="fixed inset-0 z-[120] flex items-start justify-center overflow-auto bg-foreground/30 backdrop-blur-sm p-4"
            role="dialog"
            aria-modal="true"
          >
            <div className="my-8 w-full max-w-md rounded-2xl border bg-card p-4 shadow-2xl">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-card-foreground">Güvenli Ödeme</span>
                <button
                  type="button"
                  onClick={() => setIyzicoForm(null)}
                  aria-label="Kapat"
                  className="rounded-md px-2 py-1 text-muted-foreground hover:bg-secondary"
                >
                  ✕
                </button>
              </div>
              {/* iyzico checkoutFormContent buraya render olur */}
              <div id="iyzipay-checkout-form" className="responsive" />
            </div>
          </div>
        </Portal>
      )}

      {success && (
        <Card className="bg-emerald-50 border-emerald-300">
          <CardContent className="p-4 text-sm text-emerald-900">✓ {success}</CardContent>
        </Card>
      )}
      {error && (
        <Card className="bg-destructive/10 border-destructive/50">
          <CardContent className="p-4 text-sm text-destructive">⚠ {error}</CardContent>
        </Card>
      )}

      <Card className="relative overflow-hidden border-primary/30 bg-gradient-to-br from-primary/10 via-primary/[0.04] to-transparent">
        {/* İnce dekoratif ışıma — sade ama nefes alan bir his verir. */}
        <div className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-primary/10 blur-3xl" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
        <CardHeader className="relative">
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="flex items-center gap-2.5 text-base sm:text-lg">
              <span className="rounded-xl bg-primary/15 p-2 text-primary ring-1 ring-primary/20">
                <Crown className="h-5 w-5" />
              </span>
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] font-normal uppercase tracking-wider text-muted-foreground">
                  Mevcut Plan
                </span>
                <span className="text-primary">
                  {PLANS.find((p) => p.key === activePlan)?.name || activePlan}
                </span>
              </span>
            </CardTitle>
            <div className="flex flex-col items-end gap-1.5">
              <span className="text-sm font-semibold tabular-nums">
                {PLANS.find((p) => p.key === activePlan)?.price}
              </span>
              {(() => {
                const cancel = current?.cancel_at_period_end;
                const free = activePlan === "free";
                const cls = cancel
                  ? "border-amber-400/40 bg-amber-400/15 text-amber-700 dark:text-amber-300"
                  : free
                  ? "border-border bg-muted text-muted-foreground"
                  : "border-emerald-400/40 bg-emerald-400/15 text-emerald-700 dark:text-emerald-300";
                const txt = cancel ? "İptal edilecek" : free ? "Ücretsiz" : "Aktif";
                return (
                  <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${cls}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${cancel ? "bg-amber-500" : free ? "bg-muted-foreground/50" : "bg-emerald-500"}`} />
                    {txt}
                  </span>
                );
              })()}
            </div>
          </div>
          {current?.period_end && (
            <CardDescription className="pt-1">
              {current.cancel_at_period_end
                ? `Dönem sonu: ${new Date(current.period_end).toLocaleDateString("tr-TR")} (iptal edilecek)`
                : `Sonraki yenileme: ${new Date(current.period_end).toLocaleDateString("tr-TR")}`}
            </CardDescription>
          )}
        </CardHeader>
        {current && current.plan !== "free" && !current.cancel_at_period_end && (
          <CardContent className="relative">
            <Button onClick={cancelSub} variant="outline" size="sm">Aboneliği İptal Et</Button>
          </CardContent>
        )}
      </Card>

      {loading ? (
        <div className="grid md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-80 rounded-lg bg-muted animate-pulse" />)}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PLANS.map((p, i) => {
            const isCurrent = p.key === activePlan;
            const isHedef = p.key === hedefPlan && !isCurrent;
            return (
              <Card
                key={p.key}
                id={`plan-${p.key}`}
                className={
                  "group relative flex h-full flex-col transition-all duration-300 ease-out " +
                  // Pakete göre hover efekti (aktif plan kartı hariç — o eylemsiz).
                  (isCurrent ? "" : EFEKT[i] + " ") +
                  (isHedef
                    ? "border-primary ring-2 ring-primary shadow-lg"
                    : p.popular
                    ? "border-accent shadow-md"
                    : isCurrent
                    ? "border-primary"
                    : "")
                }
              >
                <CardHeader>
                  {p.popular && (
                    <span className="text-xs bg-accent text-accent-foreground px-2 py-0.5 rounded uppercase tracking-wider self-start mb-2">
                      Popüler
                    </span>
                  )}
                  {isCurrent && (
                    <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded self-start mb-2">
                      Aktif Plan
                    </span>
                  )}
                  <CardTitle>{p.name}</CardTitle>
                  <div className="text-3xl font-bold mt-2 origin-left transition-transform duration-300 group-hover:scale-[1.04]">
                    {p.price}
                  </div>
                  <CardDescription>{p.desc}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col">
                  <ul className="space-y-2 text-sm mb-6 flex-1">
                    {p.features.map((f) => (
                      <li key={f} className="flex gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  {p.key === "enterprise" ? (
                    <Button asChild className="w-full" variant="outline">
                      <a href="mailto:satis@hukukcuyapayzekasi.com?subject=Enterprise%20paket">İletişime Geç</a>
                    </Button>
                  ) : isCurrent ? (
                    <Button disabled className="w-full" variant="outline">Aktif Plan</Button>
                  ) : !SATIS_ACIK ? (
                    /* LANSMAN MODU — satış kapalı, bekleme listesine yönlendir.
                       Satış açılınca (SATIS_ACIK=true) alttaki normal akış geri gelir. */
                    p.key === "free" ? (
                      <Button disabled className="w-full" variant="outline">Bu Plana Geç</Button>
                    ) : (
                      <Button asChild variant={p.popular ? "default" : "outline"} className="w-full">
                        <Link href={`/bekleme-listesi?plan=${p.key}`}>Bekleme Listesine Katıl</Link>
                      </Button>
                    )
                  ) : (
                    <Button
                      onClick={() => planSec(p.key)}
                      disabled={checkingOut === p.key || p.key === "free"}
                      variant={p.popular ? "default" : "outline"}
                      className="w-full"
                    >
                      {checkingOut === p.key ? (
                        "Yükleniyor…"
                      ) : (
                        "Bu Plana Geç"
                      )}
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
  