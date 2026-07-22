"use client";

import { Check, ChevronDown } from "lucide-react";

const STEPS = ["Grunnlag", "Kilde og media", "Tilpasning", "Kontroll"];

export function GenerationJourney({ current = 1 }: { current?: number }) {
  return (
    <nav aria-label="Steg i genereringen" className="mb-6 rounded-2xl border border-border bg-surface px-4 py-3">
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {STEPS.map((label, index) => {
          const number = index + 1;
          const complete = number < current;
          const active = number === current;
          return (
            <li key={label} className={`flex items-center gap-2 text-xs ${active ? "font-semibold text-text-primary" : "text-text-muted"}`} aria-current={active ? "step" : undefined}>
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${active || complete ? "border-accent-blue bg-accent-blue text-white" : "border-border bg-bg"}`}>
                {complete ? <Check size={13} aria-hidden /> : number}
              </span>
              <span>{label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function AdvancedOptions({
  title = "Flere valg",
  description,
  children,
  defaultOpen = false,
}: {
  title?: string;
  description?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details className="group rounded-2xl border border-border bg-surface-elevated" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue">
        <span>
          <span className="block text-sm font-semibold text-text-primary">{title}</span>
          {description && <span className="mt-0.5 block text-xs text-text-muted">{description}</span>}
        </span>
        <ChevronDown size={18} className="shrink-0 text-text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="border-t border-border p-4">{children}</div>
    </details>
  );
}

export function GenerationSummary({ items }: { items: Array<{ label: string; value?: string | null }> }) {
  const visible = items.filter((item) => item.value);
  if (!visible.length) return null;
  return (
    <aside aria-label="Oppsummering av valgene" className="rounded-2xl border border-border bg-bg p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">Oppsummering av valgene</p>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        {visible.map((item) => (
          <div key={item.label} className="min-w-0">
            <dt className="text-xs text-text-muted">{item.label}</dt>
            <dd className="truncate font-medium text-text-primary">{item.value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
