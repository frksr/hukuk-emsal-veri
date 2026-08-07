"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  Upload, FileText, Loader2, Trash2, Search, Lock, AlertTriangle,
  FolderClosed, FileCheck, Sparkles, CheckCircle2, XCircle, FileArchive, X,
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

// Tekli dosyalar 25 MB backend sınırına tabi (bkz. api/routers/uyap.py
// MAX_FILE_SIZE). ZIP arşivleri ayrı, daha yüksek bir sınıra tabi
// (MAX_BATCH_ARCHIVE_SIZE) çünkü içinde onlarca dosya olabilir.
const MAX_UPLOAD_MB = 25;
const MAX_ZIP_MB = 300;
const SINGLE_ALLOWED_EXT = ["pdf", "docx", "txt", "md", "udf"];

function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}

type QueueStatus = "queued" | "uploading" | "done" | "error";
type QueueItem = {
  id: string;
  name: string;
  size: number;
  status: QueueStatus;
  message?: string;
  subResults?: { filename: string; status: string; message?: string }[];
};

export function DosyalarPanel() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [planError, setPlanError] = useState<string | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [dragOver, setDragOver] = useState(false);
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

  function updateQueueItem(id: string, patch: Partial<QueueItem>) {
    setQueue((q) => q.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  }

  async function uploadOne(item: QueueItem, file: File) {
    updateQueueItem(item.id, { status: "uploading" });
    const isZip = extOf(file.name) === "zip";
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (!isZip) fd.append("title", file.name);
      const url = isZip ? "/api/proxy/uyap/upload/batch" : "/api/proxy/uyap/upload";
      const r = await fetch(url, { method: "POST", body: fd });
      const j = await r.json().catch(() => null);
      if (!r.ok) throw new Error(j?.message || "Yüklenemedi");

      if (isZip) {
        const summary = j?.data?.summary;
        const results = j?.data?.results || [];
        updateQueueItem(item.id, {
          status: "done",
          message: summary
            ? `${summary.success}/${summary.total} yüklendi` +
              (summary.failed ? `, ${summary.failed} hata` : "") +
              (summary.skipped ? `, ${summary.skipped} atlandı` : "")
            : undefined,
          subResults: results,
        });
      } else {
        updateQueueItem(item.id, { status: "done" });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Yükleme hatası";
      // Tarayıcı ağ hatası (ör. bağlantı koptu) genelde "Failed to fetch" döner —
      // kullanıcıya daha anlamlı bir mesaj göster.
      updateQueueItem(item.id, {
        status: "error",
        message: msg === "Failed to fetch"
          ? "Bağlantı koptu, tekrar deneyin."
          : msg,
      });
    }
  }

  // Çoklu dosya / sürükle-bırak: her dosya kuyruğa eklenir, sınırlı eşzamanlılıkla
  // (aynı anda 3 istek) yüklenir. .zip dosyaları /upload/batch'e, diğerleri
  // /upload'a gider. Backend sınırını aşan dosyalar sunucuya hiç gitmeden
  // burada "error" olarak işaretlenir (ERR_CONNECTION_RESET yerine net mesaj).
  async function handleFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (files.length === 0) return;
    setError(null);

    const runnable: { item: QueueItem; file: File }[] = [];
    const newItems: QueueItem[] = [];

    for (const file of files) {
      const ext = extOf(file.name);
      const isZip = ext === "zip";
      const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

      if (!isZip && !SINGLE_ALLOWED_EXT.includes(ext)) {
        const item: QueueItem = {
          id, name: file.name, size: file.size, status: "error",
          message: `Desteklenmeyen format (.${ext || "?"}).`,
        };
        newItems.push(item);
        continue;
      }
      const limitMb = isZip ? MAX_ZIP_MB : MAX_UPLOAD_MB;
      if (file.size > limitMb * 1024 * 1024) {
        const item: QueueItem = {
          id, name: file.name, size: file.size, status: "error",
          message: `Dosya ${limitMb} MB sınırını aşıyor (${(file.size / (1024 * 1024)).toFixed(1)} MB).`,
        };
        newItems.push(item);
        continue;
      }
      const item: QueueItem = { id, name: file.name, size: file.size, status: "queued" };
      newItems.push(item);
      runnable.push({ item, file });
    }

    setQueue((q) => [...newItems, ...q]);
    if (runnable.length === 0) return;

    setUploading(true);
    const CONCURRENCY = 3;
    let idx = 0;
    async function worker() {
      while (idx < runnable.length) {
        const cur = runnable[idx++];
        if (!cur) break;   // yarışta başka worker aldıysa
        await uploadOne(cur.item, cur.file);
      }
    }
    await Promise.all(
      Array.from({ length: Math.min(CONCURRENCY, runnable.length) }, worker),
    );
    setUploading(false);
    await loadDocs();
    if (fileRef.current) fileRef.current.value = "";
  }

  function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) handleFiles(e.target.files);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files);
  }
  function onDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(true);
  }
  function onDragLeave() {
    setDragOver(false);
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

  const activeQueue = queue.filter((q) => q.status === "queued" || q.status === "uploading");
  const settledCount = queue.length - activeQueue.length;

  return (
    <div className="space-y-4">
      <Card>
        <CardContent
          className={`p-4 flex flex-wrap gap-3 items-center rounded-lg transition-colors ${
            dragOver ? "bg-primary/5 ring-2 ring-primary/40 ring-inset" : ""
          }`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
        >
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
            <strong>{total}</strong> dosya
          </div>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.udf,.zip"
            onChange={handleUpload}
            className="hidden"
          />
          <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
            {uploading && activeQueue.length > 0
              ? `Yükleniyor (${settledCount}/${queue.length})`
              : "Dosya Yükle"}
          </Button>
          <p className="w-full text-xs text-muted-foreground">
            Birden fazla dosyayı buraya sürükleyip bırakabilir veya çok sayıda dosyanız
            varsa tek bir <strong>.zip</strong> olarak toplu yükleyebilirsiniz. UYAP&apos;ın
            kendi <strong>.udf</strong> formatı da desteklenir — önce PDF&apos;e çevirmenize gerek yok.
          </p>
        </CardContent>
      </Card>

      {queue.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Yükleme kuyruğu</span>
              {activeQueue.length === 0 && (
                <Button size="sm" variant="ghost" onClick={() => setQueue([])}>
                  <X className="h-3.5 w-3.5 mr-1" /> Temizle
                </Button>
              )}
            </div>
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {queue.map((it) => {
                const isZip = extOf(it.name) === "zip";
                return (
                  <div key={it.id} className="text-xs border rounded p-2">
                    <div className="flex items-center gap-2">
                      {it.status === "uploading" || it.status === "queued" ? (
                        <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-muted-foreground" />
                      ) : it.status === "done" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-emerald-600" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 flex-shrink-0 text-destructive" />
                      )}
                      {isZip ? (
                        <FileArchive className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                      ) : (
                        <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                      )}
                      <span className="truncate flex-1">{it.name}</span>
                      <span className="text-muted-foreground flex-shrink-0">{formatSize(it.size)}</span>
                    </div>
                    {it.message && (
                      <div className={`mt-1 pl-5 ${it.status === "error" ? "text-destructive" : "text-muted-foreground"}`}>
                        {it.message}
                      </div>
                    )}
                    {it.subResults && it.subResults.length > 0 && (
                      <div className="mt-1 pl-5 space-y-0.5">
                        {it.subResults.map((sr, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-muted-foreground">
                            {sr.status === "ready" ? (
                              <CheckCircle2 className="h-3 w-3 flex-shrink-0 text-emerald-600" />
                            ) : sr.status === "skipped" ? (
                              <AlertTriangle className="h-3 w-3 flex-shrink-0 text-amber-500" />
                            ) : (
                              <XCircle className="h-3 w-3 flex-shrink-0 text-destructive" />
                            )}
                            <span className="truncate">{sr.filename}</span>
                            {sr.message && <span className="truncate">— {sr.message}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900 flex gap-2">
        <Lock className="h-4 w-4 flex-shrink-0 mt-0.5" />
        <div>
          Dosyalarınız <strong>AES-256 ile şifreli</strong> olarak, KVKK m.9 kapsamında AB (Avrupa Birliği)
          sunucularında saklanır. Her dosya size özel anahtarla şifrelidir, başka kullanıcılar veya biz okuyamayız.
          Yapay Zeka sorgusunda kişisel veriler — <strong>TC kimlik no, IBAN, telefon, taraf/vekil isimleri,
          hakim ve heyet üyesi isimleri, belge no ve sicil no</strong> dahil — otomatik olarak maskelenir; bu
          bilgilerin gerçek hali yapay zekaya <strong>hiçbir zaman gönderilmez</strong>.
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
            const st = STATUS_LABEL[doc.status] ?? STATUS_LABEL.uploaded
              ?? { tr: doc.status, color: "bg-secondary text-secondary-foreground" };
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
                          <Sparkles className="h-3 w-3 inline" /> AI aramaya hazır
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
