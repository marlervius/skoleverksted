"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import type { TruthClaimStatus, TruthPassport as TruthPassportType } from "@/lib/platform-api";

const statusLabel = {
  verified: "Faktapasset er grønt",
  needs_review: "Må kontrolleres",
  blocked: "Kontrollen ble blokkert",
  verification_failed: "Faktakontrollen feilet",
  source_unavailable: "Kildegrunnlag utilgjengelig",
  not_evaluated: "Ikke evaluert",
};

const claimLabel: Record<TruthClaimStatus, string> = {
  verified: "Dokumentert",
  interpretation: "Tolkning",
  disputed: "Omstridt",
  time_sensitive: "Tidsavhengig",
  unsupported: "Ikke dokumentert",
  verification_failed: "Verifisering feilet",
  source_unavailable: "Kilde utilgjengelig",
  not_evaluated: "Ikke evaluert",
};

const claimIcon = {
  verified: CheckCircle2,
  interpretation: Scale,
  disputed: ShieldAlert,
  time_sensitive: Clock3,
  unsupported: AlertTriangle,
  verification_failed: AlertTriangle,
  source_unavailable: AlertTriangle,
  not_evaluated: AlertTriangle,
};

const sourceTierLabel = {
  primary: "primærkilde",
  authoritative: "faglig autoritet",
  editorial: "redaktørstyrt",
  other: "annen kilde",
};

const sourceOriginLabel = {
  teacher: "lærerens kilde",
  grounding: "Google-grounding",
  model: "modellrapportert",
};

const sourceFetchLabel = {
  provided: "oppgitt",
  grounded: "hentet via søk",
  model_reported: "ikke hentet av systemet",
  fetched: "hentet",
  source_unavailable: "ikke tilgjengelig",
};

function formatRetrievedAt(value: string) {
  try {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("nb-NO", { dateStyle: "medium" }).format(date);
  } catch {
    return "";
  }
}

export function TruthPassport({ passport }: { passport: TruthPassportType }) {
  const verified = passport.status === "verified";
  return (
    <section
      className={`rounded-xl border p-4 sm:p-5 ${
        verified
          ? "border-emerald-200 bg-emerald-50/60"
          : "border-amber-200 bg-amber-50/70"
      }`}
      aria-labelledby="truth-passport-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className={`flex items-center gap-2 text-xs font-semibold uppercase tracking-wide ${
            verified ? "text-emerald-800" : "text-amber-900"
          }`}>
            {verified
              ? <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              : <ShieldAlert className="h-4 w-4" aria-hidden="true" />}
            Faktapass v{passport.version}
          </div>
          <h3 id="truth-passport-title" className="mt-1 font-semibold text-stone-900">
            {statusLabel[passport.status]}
          </h3>
          <p className="mt-1 max-w-2xl text-sm text-stone-700">{passport.summary}</p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-center">
          <div className="rounded-lg border border-white/80 bg-white px-3 py-2">
            <div className="text-xl font-semibold text-stone-900">{passport.coverage_percent}%</div>
            <div className="text-[10px] uppercase tracking-wide text-stone-500">kildedekning</div>
          </div>
          <div className="rounded-lg border border-white/80 bg-white px-3 py-2">
            <div className="text-xl font-semibold text-stone-900">
              {passport.verified_claims}/{passport.total_claims}
            </div>
            <div className="text-[10px] uppercase tracking-wide text-stone-500">dokumentert</div>
          </div>
        </div>
      </div>

      {passport.limitations.length > 0 && (
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-amber-900">
          {passport.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
        </ul>
      )}

      <details className="mt-4 rounded-lg border border-stone-200 bg-white">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-stone-800">
          Se påstander og kilder
        </summary>
        <div className="space-y-5 border-t border-stone-200 p-4">
          <div className="space-y-2">
            {passport.claims.map((claim) => {
              const Icon = claimIcon[claim.status];
              return (
                <div key={claim.id} className="rounded-lg border border-stone-200 p-3">
                  <div className="flex items-start gap-2">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-stone-600" aria-hidden="true" />
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                        {claimLabel[claim.status]}
                      </div>
                      <p className="mt-1 text-sm text-stone-800">{claim.claim}</p>
                      {claim.evidence && (
                        <p className="mt-1 text-xs text-stone-600">{claim.evidence}</p>
                      )}
                      {claim.exact_text && claim.exact_text !== claim.claim && (
                        <details className="mt-2 text-xs text-stone-600">
                          <summary className="cursor-pointer font-medium">Se nøyaktig tekstutdrag</summary>
                          <blockquote className="mt-1 border-l-2 border-stone-300 pl-2 italic">{claim.exact_text}</blockquote>
                        </details>
                      )}
                      {claim.action === "qualify" && claim.replacement && (
                        <p className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">
                          <span className="font-semibold">Foreslått presisering:</span> {claim.replacement}
                        </p>
                      )}
                      {claim.source_urls.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {claim.source_urls.map((url) => {
                            const source = passport.sources.find((item) => item.url === url);
                            return (
                              <a
                                key={url}
                                href={url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-xs font-medium text-stone-700 underline"
                              >
                                {source?.title || "Åpne dokumentasjon"}
                                <ExternalLink className="h-3 w-3" aria-hidden="true" />
                              </a>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {passport.removed_claims.length > 0 && (
            <div>
              <h4 className="flex items-center gap-2 text-sm font-semibold text-stone-800">
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                Fjernet fordi det ikke kunne dokumenteres
              </h4>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-stone-600">
                {passport.removed_claims.map((claim) => <li key={claim}>{claim}</li>)}
              </ul>
            </div>
          )}

          <div>
            <h4 className="text-sm font-semibold text-stone-800">Registrerte kilder</h4>
            <ul className="mt-2 space-y-2">
              {passport.sources.map((source) => (
                <li key={source.url} className="text-xs text-stone-600">
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-medium text-stone-800 underline"
                  >
                    {source.title}
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </a>
                  <span>
                    {source.publisher && ` · ${source.publisher}`}
                    {` · ${sourceTierLabel[source.source_tier]}`}
                    {` · ${sourceOriginLabel[source.origin]}`}
                    {` · ${sourceFetchLabel[source.fetch_status]}`}
                    {formatRetrievedAt(source.retrieved_at) && ` · hentet ${formatRetrievedAt(source.retrieved_at)}`}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </details>
    </section>
  );
}
