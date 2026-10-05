"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ReadabilityReport } from "../lib/fovTypes";
import { visibleReadabilityIssues } from "../lib/readability";

interface Props {
  report: ReadabilityReport;
}

/**
 * Advisory CEFR readability check for the running text. It never blocks the
 * preview or the download; it points the teacher at sentences worth editing.
 */
export function ReadabilityPanel({ report }: Props) {
  const ok = report.status === "ok";
  const { shown, hidden } = visibleReadabilityIssues(report);

  return (
    <section
      className={`rounded-xl border p-4 sm:p-5 ${
        ok ? "border-emerald-200 bg-emerald-50/60" : "border-amber-200 bg-amber-50/70"
      }`}
      aria-labelledby="readability-title"
    >
      <div className="flex items-start gap-3">
        {ok ? (
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" aria-hidden="true" />
        ) : (
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden="true" />
        )}
        <div className="min-w-0">
          <h3 id="readability-title" className="font-semibold text-stone-900">
            Språknivå-sjekk ({report.base_level})
          </h3>
          <p className="mt-1 text-sm text-stone-700">{report.summary}</p>
          {report.auto_simplified && (
            <p className="mt-1 text-xs text-stone-600">
              Lange setninger ble delt automatisk for at teksten skal passe nivået.
            </p>
          )}
        </div>
      </div>

      {shown.length > 0 && (
        <ul className="mt-3 space-y-2">
          {shown.map((issue, index) => (
            <li key={`${issue.code}-${index}`} className="rounded-lg border border-amber-200 bg-white p-3">
              <p className="text-sm text-stone-900">«{issue.sentence}»</p>
              <p className="mt-1 text-xs text-stone-700">{issue.message}</p>
            </li>
          ))}
        </ul>
      )}
      {hidden > 0 && <p className="mt-2 text-xs text-stone-600">… og {hidden} til.</p>}

      {!ok && (
        <p className="mt-3 text-xs text-stone-500">
          Dette er en veiledning for teksten slik den ble generert. Den hindrer ikke forhåndsvisning eller nedlasting.
        </p>
      )}
    </section>
  );
}
