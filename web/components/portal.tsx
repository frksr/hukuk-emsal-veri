"use client";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * İçeriği doğrudan <body>'ye taşır. Modallar için gerekli: transform/filter
 * uygulayan bir ata (ör. sayfa geçiş animasyonu), içindeki `position: fixed`
 * öğeyi kendi kutusuyla sınırlar → örtü tüm ekranı kaplamaz. Portal bunu aşar.
 */
export function Portal({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(children, document.body);
}
