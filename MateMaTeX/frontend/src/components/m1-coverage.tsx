"use client";

import { useEffect, useState } from "react";
import { fetchM1Report, type M1Report } from "@/lib/api";

export function M1CoverageCard({ compact = false }: { compact?: boolean }) {
  const [report, setReport] = useState<M1Report | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchM1Report()
      .then(setReport)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Kunne ikke laste M1-data")
      );
  }, []);

  if (error) {
    if (compact) return null;
    return (
      <section className="card mb-6 not-prose">
        <h2 className="text-lg font-semibold mb-2">M1 — empirisk fasitdekning</h2>
        <p className="text-sm text-text-secondary">{error}</p>
      </section>
    );
  }

  if (!report) {
    if (compact) return null;
    return (
      <section className="card mb-6 not-prose animate-pulse">
        <div className="h-4 bg-surface-elevated rounded w-1/3 mb-3" />
        <div className="h-3 bg-surface-elevated rounded w-full" />
      </section>
    );
  }

  if (compact) {
    const top = report.levels[0];
    if (!top) return null;
    return (
      <div className="rounded-lg border border-border bg-surface-elevated/40 px-4 py-3 mb-8 max-w-xl mx-auto text-center">
        <p className="text-xs text-text-secondary mb-1">
          {report.is_example ? "M1 (eksempeldata)" : "M1 empirisk dekning"}
        </p>
        <p className="text-sm">
          <span className="font-display text-xl text-accent-green tabular-nums">
            {top.green_pct}%
          </span>
          <span className="text-text-secondary ml-2">
            SymPy-dekning · {top.level}
          </span>
        </p>
        <a href="/personvern#m1" className="text-xs text-accent-blue hover:underline mt-1 inline-block">
          Se full rapport
        </a>
      </div>
    );
  }

  return (
    <section className="card mb-6 not-prose" id="m1">
      <h2 className="text-lg font-semibold mb-2">M1 — empirisk fasitdekning</h2>
      <p className="text-sm text-text-secondary mb-4">
        {report.is_example
          ? "Eksempeldata fra M1-protokollen (erstatt med egne Udir-resultater i m1_skjema.csv)."
          : "Målt dekning fra m1_skjema.csv — poengvektet SymPy-dekning på ekte oppgaver."}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {report.levels.map((lvl) => (
          <div
            key={lvl.level}
            className="rounded-lg border border-border bg-surface-elevated/40 p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">{lvl.level}</span>
              <span className="text-xs text-text-muted">{lvl.total_points} poeng</span>
            </div>
            <div className="text-2xl font-display text-accent-green tabular-nums">
              {lvl.green_pct}%
            </div>
            <p className="text-xs text-text-secondary mt-1">
              SymPy-verifisert nå · realistisk tak {lvl.realistic_ceiling_pct}%
            </p>
            <div className="mt-2 h-1.5 rounded-full bg-border overflow-hidden">
              <div
                className="h-full bg-accent-green"
                style={{ width: `${Math.min(100, lvl.green_pct)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      {report.topics.length > 0 && (
        <details className="mt-4 text-xs text-text-secondary">
          <summary className="cursor-pointer font-medium text-text-primary">
            Per emne
          </summary>
          <ul className="mt-2 space-y-1">
            {report.topics.map((t) => (
              <li key={`${t.level}-${t.topic}`}>
                {t.level} · {t.topic}: {t.green_pct}% ({t.total_points} p)
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
