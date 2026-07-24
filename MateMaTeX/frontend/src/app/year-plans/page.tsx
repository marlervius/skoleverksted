"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  CalendarDays,
  CheckCircle2,
  Loader2,
  Plus,
  Sparkles,
} from "lucide-react";
import { listYearPlans, type YearPlan } from "@/lib/platform-api";

function progressFor(plan: YearPlan): number {
  if (!plan.periods.length) return 0;
  const score = plan.periods.reduce((total, period) => {
    if (period.status === "completed") return total + 1;
    if (period.status === "ready") return total + 0.75;
    if (period.status === "in_progress") return total + 0.4;
    return total;
  }, 0);
  return Math.round((score / plan.periods.length) * 100);
}

export default function YearPlansPage() {
  const [plans, setPlans] = useState<YearPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listYearPlans()
      .then(setPlans)
      .catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste årsplanene."))
      .finally(() => setLoading(false));
  }, []);

  const totals = useMemo(() => ({
    plans: plans.length,
    materials: plans.reduce(
      (sum, plan) => sum + plan.periods.reduce((periodSum, period) => periodSum + period.materials.length, 0),
      0,
    ),
    ready: plans.reduce(
      (sum, plan) => sum + plan.periods.filter((period) => period.status === "ready" || period.status === "completed").length,
      0,
    ),
  }), [plans]);

  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <header className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent-blue/20 bg-accent-blue/5 px-3 py-1 text-xs font-medium text-accent-blue">
            <Sparkles className="h-3.5 w-3.5" /> Fra plan til ferdige læremidler
          </div>
          <h1 className="font-display text-4xl tracking-tight">Årsplaner</h1>
          <p className="mt-2 max-w-2xl text-text-secondary">
            Planlegg hele faget, produser læremidler periode for periode og behold oversikten til neste skoleår.
          </p>
        </div>
        <Link href="/year-plans/new" className="btn-primary">
          <Plus className="h-4 w-4" /> Ny årsplan
        </Link>
      </header>

      {plans.length > 0 && (
        <section className="grid gap-3 sm:grid-cols-3" aria-label="Årsplanstatistikk">
          <div className="card flex items-center gap-3">
            <CalendarDays className="h-5 w-5 text-accent-blue" />
            <div><div className="text-2xl font-semibold">{totals.plans}</div><div className="text-xs text-text-muted">årsplaner</div></div>
          </div>
          <div className="card flex items-center gap-3">
            <BookOpenCheck className="h-5 w-5 text-accent-purple" />
            <div><div className="text-2xl font-semibold">{totals.materials}</div><div className="text-xs text-text-muted">lagrede læremidler</div></div>
          </div>
          <div className="card flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-accent-green" />
            <div><div className="text-2xl font-semibold">{totals.ready}</div><div className="text-xs text-text-muted">perioder klare</div></div>
          </div>
        </section>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-10 text-sm text-text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Laster årsplaner …
        </div>
      )}
      {error && <div role="alert" className="card border-accent-red/30 text-accent-red">{error}</div>}

      {!loading && !error && plans.length === 0 && (
        <section className="rounded-2xl border border-dashed border-border bg-surface p-10 text-center">
          <CalendarDays className="mx-auto h-9 w-9 text-accent-blue" />
          <h2 className="mt-4 text-xl font-semibold">Lag din første årsplan</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-text-secondary">
            Oppgi fag, nivå og timer per uke. Planleggeren foreslår temaer, progresjon, læringsmål,
            aktiviteter og vurdering som du kan redigere.
          </p>
          <Link href="/year-plans/new" className="btn-primary mt-6">
            <Sparkles className="h-4 w-4" /> Lag forslag
          </Link>
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-2">
        {plans.map((plan) => {
          const progress = progressFor(plan);
          const materials = plan.periods.reduce((sum, period) => sum + period.materials.length, 0);
          return (
            <Link key={plan.id} href={`/year-plans/${plan.id}`} className="card-interactive group block">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-text-muted">
                    {plan.subject} · {plan.level} · {plan.school_year}
                  </div>
                  <h2 className="mt-1.5 text-xl font-semibold">{plan.title}</h2>
                </div>
                <span className="badge bg-accent-blue/10 text-accent-blue">{progress}%</span>
              </div>
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-surface-elevated">
                <div className="h-full rounded-full bg-accent-blue transition-all" style={{ width: `${progress}%` }} />
              </div>
              <div className="mt-4 flex items-center justify-between text-sm text-text-secondary">
                <span>{plan.periods.length} perioder · {materials} læremidler</span>
                <span className="inline-flex items-center gap-1 font-medium text-text-primary">
                  Åpne <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </span>
              </div>
            </Link>
          );
        })}
      </section>
    </div>
  );
}
