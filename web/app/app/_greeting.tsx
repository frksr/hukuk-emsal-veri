"use client";
import { useEffect, useState } from "react";

const ALT_METINLER = [
  "Bugün hangi davadayız?",
  "Hadi bir emsal bulalım.",
  "Bir dilekçeyle başlayalım mı?",
  "Bugün işini kolaylaştıralım.",
  "Nereden devam edelim?",
];

function selam(saat: number): string {
  if (saat < 6) return "İyi geceler";
  if (saat < 12) return "Günaydın";
  if (saat < 18) return "İyi günler";
  return "İyi akşamlar";
}

/** Saate göre selamlama + günlük dönüşen alt metin. Kullanıcının yerel saati. */
export function Greeting({ name }: { name: string }) {
  const [s, setS] = useState<string | null>(null);
  const [alt, setAlt] = useState(ALT_METINLER[0]);

  useEffect(() => {
    const now = new Date();
    setS(selam(now.getHours()));
    // Güne göre sabit (aynı gün hep aynı metin) — rastgele titremesin.
    setAlt(ALT_METINLER[now.getDate() % ALT_METINLER.length]);
  }, []);

  return (
    <div className="animate-fade-in">
      <h1 className="text-3xl font-bold">
        {s ? `${s}, ` : "Merhaba, "}
        {name} <span className="inline-block">👋</span>
      </h1>
      <p className="text-muted-foreground mt-1">{alt}</p>
    </div>
  );
}
