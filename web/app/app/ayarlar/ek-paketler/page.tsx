"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Package, Check, Sparkles, Coins, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BasariModal } from "@/components/basari-modal";
import { CountUp } from "@/components/count-up";
import { Portal } from "@/components/portal";
import { Switch } from "@/components/ui/switch";
import { refreshPlan } from "@/lib/use-plan";

export default function EkPaketlerPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-muted-foreground"><Loader2 className="h-7 w-7 animate-spin mx-auto" /></div>}>
      <EkPaketlerIcerik />
    </Suspense>
  );
}

type Pack = {
  key: string;
  ad: string;
  aciklama: string;
  modul: string | null;
  krediler: Record<string, number>;
  amount_try: number;
  currency: string;
  bundle: boolean;
};
type Bakiye = { module: string; modul_etiket: string; balance: number };

// Token başına callback sonucu (Promise). StrictMode efekti 2 kez çalıştırsa da
// POST yalnızca BİR kez yapılır; iki mount da AYNI promise'i bekler, böylece sonucu
// (başarı/başarısızlık) CANLI olan mount güvenle gösterir — popup kaçmaz.
const tokenSonuc = new Map<string, Promise<{ ok: boolean; message?: string }>>();

function EkPaketlerIcerik() {
  const sp = useSearchParams();
  const router = useRouter();
  const vurguModul = sp.get("modul");

  const [packs, setPacks] = useState<Pack[] | null>(null);
  const [bakiyeler, setBakiyeler] = useState<Bakiye[]>([]);
  const [loading, setLoading] = useState(true);
  const [satinAlinan, setSatinAlinan] = useState<string | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  // Belirgin başarı popup'ı (satın alma tamamlandı)
  const [basari, setBasari] = useState<string | null>(null);
  // Fatura modalı (iyzico canlı modda TC/telefon/adres ister)
  const [faturaPaket, setFaturaPaket] = useState<Pack | null>(null);
  const [fatura, setFatura] = useState({ tc: "", telefon: "", adres: "", sehir: "", posta: "" });
  const [modalHata, setModalHata] = useState<string | null>(null);
  const [eksikAlanlar, setEksikAlanlar] = useState<Set<string>>(new Set());
  // Kayıtlı fatura adresi var mı? Varsa adres sorulmaz (özet gösterilir).
  const [kayitliAdresVar, setKayitliAdresVar] = useState(false);
  const [farkliGir, setFarkliGir] = useState(false);   // "farklı adres gir" açıldı mı
  const [adresKaydet, setAdresKaydet] = useState(false); // kayıtlı değilse: kaydet toggle

  // Alanı güncelle + o alanın "eksik" işaretini temizle.
  function alanGuncelle(key: "tc" | "telefon" | "adres" | "sehir" | "posta", value: string) {
    setFatura((f) => ({ ...f, [key]: value }));
    setEksikAlanlar((s) => {
      if (!s.has(key)) return s;
      const n = new Set(s);
      n.delete(key);
      return n;
    });
  }

  const yukle = useCallback(async () => {
    setLoading(true);
    try {
      const [pr, kr] = await Promise.all([
        fetch("/api/proxy/billing/addons", { cache: "no-store" }),
        fetch("/api/proxy/me/krediler", { cache: "no-store" }),
      ]);
      const pj = await pr.json();
      setPacks((pj?.data ?? pj)?.packs ?? []);
      if (kr.ok) {
        const kj = await kr.json();
        setBakiyeler((kj?.data ?? kj)?.bakiyeler ?? []);
      }
    } catch {
      setHata("Paketler yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Profilde kayıtlı fatura bilgilerini ödeme modalına ön-doldur (boş alanları).
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
          // Adres + şehir kayıtlıysa alımda adres sorulmaz, özet gösterilir.
          if (b.adres && b.sehir) setKayitliAdresVar(true);
        }
      })
      .catch(() => {});
  }, []);

  // iyzico dönüşü (?callback=1&token=...) → krediyi yükle.
  // Token yoksa: kaçan ödemeleri (callback ulaşmamış) doğrula (reconcile).
  useEffect(() => {
    let alive = true;
    (async () => {
      const token = sp.get("token");
      if (token) {
        // POST'u token başına yalnızca bir kez yap; iki mount da aynı promise'i bekler.
        let p = tokenSonuc.get(token);
        if (!p) {
          p = (async () => {
            try {
              const r = await fetch("/api/proxy/billing/addons/callback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token }),
              });
              const j = await r.json();
              return { ok: !!j?.ok, message: j?.message };
            } catch {
              return { ok: false, message: "Ödeme doğrulanamadı." };
            }
          })();
          tokenSonuc.set(token, p);
        }
        const sonuc = await p;
        if (alive) {
          if (sonuc.ok) {
            setBasari("Krediniz hesabınıza tanımlandı, hemen kullanmaya başlayabilirsiniz.");
            refreshPlan();
          } else {
            setHata(sonuc.message || "Ödeme doğrulanamadı.");
          }
          await yukle();
          // Token'ı URL'den temizle → sayfa yenilenince popup tekrar açılmaz.
          router.replace("/app/ayarlar/ek-paketler");
        }
        return;
      } else {
        // Önceki ödemelerden kredisi yüklenmemiş olan var mı? iyzico'dan doğrula.
        try {
          const r = await fetch("/api/proxy/billing/addons/reconcile", { method: "POST" });
          const j = await r.json();
          if (alive && (j?.data?.yuklenen ?? 0) > 0) {
            setMesaj("Önceki ödemeniz doğrulandı, krediler hesabınıza tanımlandı.");
          }
        } catch { /* yok say */ }
      }
      await yukle();
    })();
    return () => { alive = false; };
  }, [sp, yukle, router]);

  // "Satın al" → fatura bilgisi modalını aç.
  function satinAl(pack: Pack) {
    setHata(null); setMesaj(null); setModalHata(null);
    setFarkliGir(false); // kayıtlı adres varsa özetle aç
    setFaturaPaket(pack);
  }

  // Modal "Öde" → fatura bilgileriyle checkout başlat.
  async function checkoutGonder() {
    const pack = faturaPaket;
    if (!pack) return;
    // Zorunlu alanlar (iyzico gereği): TC, adres, şehir. Telefon/posta opsiyonel.
    const eksik = new Set<string>();
    if (fatura.tc.trim().length !== 11) eksik.add("tc");
    if (!fatura.adres.trim()) eksik.add("adres");
    if (!fatura.sehir.trim()) eksik.add("sehir");
    if (eksik.size > 0) {
      setEksikAlanlar(eksik);
      setModalHata("Lütfen yıldız (*) işaretli zorunlu alanları doldurun.");
      return;
    }
    setEksikAlanlar(new Set());
    setModalHata(null);
    setSatinAlinan(pack.key);
    try {
      const r = await fetch("/api/proxy/billing/addons/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pack_key: pack.key,
          identity_no: fatura.tc.trim() || null,
          phone: fatura.telefon.trim() || null,
          address: fatura.adres.trim() || null,
          city: fatura.sehir.trim() || null,
          zip_code: fatura.posta.trim() || null,
        }),
      });
      const j = await r.json();
      if (!r.ok) {
        // Backend doğrulama hatasını modal içinde göster (ör. geçersiz TC).
        setModalHata(j?.message || j?.detail || "Satın alma başlatılamadı.");
        return;
      }
      // "Fatura adresimi kaydet" işaretliyse (ve önceden kayıtlı değilse) profile yaz.
      // NOT: TC kimlik yasal gereği saklanmaz; yalnızca adres bilgisi kaydedilir.
      if (adresKaydet && !kayitliAdresVar) {
        try {
          await fetch("/api/proxy/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              billing: {
                adres: fatura.adres.trim(),
                sehir: fatura.sehir.trim(),
                posta: fatura.posta.trim(),
                telefon: fatura.telefon.trim(),
              },
            }),
          });
          setKayitliAdresVar(true);
        } catch { /* kayıt başarısızsa alımı engelleme */ }
      }
      const d = j?.data ?? j;
      setFaturaPaket(null);
      if (d?.granted || d?.dev_mode) {
        setBasari(`${pack.ad} hesabınıza tanımlandı.`);
        refreshPlan();
        await yukle();
      } else if (d?.payment_page_url) {
        window.location.href = d.payment_page_url;
      } else {
        setMesaj("Satın alma başlatıldı.");
      }
    } catch {
      setModalHata("Satın alma sırasında hata oluştu.");
    } finally {
      setSatinAlinan(null);
    }
  }

  const tekil = (packs ?? []).filter((p) => !p.bundle);
  const bundle = (packs ?? []).filter((p) => p.bundle);

  return (
    <div className="space-y-6">
      <BasariModal
        open={!!basari}
        baslik="Satın alma tamamlandı 🎉"
        aciklama={basari ?? undefined}
        onKapat={() => setBasari(null)}
      />

      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Package className="h-6 w-6 text-primary" /> Ek Paketler
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Üst pakete geçmeden, ihtiyacınız olan modülden ek kullanım paketi alın.
          Krediler hesabınıza tanımlanır ve <strong>süresiz</strong> geçerlidir.
        </p>
      </div>

      {mesaj && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 flex items-center gap-2">
          <Check className="h-4 w-4" /> {mesaj}
        </div>
      )}
      {hata && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          ⚠️ {hata}
        </div>
      )}

      {/* Mevcut bakiyeler — premium gold temalı, dikkat çeken kart */}
      <Card className="relative overflow-hidden border-[#D4AF37]/45 bg-gradient-to-br from-[#F7E9C2]/70 via-[#FCF6E1]/40 to-transparent shadow-[0_2px_18px_-6px_rgba(212,175,55,0.45)] dark:from-[#3a2f0a]/45 dark:via-[#2a2208]/15">
        {/* Metalik gold ışıma + üst kenar parıltısı */}
        <div className="pointer-events-none absolute -right-10 -top-10 h-36 w-36 rounded-full bg-[#D4AF37]/25 blur-3xl" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#D4AF37]/70 to-transparent" />
        <CardHeader className="relative pb-3">
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-base flex items-center gap-2">
              <span className="rounded-xl bg-gradient-to-br from-[#F4D77A] to-[#C9A227] p-2 text-[#5b4708] ring-1 ring-[#D4AF37]/40 shadow-sm">
                <Coins className="h-5 w-5" />
              </span>
              Kredi bakiyeniz
            </CardTitle>
            {bakiyeler.length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[#D4AF37]/50 bg-[#D4AF37]/15 px-3 py-1 text-sm font-semibold text-[#9A7B12] dark:text-[#E8C95B]">
                <Coins className="h-3.5 w-3.5" />
                Toplam {bakiyeler.reduce((s, b) => s + b.balance, 0)} kredi
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="relative">
          {bakiyeler.length === 0 ? (
            <div className="flex items-center gap-3 rounded-lg border border-dashed border-[#D4AF37]/45 bg-background/40 p-4">
              <Coins className="h-8 w-8 text-[#D4AF37]/80 shrink-0" />
              <div className="text-sm">
                <p className="font-medium">Henüz ek paket krediniz yok.</p>
                <p className="text-muted-foreground">Aşağıdan ihtiyacınız olan modülden paket alın; krediler süresiz geçerlidir.</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {bakiyeler.map((b) => (
                <div
                  key={b.module}
                  className="hover-lift rounded-xl border border-[#D4AF37]/45 bg-card/80 p-3 backdrop-blur"
                >
                  <div className="text-2xl font-bold tabular-nums text-[#B8860B] dark:text-[#E8C95B] leading-none">
                    <CountUp value={b.balance} />
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground truncate">{b.modul_etiket}</div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {loading && (
        <div className="p-10 text-center text-muted-foreground">
          <Loader2 className="h-7 w-7 animate-spin mx-auto" />
        </div>
      )}

      {!loading && (
        <>
          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Modül paketleri</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {tekil.map((p) => (
                <PaketKart key={p.key} p={p} vurgu={p.modul === vurguModul}
                           yukleniyor={satinAlinan === p.key} onBuy={() => satinAl(p)} />
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Avantajlı paketler</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {bundle.map((p) => (
                <PaketKart key={p.key} p={p} bundle yukleniyor={satinAlinan === p.key} onBuy={() => satinAl(p)} />
              ))}
            </div>
          </section>
        </>
      )}

      {/* Fatura bilgisi modalı — iyzico ödeme için gerekli */}
      {faturaPaket && (
        <Portal>
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-foreground/25 backdrop-blur-sm p-4 animate-fade-in"
          onClick={() => !satinAlinan && setFaturaPaket(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="w-full max-w-md rounded-xl border bg-background p-6 shadow-xl max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold">Ödeme bilgileri</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              <strong>{faturaPaket.ad}</strong> — {faturaPaket.amount_try.toLocaleString("tr-TR")} ₺.
            </p>
            <div className="mt-3 flex items-start gap-2 rounded-md border border-primary/30 bg-primary/5 p-3 text-xs text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-primary mt-0.5 shrink-0" />
              <span>
                TC Kimlik No, yalnızca ödeme kuruluşu <strong>iyzico</strong> tarafından yasal
                zorunluluk (MASAK) gereği istenir. Bu bilgi <strong>tarafımızda hiçbir şekilde
                saklanmaz</strong>; yalnızca ödeme anında güvenli şekilde iyzico'ya iletilir.
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
                  className={`mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${eksikAlanlar.has("tc") ? "border-destructive ring-1 ring-destructive" : ""}`}
                />
              </div>
              {kayitliAdresVar && !farkliGir ? (
                /* Kayıtlı fatura adresi → sorma, özet göster (değiştirme seçeneğiyle) */
                <div className="rounded-md border bg-secondary/40 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">Kayıtlı fatura adresi</span>
                    <button
                      type="button"
                      onClick={() => setFarkliGir(true)}
                      className="text-xs text-primary hover:underline shrink-0"
                    >
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
                      Cep telefonu <span className="text-muted-foreground/60">(opsiyonel)</span>
                    </label>
                    <input
                      inputMode="tel" value={fatura.telefon}
                      onChange={(e) => alanGuncelle("telefon", e.target.value)}
                      placeholder="05XXXXXXXXX"
                      className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">
                      Fatura adresi <span className="text-destructive">*</span>
                    </label>
                    <input
                      value={fatura.adres}
                      onChange={(e) => alanGuncelle("adres", e.target.value)}
                      placeholder="Adres"
                      className={`mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${eksikAlanlar.has("adres") ? "border-destructive ring-1 ring-destructive" : ""}`}
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
                        className={`mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${eksikAlanlar.has("sehir") ? "border-destructive ring-1 ring-destructive" : ""}`}
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
                    /* Kayıtlı adres yok → kaydetme toggle'ı */
                    <Switch
                      checked={adresKaydet}
                      onChange={setAdresKaydet}
                      label="Bu fatura adresimi sonraki alımlar için kaydet"
                      className="pt-1"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => setFarkliGir(false)}
                      className="text-xs text-primary hover:underline pt-1"
                    >
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
              <Button variant="outline" onClick={() => setFaturaPaket(null)} disabled={!!satinAlinan}>
                İptal
              </Button>
              <Button onClick={checkoutGonder} disabled={!!satinAlinan}>
                {satinAlinan ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Package className="h-4 w-4 mr-1.5" />}
                {satinAlinan ? "İşleniyor…" : `Öde · ${faturaPaket.amount_try.toLocaleString("tr-TR")} ₺`}
              </Button>
            </div>
          </div>
        </div>
        </Portal>
      )}
    </div>
  );
}

function PaketKart({
  p, vurgu, bundle, yukleniyor, onBuy,
}: {
  p: Pack; vurgu?: boolean; bundle?: boolean; yukleniyor: boolean; onBuy: () => void;
}) {
  return (
    <Card className={vurgu ? "border-primary ring-2 ring-primary/30" : bundle ? "border-primary/30 bg-gradient-to-br from-primary/5 to-transparent" : ""}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          {bundle ? <Sparkles className="h-4 w-4 text-primary" /> : <Package className="h-4 w-4 text-primary" />}
          {vurgu && <span className="text-[10px] uppercase tracking-wider rounded-full bg-primary/10 text-primary px-2 py-0.5">İhtiyacınız</span>}
        </div>
        <CardTitle className="text-base mt-1">{p.ad}</CardTitle>
        <CardDescription>{p.aciklama}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-2xl font-bold">
          {p.amount_try.toLocaleString("tr-TR")} <span className="text-sm font-normal text-muted-foreground">₺</span>
        </div>
        <Button className="w-full" onClick={onBuy} disabled={yukleniyor}>
          {yukleniyor ? <Loader2 className="h-4 w-4 animate-spin" /> : <Package className="h-4 w-4 mr-1.5" />}
          {yukleniyor ? "İşleniyor…" : "Satın al"}
        </Button>
      </CardContent>
    </Card>
  );
}
