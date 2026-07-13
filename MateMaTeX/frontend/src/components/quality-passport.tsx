import { AlertTriangle, CheckCircle2, CircleHelp, ShieldCheck, XCircle } from "lucide-react";
import type { QualityPassport as QualityPassportType } from "@/lib/platform-api";

const iconFor = {
  passed: CheckCircle2,
  warning: AlertTriangle,
  failed: XCircle,
  not_applicable: CircleHelp,
};

const colorFor = {
  passed: "text-accent-green",
  warning: "text-accent-orange",
  failed: "text-accent-red",
  not_applicable: "text-text-muted",
};

export function QualityPassport({ passport }: { passport: QualityPassportType }) {
  return (
    <section className="card" aria-labelledby="quality-passport-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-text-muted">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" /> Kvalitetspass v{passport.version}
          </div>
          <h2 id="quality-passport-title" className="text-lg font-semibold">{passport.title}</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Maskinelle kontroller er dokumentert. Faglig sluttansvar ligger fortsatt hos lærer.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-surface-elevated px-4 py-2 text-center">
          <div className="text-2xl font-semibold">{passport.score}</div>
          <div className="text-[10px] uppercase tracking-wide text-text-muted">av 100</div>
        </div>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {passport.checks.map((check) => {
          const Icon = iconFor[check.status];
          return (
            <div key={check.code} className="flex gap-3 rounded-lg border border-border bg-bg/40 p-3">
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${colorFor[check.status]}`} aria-hidden="true" />
              <div>
                <div className="text-sm font-medium">{check.label}</div>
                <div className="mt-0.5 text-xs leading-relaxed text-text-muted">{check.detail}</div>
              </div>
            </div>
          );
        })}
      </div>

      {passport.limitations.length > 0 && (
        <div className="mt-4 rounded-lg border border-accent-orange/25 bg-accent-orange/5 p-3">
          <div className="text-xs font-medium text-accent-orange">Må kontrolleres av lærer</div>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-text-secondary">
            {passport.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}
