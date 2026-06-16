"use client";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";
type Toast = { id: number; msg: string; type: ToastType };

const ToastCtx = createContext<(msg: string, type?: ToastType) => void>(() => {});

/** Bağımlılıksız hafif toast. `const toast = useToast(); toast("Kaydedildi","success")`. */
export function useToast() {
  return useContext(ToastCtx);
}

const ICON = { success: CheckCircle2, error: XCircle, info: Info };
const RENK = {
  success: "border-emerald-400/40 text-emerald-700 dark:text-emerald-300",
  error: "border-destructive/40 text-destructive",
  info: "border-border text-foreground",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const kapat = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (msg: string, type: ToastType = "info") => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t, { id, msg, type }]);
      setTimeout(() => kapat(id), 3500);
    },
    [kapat],
  );

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2">
        {toasts.map((t) => {
          const Icon = ICON[t.type];
          return (
            <div
              key={t.id}
              role="status"
              className={`animate-toast-in flex items-start gap-2 rounded-lg border bg-card/95 p-3 text-sm shadow-lg backdrop-blur ${RENK[t.type]}`}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="flex-1 text-foreground">{t.msg}</span>
              <button
                onClick={() => kapat(t.id)}
                aria-label="Kapat"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}
