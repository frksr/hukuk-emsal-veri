"use client";

import { useEffect, useState } from "react";
import { MessageSquarePlus, Lightbulb, AlertTriangle, Bug, MessageSquare, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type FeedbackType = "feature" | "complaint" | "bug" | "other";

type MyFeedback = {
  id: string;
  type: string;
  subject: string | null;
  message: string;
  status: string;
  created_at: string | null;
};

const TYPES: { value: FeedbackType; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: "feature", label: "Öneri", icon: Lightbulb },
  { value: "complaint", label: "Eksiklik", icon: AlertTriangle },
  { value: "bug", label: "Hata", icon: Bug },
  { value: "other", label: "Diğer", icon: MessageSquare },
];

const STATUS_TR: Record<string, { label: string; cls: string }> = {
  new: { label: "Alındı", cls: "bg-blue-100 text-blue-900 border-blue-300 dark:bg-blue-500/15 dark:text-blue-300 dark:border-blue-500/30" },
  reviewing: { label: "İnceleniyor", cls: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30" },
  in_progress: { label: "Üzerinde çalışılıyor", cls: "bg-violet-100 text-violet-900 border-violet-300 dark:bg-violet-500/15 dark:text-violet-300 dark:border-violet-500/30" },
  resolved: { label: "Çözüldü", cls: "bg-green-100 text-green-900 border-green-300 dark:bg-green-500/15 dark:text-green-300 dark:border-green-500/30" },
  wont_fix: { label: "Kapatıldı", cls: "bg-gray-100 text-gray-700 border-gray-300 dark:bg-gray-500/15 dark:text-gray-300 dark:border-gray-500/30" },
};

const TYPE_TR: Record<string, string> = {
  feature: "Öneri",
  complaint: "Eksiklik",
  bug: "Hata",
  question: "Soru",
  praise: "Teşekkür",
  other: "Diğer",
};

export default function OneriPage() {
  const [type, setType] = useState<FeedbackType>("feature");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [history, setHistory] = useState<MyFeedback[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [needsLogin, setNeedsLogin] = useState(false);

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const r = await fetch("/api/proxy/feedback/mine", { cache: "no-store" });
      if (r.status === 401 || r.status === 403) {
        setNeedsLogin(true);
        setHistory([]);
        return;
      }
      const j = await r.json();
      if (r.ok) {
        setHistory(j.data?.feedback || []);
        setNeedsLogin(false);
      }
    } catch {
      // sessizce geç — geçmiş kritik değil
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (message.trim().length < 5) {
      setError("Lütfen en az 5 karakterlik bir mesaj yazın.");
      return;
    }
    setSubmitting(true);
    try {
      const r = await fetch("/api/proxy/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedback_type: type,
          subject: subject.trim() || null,
          message: message.trim(),
          page_url: typeof window !== "undefined" ? window.location.href : null,
        }),
      });
      const j = await r.json();
      if (r.ok && j.ok) {
        setDone(true);
        setSubject("");
        setMessage("");
        setType("feature");
        loadHistory();
      } else {
        setError(j.message || "Gönderilemedi, lütfen tekrar deneyin.");
      }
    } catch {
      setError("Bağlantı hatası — lütfen tekrar deneyin.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <MessageSquarePlus className="h-6 w-6 text-primary" />
          Bize Yazın — Öneri &amp; İstek
        </h1>
        <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
          Şu özellik olsa derseniz, bir eksiklik fark ederseniz veya bir sorun yaşarsanız bize
          yazın; her mesajı okuyor ve ürünü ona göre geliştiriyoruz.
        </p>
      </div>

      <Card>
        <CardContent className="p-5">
          {done ? (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <CheckCircle2 className="h-10 w-10 text-green-500" />
              <div className="font-semibold">Teşekkürler! Mesajınız bize ulaştı.</div>
              <p className="text-sm text-muted-foreground">
                Her geri bildirimi titizlikle inceliyoruz.
              </p>
              <Button variant="outline" onClick={() => setDone(false)}>
                Yeni bir talep gönder
              </Button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium">Konu türü</label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {TYPES.map((t) => {
                    const active = type === t.value;
                    return (
                      <button
                        type="button"
                        key={t.value}
                        onClick={() => setType(t.value)}
                        className={`flex flex-col items-center gap-1 rounded-lg border px-3 py-3 text-sm transition-colors ${
                          active
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-input bg-background hover:bg-muted"
                        }`}
                      >
                        <t.icon className="h-5 w-5" />
                        {t.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Konu <span className="text-muted-foreground">(isteğe bağlı)</span>
                </label>
                <Input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Kısa bir başlık"
                  maxLength={200}
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium">Mesajınız</label>
                <Textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Aklınızdaki öneriyi, eksikliği veya sorunu olabildiğince açık şekilde anlatın…"
                  rows={6}
                  maxLength={4000}
                />
                <div className="mt-1 text-right text-xs text-muted-foreground">
                  {message.length}/4000
                </div>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Gönderiliyor…
                  </>
                ) : (
                  "Gönder"
                )}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Geçmiş talepleriniz</CardTitle>
          <CardDescription>Gönderdiğiniz talepler ve mevcut durumları.</CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          {historyLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : needsLogin ? (
            <p className="py-4 text-sm text-muted-foreground">
              Geçmiş taleplerinizi görmek için giriş yapmanız gerekir. Yine de form üzerinden
              mesaj gönderebilirsiniz.
            </p>
          ) : history.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">Henüz bir talep göndermediniz.</p>
          ) : (
            <ul className="divide-y">
              {history.map((f) => {
                const st = STATUS_TR[f.status] || {
                  label: f.status,
                  cls: "bg-muted text-muted-foreground border-border",
                };
                return (
                  <li key={f.id} className="flex flex-col gap-1 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-secondary px-2 py-0.5 text-xs">
                        {TYPE_TR[f.type] || f.type}
                      </span>
                      <span className={`rounded border px-2 py-0.5 text-xs ${st.cls}`}>
                        {st.label}
                      </span>
                      {f.created_at && (
                        <span className="text-xs text-muted-foreground">
                          {new Date(f.created_at).toLocaleDateString("tr-TR")}
                        </span>
                      )}
                    </div>
                    {f.subject && <div className="text-sm font-medium">{f.subject}</div>}
                    <p className="line-clamp-2 text-sm text-muted-foreground">{f.message}</p>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
