"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[app/error]", error);
  }, [error]);

  return (
    <div className="container-main flex flex-col items-center justify-center py-24 text-center">
      <h1>Bir hata oluştu</h1>
      <p className="mt-4 max-w-prose text-muted-foreground">
        İsteğinizi işlerken beklenmedik bir sorunla karşılaştık. Lütfen tekrar
        deneyin.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-8 inline-flex h-10 items-center justify-center rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground transition hover:bg-primary-600"
      >
        Tekrar dene
      </button>
    </div>
  );
}
