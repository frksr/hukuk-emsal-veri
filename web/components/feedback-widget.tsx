"use client";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { MessageSquare, X, Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

const TYPES = [
  { value: "bug", label: "🐛 Hata bildir", severity: "high" },
  { value: "feature", label: "💡 Özellik öner", severity: "normal" },
  { value: "praise", label: "❤️ Memnunum", severity: "low" },
  { value: "complaint", label: "😞 Şikayetim var", severity: "normal" },
  { value: "question", label: "❓ Sorum var", severity: "normal" },
];

export function FeedbackWidget() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("feature");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  // /app/admin altında widget'i gösterme (admin zaten panelde görüyor)
  if (path?.startsWith("/panel/admin")) return null;

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim()) return;
    setSending(true);
    try {
      const t = TYPES.find((x) => x.value === type);
      await fetch("/api/proxy/feedback/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedback_type: type,
          severity: t?.severity || "normal",
          subject: subject || null,
          message,
          page_url: typeof window !== "undefined" ? window.location.href : null,
          contact_email: email || null,
          screen_resolution: typeof window !== "undefined" ? `${window.innerWidth}x${window.innerHeight}` : null,
        }),
      });
      setSent(true);
      setMessage(""); setSubject("");
      setTimeout(() => { setOpen(false); setSent(false); }, 2500);
    } finally { setSending(false); }
  }

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Geri bildirim"
          className="fixed bottom-5 right-5 z-40 h-12 w-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:scale-105 transition-transform flex items-center justify-center"
        >
          <MessageSquare className="h-5 w-5" />
        </button>
      )}

      {open && (
        <div className="fixed bottom-5 right-5 z-40 w-[380px] max-w-[calc(100vw-2rem)] rounded-lg border bg-background shadow-2xl">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="font-semibold">Geri Bildirim</h3>
            <button onClick={() => setOpen(false)} aria-label="Kapat" className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          {sent ? (
            <div className="p-8 text-center">
              <div className="text-4xl mb-2">✓</div>
              <p className="font-semibold">Teşekkürler!</p>
              <p className="text-sm text-muted-foreground mt-1">Geri bildiriminiz iletildi.</p>
            </div>
          ) : (
            <form onSubmit={send} className="p-4 space-y-3">
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full h-9 rounded-md border bg-background px-3 text-sm"
              >
                {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>

              <Input
                placeholder="Konu (opsiyonel)"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />

              <Textarea
                placeholder="Lütfen detay verin..."
                rows={4}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
              />

              <Input
                type="email"
                placeholder="E-posta (cevap için, opsiyonel)"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <Button type="submit" disabled={sending || !message.trim()} className="w-full">
                {sending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Gönder
              </Button>

              <p className="text-xs text-muted-foreground text-center">
                Sayfa URL'i ve ekran çözünürlüğü otomatik gönderilir.
              </p>
            </form>
          )}
        </div>
      )}
    </>
  );
}
