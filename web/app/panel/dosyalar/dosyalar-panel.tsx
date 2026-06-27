"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  Upload, FileText, Loader2, Trash2, Search, Lock, AlertTriangle,
  FolderClosed, FileCheck, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { ListSkeleton } from "@/components/list-skeleton";

type Doc = {
  id: string;
  title: string;
  case_no: string | null;
  decision_no: string | null;
  court: string | null;
  doc_type: string;
  file_name: string;
  file_size: number;
  status: "uploaded" | "processing" | "ready" | "error";
  chunk_count: number;
  tags: string[] | null;
  document_date: string | null;
  created_at: string;
};

const DOC_TYPE_LABEL: Record<string, string> = {
  dilekce: "Dilekçe",
  karar: "Karar",
  sozlesme: "Sözleşme",
  ihtarname: "İhtarname",
  evrak: "Evrak",
};

const STATUS_LABEL: Record<string, { tr: string; color: string }> = {
  uploaded: { tr: "Yüklendi", color: "bg-blue-100 text-blue-900" },
  processing: { tr: "İşleniyor", color: "bg-amber-100 text-amber-900" },
  ready: { tr: "Hazır", color: "bg-emerald-100 text-emerald-900" },
  error: { tr: "Hata", color: "bg-red-100 text-red-900" },
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function DosyalarPanel() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [planError, setPlanError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadDocs() {
    setLoading(true); setError(null); setPlanError(null);
    try {
      const r = await fetch("/api/proxy/uyap/?limit=100");
      const j = await r.json();
      if (r.status === 402) {
        setPlanError(j.message || "UYAP eklentili plan gerekli.");
        setDocs([]); setTotal(0);
        return;
      }
      if (!r.ok) throw new Error(j.message || "Liste alınamadı");
      setDocs(j.data?.documents || []);
      setTotal(j.data?.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  useEffect(() => { loadDocs(); }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", file.name);
      const r = await fetch("/api/proxy/uyap/upload", { method: "POST", body: fd });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Yüklenemedi");
      await loadDocs();
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yükleme hatası");
    } finally { setUploading(false); }
  }

  async function handleDelete(doc: Doc) {
    if (!confirm(`"${doc.title}" silinsin mi? Bu işlem geri alınamaz.`)) return;
    try {
      const r = await fetch(`/api/proxy/uyap/${doc.id}`, { method: "DELETE" });
      if (!r.ok) throw new Error("Silinemedi");
      await loadDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Silme hatası");
    }
  }

  const filtered = docs.filter((d) =>
    !search ||
    d.title.toLowerCase().includes(search.toLowerCase()) ||
    (d.case_no || "").includes(search) ||
    (d.court || "").toLowerCase().includes(search.toLowerCase()),
  );

  if (planError) {
    return (
      <Card className="border-accent/40 bg-accent/5">
        <CardContent className="p-8 text-center">
          <Lock className="h-12 w-12 text-accent mx-auto mb-3" />
          <h2 className="text-xl font-semibold mb-2">UYAP Eklentisi Gerekli</h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">
            {planError}
          </p>
          <Button asChild>
            <Link href="/panel/ayarlar/abonelik">Planı Yükselt</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4 flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[200px] relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Başlık, esas no veya mahkeme..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="text-sm text-muted-foreground">
            <strong>{total}</strong> dosya · <strong>{docs.reduce((a, d) => a + d.chunk_count, 0)}</strong> chunk
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={handleUpload}
            className="hidden"
            disabled={uploading}
          />
          <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
            Dosya Yükle
          </Button>
        </CardContent>
      </Card>

      <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900 flex gap-2">
        <Lock className="h-4 w-4 flex-shrink-0 mt-0.5" />
        <div>
          Dosyalarınız <strong>AES-256 ile şifreli</strong> olarak Türkiye lokasyonunda saklanır.
          Her dosya size özel anahtarla şifrelidir, başka kullanıcılar veya biz okuyamayız.
          Yapay Zeka sorgusunda kişisel veriler (TC, IBAN, telefon) maskelenerek işlenir.
        </div>
      </div>

      {error && (
        <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive flex gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {loading ? (
        <ListSkeleton rows={3} />
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            <FolderClosed className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="mb-1">
              {docs.length === 0 ? "Henüz dosya yüklemediniz." : "Aramayla eşleşen dosya yok."}
            </p>
            {docs.length === 0 && (
              <p className="text-sm">İlk UYAP dosyanızı yükleyerek başlayın.</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2 stagger">
          {filtered.map((doc) => {
            const st = STATUS_LABEL[doc.status] || STATUS_LABEL.uploaded;
            return (
              <Card key={doc.id} className="hover-lift hover:border-primary/50">
                <CardContent className="p-4 flex items-start gap-3">
                  <div className="h-10 w-10 rounded bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <FileText className="h-5 w-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <Link href={`/app/dosya/${doc.id}`} className="font-semibold hover:text-primary transition-colors block truncate">
                      {doc.title}
                    </Link>
                    <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-muted-foreground">
                      <span className={`px-2 py-0.5 rounded ${st.color}`}>{st.tr}</span>
                      <span className="px-2 py-0.5 rounded bg-secondary text-secondary-foreground">
                        {DOC_TYPE_LABEL[doc.doc_type] || doc.doc_type}
                      </span>
                      {doc.case_no && <span>Esas: {doc.case_no}</span>}
                      {doc.decision_no && <span>Karar: {doc.decision_no}</span>}
                      {doc.court && <span className="truncate">{doc.court}</span>}
                      <span>{formatSize(doc.file_size)}</span>
                      {doc.chunk_count > 0 && (
                        <span className="text-primary">
                          <Sparkles className="h-3 w-3 inline" /> {doc.chunk_count} chunk
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button asChild size="sm" variant="ghost">
                      <Link href={`/app/dosya/${doc.id}`}>
                        <FileCheck className="h-4 w-4" />
                      </Link>
                    </Button>
                    <Button onClick={() => handleDelete(doc)} size="sm" variant="ghost">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
