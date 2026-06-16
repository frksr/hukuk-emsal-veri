"use client";

import { useState } from "react";
import { Check, Code, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

/**
 * "Bu aracı sitenize ekleyin" bölümü — hukuk bürosu siteleri için iframe kodu.
 * Doğal backlink + marka bilinirliği kanalı.
 */
export function EmbedKodu({ path = "/embed/faiz", baslik = "Faiz Hesaplayıcı" }: {
  path?: string;
  baslik?: string;
}) {
  const [copied, setCopied] = useState(false);

  const kod = `<iframe src="${SITE_URL}${path}" width="100%" height="640" style="border:1px solid #e2e8f0;border-radius:8px;" title="${baslik} — hukukcuyapayzekasi.com" loading="lazy"></iframe>`;

  function copy() {
    navigator.clipboard.writeText(kod);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Card className="mt-10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Code className="h-4 w-4" /> Bu aracı sitenize ekleyin
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-3">
          {baslik}&apos;yı kendi web sitenizde ücretsiz kullanabilirsiniz —
          aşağıdaki kodu sayfanıza yapıştırmanız yeterli. Oranlar otomatik güncel kalır.
        </p>
        <div className="relative">
          <pre className="text-xs bg-muted rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-all">
            {kod}
          </pre>
          <Button
            onClick={copy}
            size="sm"
            variant="outline"
            className="absolute top-2 right-2"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            <span className="ml-1.5">{copied ? "Kopyalandı" : "Kopyala"}</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
