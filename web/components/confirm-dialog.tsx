"use client";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

type Opts = {
  title?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
};

type State = (Opts & { open: boolean; message: string; resolve?: (v: boolean) => void });

/**
 * Native window.confirm yerine kendi tasarım onay modalımız.
 *
 * Kullanım:
 *   const { confirm, dialog } = useConfirm();
 *   ...
 *   if (!(await confirm("Bu not silinsin mi?", { danger: true }))) return;
 *   ...
 *   return (<>{dialog} ...</>);
 */
export function useConfirm() {
  const [state, setState] = useState<State>({ open: false, message: "" });

  const confirm = useCallback((message: string, opts: Opts = {}) => {
    return new Promise<boolean>((resolve) => {
      setState({ open: true, message, resolve, ...opts });
    });
  }, []);

  const kapat = useCallback((sonuc: boolean) => {
    setState((s) => {
      s.resolve?.(sonuc);
      return { ...s, open: false, resolve: undefined };
    });
  }, []);

  useEffect(() => {
    if (!state.open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") kapat(false);
      if (e.key === "Enter") kapat(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.open, kapat]);

  const dialog = state.open ? (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 animate-fade-in"
      onClick={() => kapat(false)}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md rounded-xl border bg-background p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <div className={`mt-0.5 rounded-full p-2 ${state.danger ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary"}`}>
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-semibold">{state.title ?? "Onay"}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{state.message}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={() => kapat(false)}>
            {state.cancelText ?? "İptal"}
          </Button>
          <Button
            variant={state.danger ? "destructive" : "default"}
            onClick={() => kapat(true)}
            autoFocus
          >
            {state.confirmText ?? "Onayla"}
          </Button>
        </div>
      </div>
    </div>
  ) : null;

  return { confirm, dialog };
}
