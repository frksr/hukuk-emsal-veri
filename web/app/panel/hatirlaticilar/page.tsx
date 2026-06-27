"use client";
import { useEffect, useRef, useState } from "react";
import { Loader2, Bell, Plus, Trash2, Pencil, X, Clock, CheckCircle2, AlertCircle, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useConfirm } from "@/components/confirm-dialog";
import { usePlan } from "@/lib/use-plan";
import { AracYukleniyor } from "@/components/arac-yukleniyor";
import { ProUpsell } from "@/components/pro-upsell";
import { ListSkeleton } from "@/components/list-skeleton";

type Hatirlatici = {
  id: string;
  baslik: string;
  not_metni: string | null;
  kaynak_tip: string;
  kaynak_id: string | null;
  kaynak_ozet: string | null;
  remind_at: string;
  channel: string;
  status: string;
  sent_at: string | null;
};

type Kaynaklar = {
  notlar: { id: string; baslik: string }[];
  uretimler: { id: string; tool: string; baslik: string }[];
  dosyalar: { id: string; baslik: string }[];
};

const BOS = {
  baslik: "",
  not_metni: "",
  remind_at: "",
  kaynak_tip: "serbest",
  kaynak_id: "",
  kaynak_ozet: "",
  channel: "email",
};

// "2026-06-20T14:30" (datetime-local) -> ISO; boş ise ""
function toISO(local: string): string {
  if (!local) return "";
  const d = new Date(local);
  return isNaN(d.getTime()) ? "" : d.toISOString();
}
// ISO -> datetime-local input değeri (yerel saat)
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const off = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - off).toISOString().slice(0, 16);
}

function durumRozeti(h: Hatirlatici) {
  if (h.status === "sent")
    return <span className="inline-flex items-center gap-1 text-xs text-green-600"><CheckCircle2 className="h-3.5 w-3.5" /> Gönderildi</span>;
  if (h.status === "failed")
    return <span className="inline-flex items-center gap-1 text-xs text-destructive"><AlertCircle className="h-3.5 w-3.5" /> Başarısız</span>;
  if (h.status === "canceled")
    return <span className="text-xs text-muted-foreground">İptal</span>;
  return <span className="inline-flex items-center gap-1 text-xs text-primary"><Clock className="h-3.5 w-3.5" /> Bekliyor</span>;
}

export default function HatirlaticilarPage() {
  const { loading: planLoading, isLoggedIn, isPaid } = usePlan();
  const [liste, setListe] = useState<Hatirlatici[] | null>(null);
  const [kaynaklar, setKaynaklar] = useState<Kaynaklar | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ ...BOS });
  const [editId, setEditId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { confirm, dialog } = useConfirm();
  // Yapay Zeka ile oluşturma
  const [aiMetin, setAiMetin] = useState("");
  const [aiYukleniyor, setAiYukleniyor] = useState(false);
  const [aiSorular, setAiSorular] = useState<{ alan: string; soru: string }[]>([]);
  const [aiSonuc, setAiSonuc] = useState(false);
  // Adım adım eksik alan sorusu
  const [aiAdim, setAiAdim] = useState(0);
  const [aiAdimCevap, setAiAdimCevap] = useState("");
  // Cache: aynı metin için tekrar AI'a gitme
  type AiCache = { baslik: string | null; remind_at: string | null; not_metni: string | null; eksik: { alan: string; soru: string }[] };
  const aiCacheRef = useRef<Map<string, AiCache>>(new Map());

  async function yukle() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/hatirlatici/", { cache: "no-store" });
      if (!r.ok) throw new Error("Hatırlatıcılar yüklenemedi.");
      const j = await r.json();
      setListe((j?.data ?? j)?.hatirlaticilar ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  async function kaynaklariYukle() {
    try {
      const r = await fetch("/api/proxy/hatirlatici/kaynaklar", { cache: "no-store" });
      if (!r.ok) return;
      const j = await r.json();
      const d = j?.data ?? j;
      setKaynaklar({
        notlar: d?.notlar ?? [],
        uretimler: d?.uretimler ?? [],
        dosyalar: d?.dosyalar ?? [],
      });
    } catch {
      /* yok say */
    }
  }

  useEffect(() => {
    if (!planLoading && isPaid) {
      yukle();
      kaynaklariYukle();
    }
  }, [planLoading, isPaid]);

  function reset() {
    setForm({ ...BOS });
    setEditId(null);
    setAiMetin("");
    setAiSorular([]);
    setAiSonuc(false);
    setAiAdim(0);
    setAiAdimCevap("");
  }

  function _aiUygula(d: AiCache) {
    setForm((f) => ({
      ...f,
      baslik: d.baslik || f.baslik,
      remind_at: d.remind_at || f.remind_at,
      not_metni: d.not_metni || f.not_metni,
    }));
    setAiSorular(d.eksik ?? []);
    setAiAdim(0);
    setAiAdimCevap("");
    setAiSonuc(true);
  }

  async function aiHazirla() {
    const metin = aiMetin.trim();
    if (metin.length < 3) return;

    // Sonuç zaten gösteriliyorsa (kullanıcı tekrar bastı) — yineleme yok
    if (aiSonuc) return;

    // Cache'de varsa göndermeden uygula (kısa gecikmeyle "işleniyor" hissi ver)
    const cached = aiCacheRef.current.get(metin);
    if (cached) {
      setAiYukleniyor(true);
      await new Promise((r) => setTimeout(r, 400));
      _aiUygula(cached);
      setAiYukleniyor(false);
      return;
    }

    setAiYukleniyor(true);
    setError(null);
    try {
      const simdi = toLocalInput(new Date().toISOString());
      const r = await fetch("/api/proxy/hatirlatici/ai-tasla", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metin, simdi }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.message || "Yapay Zeka şu an yanıt veremedi.");
      const d = j?.data ?? j;
      const sonuc: AiCache = {
        baslik: d.baslik || null,
        remind_at: d.remind_at || null,
        not_metni: d.not_metni || metin,
        eksik: (d.eksik ?? []) as { alan: string; soru: string }[],
      };
      aiCacheRef.current.set(metin, sonuc);
      _aiUygula(sonuc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setAiYukleniyor(false);
    }
  }

  // Adım adım eksik alan cevabını uygula ve bir sonraki adıma geç
  function aiAdimIlerle() {
    const soruAlan = aiSorular[aiAdim]?.alan;
    if (!soruAlan || !aiAdimCevap.trim()) return;
    if (soruAlan === "baslik") {
      setForm((f) => ({ ...f, baslik: aiAdimCevap.trim() }));
    } else if (soruAlan === "remind_at") {
      setForm((f) => ({ ...f, remind_at: aiAdimCevap.trim() }));
    }
    setAiAdimCevap("");
    setAiAdim((i) => i + 1);
  }

  async function aiOlustur() {
    const remindISO = toISO(form.remind_at);
    if (!form.baslik.trim() || !remindISO) {
      setError("Lütfen başlık ve tarih/saat alanlarını doldurun.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/hatirlatici/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          baslik: form.baslik,
          not_metni: form.not_metni || null,
          kaynak_tip: "serbest",
          kaynak_id: null,
          kaynak_ozet: null,
          remind_at: remindISO,
          channel: "email",
        }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => null);
        throw new Error(j?.message || "Oluşturulamadı. Tarih gelecekte olmalı.");
      }
      reset();
      await yukle();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setSaving(false);
    }
  }

  // Kaynak seçimi: "tip:id" formatında değer; kaynak_tip/id/ozet doldurur.
  function kaynakSec(value: string) {
    if (!value || value === "serbest") {
      setForm((f) => ({ ...f, kaynak_tip: "serbest", kaynak_id: "", kaynak_ozet: "" }));
      return;
    }
    const [tip, id] = value.split("::");
    let ozet = "";
    if (tip === "not") ozet = kaynaklar?.notlar.find((x) => x.id === id)?.baslik ?? "";
    else if (tip === "uretim") ozet = kaynaklar?.uretimler.find((x) => x.id === id)?.baslik ?? "";
    else if (tip === "dosya") ozet = kaynaklar?.dosyalar.find((x) => x.id === id)?.baslik ?? "";
    setForm((f) => ({
      ...f,
      kaynak_tip: tip,
      kaynak_id: id,
      kaynak_ozet: ozet,
      baslik: f.baslik || ozet,
    }));
  }

  async function kaydet(e: React.FormEvent) {
    e.preventDefault();
    const remindISO = toISO(form.remind_at);
    if (!form.baslik.trim() || !remindISO) {
      setError("Başlık ve tarih/saat zorunludur.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (editId) {
        const r = await fetch(`/api/proxy/hatirlatici/${editId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            baslik: form.baslik,
            not_metni: form.not_metni || null,
            remind_at: remindISO,
          }),
        });
        if (!r.ok) throw new Error("Güncellenemedi.");
      } else {
        const r = await fetch("/api/proxy/hatirlatici/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            baslik: form.baslik,
            not_metni: form.not_metni || null,
            kaynak_tip: form.kaynak_tip,
            kaynak_id: form.kaynak_id || null,
            kaynak_ozet: form.kaynak_ozet || null,
            remind_at: remindISO,
            channel: "email",
          }),
        });
        if (!r.ok) {
          const j = await r.json().catch(() => null);
          throw new Error(j?.message || "Oluşturulamadı. Tarih gelecekte olmalı.");
        }
      }
      reset();
      await yukle();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setSaving(false);
    }
  }

  function duzenle(h: Hatirlatici) {
    setEditId(h.id);
    setForm({
      baslik: h.baslik,
      not_metni: h.not_metni || "",
      remind_at: toLocalInput(h.remind_at),
      kaynak_tip: h.kaynak_tip,
      kaynak_id: h.kaynak_id || "",
      kaynak_ozet: h.kaynak_ozet || "",
      channel: h.channel,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function sil(id: string) {
    const onay = await confirm("Bu hatırlatıcı kalıcı olarak silinecek. Devam edilsin mi?", {
      title: "Hatırlatıcıyı sil",
      confirmText: "Sil",
      danger: true,
    });
    if (!onay) return;
    await fetch(`/api/proxy/hatirlatici/${id}`, { method: "DELETE" });
    if (editId === id) reset();
    await yukle();
  }

  if (planLoading) return <AracYukleniyor />;

  if (!isPaid) {
    return (
      <ProUpsell
        isLoggedIn={isLoggedIn}
        baslik="Hatırlatıcılar"
        aciklama="Dava, dosya, not veya herhangi bir veriyle ilgili hatırlatıcı kurun; zamanı gelince e-posta ile uyaralım."
        ozellikler={[
          "Notlarınız, AI üretimleriniz veya dosyalarınızdan dinamik kaynak seçimi",
          "Kendi notunuzu ekleyin, tarih/saat belirleyin",
          "E-posta ile otomatik bildirim (WhatsApp & Telegram yakında)",
        ]}
      />
    );
  }

  // Kaynak seçenekleri için mevcut seçili değer
  const seciliKaynak =
    form.kaynak_tip !== "serbest" && form.kaynak_id
      ? `${form.kaynak_tip}::${form.kaynak_id}`
      : "serbest";

  const simdi = Date.now();
  const yaklasan = (liste ?? []).filter(
    (h) => h.status === "pending" && new Date(h.remind_at).getTime() >= simdi,
  );
  const gecmis = (liste ?? []).filter(
    (h) => !(h.status === "pending" && new Date(h.remind_at).getTime() >= simdi),
  );

  return (
    <div className="space-y-6">
      {dialog}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bell className="h-6 w-6 text-primary" /> Hatırlatıcılar
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Dava, dosya, notlarınız veya herhangi bir veriyle ilgili hatırlatıcı kurun. Zamanı gelince e-posta ile haber veririz.
        </p>
      </div>

      {/* Yapay Zeka ile hızlı oluşturma (yalnızca yeni kayıtta) */}
      {!editId && (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" /> Yapay Zeka ile hızlı oluştur
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!aiSonuc ? (
              /* — GİRİŞ EKRANI — */
              <>
                <p className="text-sm text-muted-foreground">
                  Hatırlatıcınızı kendi cümlelerinizle yazın; gerisini hallederiz. Örn:
                  &ldquo;Yarın 15.00&apos;te Ahmet&apos;in icra dosyası itiraz süresinin son gününü hatırlat.&rdquo;
                </p>
                <Textarea
                  rows={3}
                  placeholder="Hatırlatıcıyı serbestçe yazın…"
                  value={aiMetin}
                  onChange={(e) => setAiMetin(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) aiHazirla(); }}
                />
                <div className="flex justify-end">
                  <Button type="button" onClick={aiHazirla} disabled={aiYukleniyor || aiMetin.trim().length < 3}>
                    {aiYukleniyor ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Sparkles className="h-4 w-4 mr-1" />}
                    Yapay Zeka ile hazırla
                  </Button>
                </div>
              </>
            ) : aiAdim < aiSorular.length ? (
              /* — EKSİK ALAN SORUSU (adım adım) — */
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground italic">&ldquo;{aiMetin}&rdquo;</p>
                {/* İlerleme */}
                {aiSorular.length > 1 && (
                  <p className="text-xs text-muted-foreground">
                    Soru {aiAdim + 1} / {aiSorular.length}
                  </p>
                )}
                <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
                  <p className="text-sm flex items-start gap-2">
                    <Sparkles className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                    <span>{aiSorular[aiAdim].soru}</span>
                  </p>
                </div>
                {aiSorular[aiAdim].alan === "remind_at" ? (
                  <Input
                    type="datetime-local"
                    value={aiAdimCevap}
                    onChange={(e) => setAiAdimCevap(e.target.value)}
                    autoFocus
                  />
                ) : (
                  <Input
                    placeholder="Yanıtınızı yazın…"
                    value={aiAdimCevap}
                    onChange={(e) => setAiAdimCevap(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") aiAdimIlerle(); }}
                    autoFocus
                  />
                )}
                <div className="flex gap-2 justify-between">
                  <Button type="button" variant="ghost" size="sm" onClick={reset}>
                    <X className="h-4 w-4 mr-1" /> Vazgeç
                  </Button>
                  <Button
                    type="button"
                    onClick={aiAdimIlerle}
                    disabled={!aiAdimCevap.trim()}
                  >
                    {aiAdim < aiSorular.length - 1 ? "Devam →" : "Tamam →"}
                  </Button>
                </div>
              </div>
            ) : (
              /* — ONAY / ÖZET EKRANI — */
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground italic">&ldquo;{aiMetin}&rdquo;</p>
                {/* Başlık — düzenlenebilir */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Başlık</label>
                  <Input
                    value={form.baslik}
                    onChange={(e) => setForm((f) => ({ ...f, baslik: e.target.value }))}
                    placeholder="Hatırlatıcı başlığı…"
                  />
                </div>
                {/* Tarih & Saat — düzenlenebilir */}
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Tarih & Saat</label>
                  <Input
                    type="datetime-local"
                    value={form.remind_at}
                    onChange={(e) => setForm((f) => ({ ...f, remind_at: e.target.value }))}
                  />
                </div>
                {/* Not */}
                {form.not_metni && (
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Not</label>
                    <Textarea
                      rows={2}
                      value={form.not_metni}
                      onChange={(e) => setForm((f) => ({ ...f, not_metni: e.target.value }))}
                    />
                  </div>
                )}
                <div className="flex gap-2 justify-between pt-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => { setAiSonuc(false); setAiAdim(0); setAiSorular([]); }}
                  >
                    <X className="h-4 w-4 mr-1" /> Yeniden yaz
                  </Button>
                  <Button
                    type="button"
                    onClick={aiOlustur}
                    disabled={saving || !form.baslik.trim() || !form.remind_at}
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
                    Hatırlatıcıyı Oluştur
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Oluşturma / düzenleme formu */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {editId ? "Hatırlatıcıyı düzenle" : "Yeni hatırlatıcı"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={kaydet} className="space-y-3">
            <Input
              placeholder="Başlık (örn: 'İcra dosyası itiraz süresi son gün')"
              value={form.baslik}
              onChange={(e) => setForm({ ...form, baslik: e.target.value })}
            />
            {soru("baslik") && (
              <p className="text-xs text-primary flex items-center gap-1">
                <Sparkles className="h-3 w-3 shrink-0" /> {soru("baslik")}
              </p>
            )}

            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Tarih & saat</label>
                <Input
                  type="datetime-local"
                  value={form.remind_at}
                  onChange={(e) => setForm({ ...form, remind_at: e.target.value })}
                />
                {soru("remind_at") && (
                  <p className="text-xs text-primary flex items-center gap-1 mt-1">
                    <Sparkles className="h-3 w-3 shrink-0" /> {soru("remind_at")}
                  </p>
                )}
              </div>

              {!editId && (
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">İlgili kaynak (opsiyonel)</label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={seciliKaynak}
                    onChange={(e) => kaynakSec(e.target.value)}
                  >
                    <option value="serbest">Serbest (kaynak yok)</option>
                    {kaynaklar?.notlar?.length ? (
                      <optgroup label="Notlarım">
                        {kaynaklar.notlar.map((n) => (
                          <option key={n.id} value={`not::${n.id}`}>{n.baslik}</option>
                        ))}
                      </optgroup>
                    ) : null}
                    {kaynaklar?.uretimler?.length ? (
                      <optgroup label="AI Üretimlerim">
                        {kaynaklar.uretimler.map((u) => (
                          <option key={u.id} value={`uretim::${u.id}`}>{u.baslik}</option>
                        ))}
                      </optgroup>
                    ) : null}
                    {kaynaklar?.dosyalar?.length ? (
                      <optgroup label="Dosyalarım">
                        {kaynaklar.dosyalar.map((d) => (
                          <option key={d.id} value={`dosya::${d.id}`}>{d.baslik}</option>
                        ))}
                      </optgroup>
                    ) : null}
                  </select>
                </div>
              )}
            </div>

            <Textarea
              rows={3}
              placeholder="Notunuz (opsiyonel) — hatırlatıcı e-postasında gösterilir."
              value={form.not_metni}
              onChange={(e) => setForm({ ...form, not_metni: e.target.value })}
            />

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Bildirim kanalı</label>
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-md border bg-secondary px-3 py-1.5 text-sm">
                    E-posta
                  </span>
                  <span className="text-xs rounded-md border border-dashed px-2 py-1 text-muted-foreground" title="Yakında">
                    WhatsApp · yakında
                  </span>
                  <span className="text-xs rounded-md border border-dashed px-2 py-1 text-muted-foreground" title="Yakında">
                    Telegram · yakında
                  </span>
                </div>
              </div>
              <div className="flex gap-2">
                {editId && (
                  <Button type="button" variant="ghost" onClick={reset}>
                    <X className="h-4 w-4 mr-1" /> İptal
                  </Button>
                )}
                <Button type="submit" disabled={saving || !form.baslik.trim() || !form.remind_at}>
                  {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
                  {editId ? "Güncelle" : "Oluştur"}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          ⚠️ {error}
        </div>
      )}

      {loading && <ListSkeleton rows={3} />}

      {!loading && liste && liste.length === 0 && (
        <Card><CardContent className="p-8 text-center text-muted-foreground">
          <Bell className="h-10 w-10 mx-auto mb-3 opacity-30" />
          Henüz hatırlatıcınız yok. Yukarıdan ilk hatırlatıcınızı oluşturun.
        </CardContent></Card>
      )}

      {!loading && yaklasan.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">Yaklaşan</h2>
          <div className="space-y-2 stagger">
            {yaklasan.map((h) => (
              <HatirlaticiKart key={h.id} h={h} onDuzenle={duzenle} onSil={sil} />
            ))}
          </div>
        </div>
      )}

      {!loading && gecmis.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">Geçmiş</h2>
          <div className="space-y-2 opacity-80">
            {gecmis.map((h) => (
              <HatirlaticiKart key={h.id} h={h} onDuzenle={duzenle} onSil={sil} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HatirlaticiKart({
  h,
  onDuzenle,
  onSil,
}: {
  h: Hatirlatici;
  onDuzenle: (h: Hatirlatici) => void;
  onSil: (id: string) => void;
}) {
  const tarih = new Date(h.remind_at).toLocaleString("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
  return (
    <Card className="hover-lift">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="font-semibold truncate">{h.baslik}</div>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {tarih}</span>
              {durumRozeti(h)}
              {h.kaynak_tip && h.kaynak_tip !== "serbest" && (
                <span className="rounded-full bg-secondary px-2 py-0.5">{h.kaynak_tip}</span>
              )}
            </div>
            {h.not_metni && (
              <p className="text-sm text-foreground/80 mt-2 whitespace-pre-wrap">{h.not_metni}</p>
            )}
            {h.kaynak_ozet && (
              <p className="text-xs text-muted-foreground mt-1 border-l-2 border-border pl-2">{h.kaynak_ozet}</p>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={() => onDuzenle(h)} title="Düzenle" className="text-muted-foreground hover:text-foreground">
              <Pencil className="h-4 w-4" />
            </button>
            <button onClick={() => onSil(h.id)} title="Sil" className="text-muted-foreground hover:text-destructive">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
