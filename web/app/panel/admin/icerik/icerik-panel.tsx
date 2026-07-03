"use client";
import { useEffect, useState } from "react";
import {
  Plus,
  Sparkles,
  Eye,
  FileEdit,
  Trash2,
  ArrowLeft,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Faq = { soru: string; cevap: string };

type Makale = {
  id?: string;
  slug?: string;
  title: string;
  excerpt?: string | null;
  body?: string;
  meta_title?: string | null;
  meta_description?: string | null;
  keywords?: string[];
  faq?: Faq[];
  seo_score?: number;
  seo_notes?: string[];
  status?: string;
  author?: string | null;
  cover_image?: string | null;
  published_at?: string | null;
  updated_at?: string | null;
};

const BOS: Makale = {
  title: "",
  slug: "",
  excerpt: "",
  body: "",
  meta_title: "",
  meta_description: "",
  keywords: [],
  faq: [],
  cover_image: "",
};

function ScoreBadge({ score }: { score?: number }) {
  const s = score ?? 0;
  const color =
    s >= 80
      ? "bg-green-100 text-green-800 border-green-300"
      : s >= 50
      ? "bg-amber-100 text-amber-800 border-amber-300"
      : "bg-red-100 text-red-800 border-red-300";
  return (
    <span className={`text-xs rounded-full border px-2 py-0.5 ${color}`}>
      SEO {s}/100
    </span>
  );
}

export function IcerikPanel() {
  const [items, setItems] = useState<Makale[]>([]);
  const [view, setView] = useState<"list" | "edit">("list");
  const [current, setCurrent] = useState<Makale>(BOS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/icerik/admin/liste");
      const j = await r.json();
      if (r.ok) setItems(j.data || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function flash(ok: boolean, text: string) {
    setMsg({ ok, text });
    setTimeout(() => setMsg(null), 4000);
  }

  function yeni() {
    setCurrent(BOS);
    setView("edit");
    setMsg(null);
  }

  async function duzenle(id: string) {
    const r = await fetch(`/api/proxy/icerik/admin/makale/${id}`);
    const j = await r.json();
    if (r.ok) {
      setCurrent({ ...j.data, keywords: j.data.keywords || [], faq: j.data.faq || [] });
      setView("edit");
      setMsg(null);
    }
  }

  async function kaydet(): Promise<string | null> {
    if (!current.title.trim()) {
      flash(false, "Başlık zorunlu.");
      return null;
    }
    setSaving(true);
    try {
      const payload = {
        title: current.title,
        slug: current.slug || undefined,
        excerpt: current.excerpt,
        body: current.body,
        meta_title: current.meta_title,
        meta_description: current.meta_description,
        keywords: current.keywords,
        faq: current.faq,
        author: current.author,
        cover_image: current.cover_image || null,
      };
      const url = current.id
        ? `/api/proxy/icerik/admin/makale/${current.id}`
        : "/api/proxy/icerik/admin/makale";
      const method = current.id ? "PUT" : "POST";
      const r = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const j = await r.json();
      if (!r.ok) {
        flash(false, j.detail || j.error || "Kaydedilemedi.");
        return null;
      }
      setCurrent({ ...j.data, keywords: j.data.keywords || [], faq: j.data.faq || [] });
      flash(true, "Kaydedildi.");
      load();
      return j.data.id as string;
    } finally {
      setSaving(false);
    }
  }

  async function seoUret() {
    let id = current.id;
    if (!id) {
      id = (await kaydet()) || undefined;
      if (!id) return;
    }
    setSaving(true);
    try {
      const r = await fetch(`/api/proxy/icerik/admin/makale/${id}/seo`, {
        method: "POST",
      });
      const j = await r.json();
      if (!r.ok) {
        flash(false, j.detail || "SEO üretilemedi.");
        return;
      }
      setCurrent({ ...j.data, keywords: j.data.keywords || [], faq: j.data.faq || [] });
      flash(true, j.message || "SEO üretildi.");
      load();
    } finally {
      setSaving(false);
    }
  }

  async function durumDegistir(id: string, eylem: "yayinla" | "taslak") {
    const r = await fetch(`/api/proxy/icerik/admin/makale/${id}/${eylem}`, {
      method: "POST",
    });
    const j = await r.json();
    if (r.ok) {
      flash(true, j.message || "Güncellendi.");
      if (current.id === id) setCurrent({ ...current, status: j.data.status });
      load();
    } else {
      flash(false, j.detail || "İşlem başarısız.");
    }
  }

  async function sil(id: string) {
    if (!confirm("Bu makale kalıcı olarak silinsin mi?")) return;
    const r = await fetch(`/api/proxy/icerik/admin/makale/${id}`, {
      method: "DELETE",
    });
    if (r.ok) {
      flash(true, "Silindi.");
      if (current.id === id) {
        setView("list");
        setCurrent(BOS);
      }
      load();
    }
  }

  // -- FAQ editör yardımcıları --
  function faqEkle() {
    setCurrent({ ...current, faq: [...(current.faq || []), { soru: "", cevap: "" }] });
  }
  function faqGuncelle(i: number, alan: keyof Faq, val: string) {
    const faq = [...(current.faq || [])];
    faq[i] = { ...faq[i], [alan]: val };
    setCurrent({ ...current, faq });
  }
  function faqSil(i: number) {
    const faq = [...(current.faq || [])];
    faq.splice(i, 1);
    setCurrent({ ...current, faq });
  }

  // ====================== LİSTE GÖRÜNÜMÜ ======================
  if (view === "list") {
    return (
      <div className="space-y-4">
        {msg && (
          <div
            className={`rounded-md border p-3 text-sm flex items-center gap-2 ${
              msg.ok
                ? "bg-green-50 border-green-300 text-green-800"
                : "bg-red-50 border-red-300 text-red-800"
            }`}
          >
            {msg.ok ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            {msg.text}
          </div>
        )}

        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">İçerik / Blog Yönetimi</h2>
          <Button onClick={yeni} size="sm">
            <Plus className="h-4 w-4 mr-1.5" /> Yeni Makale
          </Button>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              Henüz makale yok. “Yeni Makale” ile başlayın.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {items.map((m) => (
              <Card key={m.id}>
                <CardContent className="p-4 flex flex-wrap items-center gap-3">
                  {m.cover_image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={m.cover_image}
                      alt=""
                      className="h-12 w-20 shrink-0 rounded-md border object-cover bg-muted"
                    />
                  ) : (
                    <div className="h-12 w-20 shrink-0 rounded-md border bg-gradient-to-br from-primary/15 to-accent/15" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium truncate">{m.title}</span>
                      <span
                        className={`text-xs rounded-full border px-2 py-0.5 ${
                          m.status === "published"
                            ? "bg-green-100 text-green-800 border-green-300"
                            : "bg-gray-100 text-gray-700 border-gray-300"
                        }`}
                      >
                        {m.status === "published" ? "Yayında" : "Taslak"}
                      </span>
                      <ScoreBadge score={m.seo_score} />
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5 truncate">
                      /blog/{m.slug}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {m.status === "published" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => durumDegistir(m.id!, "taslak")}
                      >
                        Taslağa al
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => durumDegistir(m.id!, "yayinla")}
                      >
                        Yayınla
                      </Button>
                    )}
                    {m.status === "published" && (
                      <a
                        href={`/blog/${m.slug}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md border hover:bg-muted"
                        title="Sitede gör"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => duzenle(m.id!)}
                    >
                      <FileEdit className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => sil(m.id!)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ====================== DÜZENLEME GÖRÜNÜMÜ ======================
  const inputCls =
    "w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40";
  return (
    <div className="space-y-4 max-w-4xl">
      {msg && (
        <div
          className={`rounded-md border p-3 text-sm flex items-center gap-2 ${
            msg.ok
              ? "bg-green-50 border-green-300 text-green-800"
              : "bg-red-50 border-red-300 text-red-800"
          }`}
        >
          {msg.ok ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          {msg.text}
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <Button variant="outline" size="sm" onClick={() => setView("list")}>
          <ArrowLeft className="h-4 w-4 mr-1.5" /> Liste
        </Button>
        <div className="flex items-center gap-2">
          {current.id && current.status === "published" && (
            <span className="text-xs text-green-700">● Yayında</span>
          )}
          <ScoreBadge score={current.seo_score} />
          <Button variant="outline" size="sm" onClick={seoUret} disabled={saving}>
            <Sparkles className="h-4 w-4 mr-1.5" /> SEO Üret
          </Button>
          <Button size="sm" onClick={kaydet} disabled={saving}>
            {saving ? "Kaydediliyor…" : "Kaydet"}
          </Button>
          {current.id &&
            (current.status === "published" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => durumDegistir(current.id!, "taslak")}
              >
                Taslağa al
              </Button>
            ) : (
              <Button size="sm" onClick={() => durumDegistir(current.id!, "yayinla")}>
                <Eye className="h-4 w-4 mr-1.5" /> Yayınla
              </Button>
            ))}
        </div>
      </div>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div>
            <label className="text-sm font-medium">Başlık</label>
            <input
              className={inputCls}
              value={current.title}
              onChange={(e) => setCurrent({ ...current, title: e.target.value })}
              placeholder="Örn. İcra Takibi Nasıl Başlatılır?"
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">Slug (URL)</label>
              <input
                className={inputCls}
                value={current.slug || ""}
                onChange={(e) => setCurrent({ ...current, slug: e.target.value })}
                placeholder="boş bırakılırsa başlıktan üretilir"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Yazar</label>
              <input
                className={inputCls}
                value={current.author || ""}
                onChange={(e) => setCurrent({ ...current, author: e.target.value })}
                placeholder="Hukukçu Yapay Zekası Editör Ekibi"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">Özet (liste kartı)</label>
            <input
              className={inputCls}
              value={current.excerpt || ""}
              onChange={(e) => setCurrent({ ...current, excerpt: e.target.value })}
            />
          </div>

          <div>
            <label className="text-sm font-medium">
              Kapak Görseli (URL){" "}
              <span className="text-xs text-muted-foreground">
                — liste kartında ve makale başında görünür, boş bırakılırsa
                otomatik bir marka görseli kullanılır
              </span>
            </label>
            <div className="flex gap-3 items-start mt-1">
              <input
                className={inputCls}
                value={current.cover_image || ""}
                onChange={(e) =>
                  setCurrent({ ...current, cover_image: e.target.value })
                }
                placeholder="/blog/covers/ornek.svg veya https://..."
              />
              {current.cover_image && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={current.cover_image}
                  alt="Kapak önizleme"
                  className="h-16 w-28 shrink-0 rounded-md border object-cover bg-muted"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.visibility = "hidden";
                  }}
                />
              )}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">
              Gövde (Markdown destekli)
            </label>
            <textarea
              className={`${inputCls} min-h-[260px] font-mono`}
              value={current.body || ""}
              onChange={(e) => setCurrent({ ...current, body: e.target.value })}
              placeholder="Makale içeriğini buraya yazın. Başlıklar için ## kullanın."
            />
          </div>
        </CardContent>
      </Card>

      {/* SEO bölümü */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">SEO Alanları</h3>
            <span className="text-xs text-muted-foreground">
              “SEO Üret” ile otomatik doldur, gerekirse elle düzenle
            </span>
          </div>

          <div>
            <label className="text-sm font-medium">
              Meta Başlık{" "}
              <span className="text-xs text-muted-foreground">
                ({(current.meta_title || "").length} / ideal 30-60)
              </span>
            </label>
            <input
              className={inputCls}
              value={current.meta_title || ""}
              onChange={(e) =>
                setCurrent({ ...current, meta_title: e.target.value })
              }
            />
          </div>

          <div>
            <label className="text-sm font-medium">
              Meta Açıklama{" "}
              <span className="text-xs text-muted-foreground">
                ({(current.meta_description || "").length} / ideal 120-160)
              </span>
            </label>
            <textarea
              className={`${inputCls} min-h-[70px]`}
              value={current.meta_description || ""}
              onChange={(e) =>
                setCurrent({ ...current, meta_description: e.target.value })
              }
            />
          </div>

          <div>
            <label className="text-sm font-medium">
              Anahtar Kelimeler (virgülle ayırın)
            </label>
            <input
              className={inputCls}
              value={(current.keywords || []).join(", ")}
              onChange={(e) =>
                setCurrent({
                  ...current,
                  keywords: e.target.value
                    .split(",")
                    .map((k) => k.trim())
                    .filter(Boolean),
                })
              }
            />
          </div>

          {/* FAQ editör */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium">
                SSS (FAQPage schema olarak yayınlanır)
              </label>
              <Button size="sm" variant="outline" onClick={faqEkle}>
                <Plus className="h-4 w-4 mr-1" /> Soru ekle
              </Button>
            </div>
            <div className="space-y-3">
              {(current.faq || []).map((f, i) => (
                <div key={i} className="rounded-md border p-3 space-y-2">
                  <div className="flex gap-2">
                    <input
                      className={inputCls}
                      value={f.soru}
                      onChange={(e) => faqGuncelle(i, "soru", e.target.value)}
                      placeholder="Soru"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => faqSil(i)}
                      className="text-red-600 shrink-0"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <textarea
                    className={`${inputCls} min-h-[60px]`}
                    value={f.cevap}
                    onChange={(e) => faqGuncelle(i, "cevap", e.target.value)}
                    placeholder="Cevap"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* SEO notları */}
          {current.seo_notes && current.seo_notes.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-900 mb-1">
                İyileştirme önerileri
              </p>
              <ul className="list-disc pl-5 text-sm text-amber-800 space-y-0.5">
                {current.seo_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
