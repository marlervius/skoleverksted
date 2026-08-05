"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookCopy,
  CheckCircle2,
  FileStack,
  LibraryBig,
  Loader2,
  Plus,
  Sparkles,
} from "lucide-react";
import { listCompendia, type Compendium, type CompendiumChapterStatus, type CompendiumStatus } from "@/lib/platform-api";

const statusLabels: Record<CompendiumStatus, string> = {
  outline: "Disposisjon",
  writing: "Under produksjon",
  review: "Til lærerkontroll",
  approved: "Godkjent",
  archived: "Arkivert",
};

const failedChapterStatuses: CompendiumChapterStatus[] = [
  "needs_revision",
  "generation_incomplete",
  "parse_failure",
  "language_quality_failed",
  "source_grounding_failed",
  "verification_failed",
];

function progress(compendium: Compendium): number {
  if (!compendium.chapters.length) return 0;
  const completed = compendium.chapters.reduce((sum, chapter) => {
    if (chapter.status === "approved") return sum + 1;
    if (chapter.status === "generated") return sum + 0.7;
    if (failedChapterStatuses.includes(chapter.status)) return sum + 0.2;
    return sum;
  }, 0);
  return Math.round((completed / compendium.chapters.length) * 100);
}

export default function CompendiaPage() {
  const [items, setItems] = useState<Compendium[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listCompendia()
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste kompendiene."))
      .finally(() => setLoading(false));
  }, []);

  const totals = useMemo(() => ({
    chapters: items.reduce((sum, item) => sum + item.chapters.length, 0),
    approved: items.filter((item) => item.status === "approved").length,
    files: items.filter((item) => item.artifact_version > 0).length,
  }), [items]);

  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <header className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent-teal/20 bg-accent-teal/10 px-3 py-1 text-xs font-medium text-accent-teal">
            <Sparkles className="h-3.5 w-3.5" /> Fra disposisjon til fagbibliotek
          </div>
          <h1 className="font-display text-4xl tracking-tight">Kompendier</h1>
          <p className="mt-2 max-w-2xl text-text-secondary">
            Lag fordypningslitteratur, oppslagsverk, kildesamlinger og appendiks med kontrollert omfang og dokumenterte kilder.
          </p>
        </div>
        <Link href="/compendia/new" className="btn-primary">
          <Plus className="h-4 w-4" /> Nytt kompendium
        </Link>
      </header>

      {items.length > 0 && (
        <section className="grid gap-3 sm:grid-cols-3" aria-label="Bibliotekstatistikk">
          <div className="card flex items-center gap-3"><LibraryBig className="h-5 w-5 text-accent-teal" /><div><div className="text-2xl font-semibold">{items.length}</div><div className="text-xs text-text-muted">kompendier</div></div></div>
          <div className="card flex items-center gap-3"><BookCopy className="h-5 w-5 text-accent-purple" /><div><div className="text-2xl font-semibold">{totals.chapters}</div><div className="text-xs text-text-muted">kapitler</div></div></div>
          <div className="card flex items-center gap-3"><CheckCircle2 className="h-5 w-5 text-accent-green" /><div><div className="text-2xl font-semibold">{totals.approved}/{totals.files}</div><div className="text-xs text-text-muted">godkjent / bygget</div></div></div>
        </section>
      )}

      {loading && <div className="flex items-center gap-2 py-10 text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster fagbiblioteket …</div>}
      {error && <div role="alert" className="card border-accent-red/30 text-accent-red">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <section className="rounded-2xl border border-dashed border-border bg-surface p-10 text-center">
          <FileStack className="mx-auto h-10 w-10 text-accent-teal" />
          <h2 className="mt-4 text-xl font-semibold">Bygg ditt første fagkompendium</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
            Du godkjenner først avgrensning og innholdsfortegnelse. Deretter produseres og kontrolleres ett kapittel om gangen.
          </p>
          <Link href="/compendia/new" className="btn-primary mt-6"><Sparkles className="h-4 w-4" /> Lag disposisjon</Link>
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-2">
        {items.map((item) => {
          const itemProgress = progress(item);
          const sourceCount = new Set(item.chapters.flatMap((chapter) => chapter.sources.map((source) => source.url || source.title))).size;
          return (
            <Link key={item.id} href={`/compendia/${item.id}`} className="card-interactive group block">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-text-muted">{item.subject} · {item.level}</div>
                  <h2 className="mt-1.5 text-xl font-semibold">{item.title}</h2>
                  <p className="mt-2 line-clamp-2 text-sm text-text-secondary">{item.purpose || item.topic}</p>
                </div>
                <span className="badge shrink-0 bg-accent-teal/10 text-accent-teal">{statusLabels[item.status]}</span>
              </div>
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-surface-elevated"><div className="h-full rounded-full bg-accent-teal" style={{ width: `${itemProgress}%` }} /></div>
              <div className="mt-4 flex items-center justify-between text-sm text-text-secondary">
                <span>{item.chapters.length} kapitler · {sourceCount} kilder · v{item.artifact_version}</span>
                <span className="inline-flex items-center gap-1 font-medium text-text-primary">Åpne <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></span>
              </div>
            </Link>
          );
        })}
      </section>
    </div>
  );
}
