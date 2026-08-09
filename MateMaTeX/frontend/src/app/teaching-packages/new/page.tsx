"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Check, Loader2, PackageOpen } from "lucide-react";
import {
  createTeachingPackage,
  getYearPlan,
  listTeachingPackages,
  type TeachingArtifactType,
  type TruthSource,
  type YearPlan,
} from "@/lib/platform-api";

const labels: Record<TeachingArtifactType, { title: string; description: string }> = {
  presentation: { title: "PowerPoint-presentasjon", description: "Redigerbare lysbilder med lærernotater og kilder." },
  student_sheet: { title: "Læringsark og elevtekst", description: "Sammenhengende elevtekst i PDF og Word." },
  exercise_sheet: { title: "Oppgaveark", description: "Elevoppgaver med kilde- og refleksjonsspørsmål." },
  answer_key: { title: "Fasit", description: "Veiledende svar og vurderingsnotat." },
  teacher_guide: { title: "Lærerveiledning", description: "Forslag til gjennomføring, differensiering og begrensninger." },
};

const allTypes: TeachingArtifactType[] = ["presentation", "student_sheet", "exercise_sheet", "answer_key", "teacher_guide"];

function NewTeachingPackageForm() {
  const search = useSearchParams();
  const router = useRouter();
  const planId = search.get("yearPlan") || "";
  const periodId = search.get("period") || "";
  const projectId = search.get("project") || undefined;
  const [plan, setPlan] = useState<YearPlan | null>(null);
  const [selected, setSelected] = useState<TeachingArtifactType[]>(allTypes);
  const [audience, setAudience] = useState("Elever");
  const [sourceBrief, setSourceBrief] = useState("");
  const [sourceUrls, setSourceUrls] = useState("");
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!planId || !periodId) {
      setError("Årsplan og periode mangler i lenken.");
      setLoading(false);
      return;
    }
    getYearPlan(planId)
      .then(setPlan)
      .catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste årsplanen."))
      .finally(() => setLoading(false));
  }, [periodId, planId]);

  const period = useMemo(() => plan?.periods.find((item) => item.id === periodId) || null, [periodId, plan]);

  async function start() {
    if (!plan || !period || selected.length === 0) return;
    setStarting(true);
    setError("");
    try {
      const existing = await listTeachingPackages({ yearPlanId: plan.id, periodId: period.id, limit: 1 });
      const packageValue = existing[0] || await createTeachingPackage({
        year_plan_id: plan.id,
        period_id: period.id,
        artifact_types: selected,
        audience,
        source_brief: sourceBrief,
        sources: sourceUrls
          .split(/\r?\n/)
          .map((url) => url.trim())
          .filter((url) => /^https?:\/\//i.test(url))
          .map((url): TruthSource => ({
            title: url,
            url,
            publisher: "",
            source_tier: "other",
            retrieved_at: new Date().toISOString(),
            origin: "teacher",
            fetch_status: "provided",
          })),
        project_id: projectId,
      });
      router.push(`/teaching-packages/${packageValue.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke opprette undervisningspakken.");
      setStarting(false);
    }
  }

  if (loading) return <div className="flex items-center gap-2 py-12 text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster perioden …</div>;
  if (!plan || !period) return <div role="alert" className="card text-accent-red">{error || "Perioden finnes ikke."}</div>;

  return (
    <main className="mx-auto max-w-4xl space-y-6">
      <button className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary" onClick={() => router.back()}>
        <ArrowLeft className="h-4 w-4" /> Tilbake til årsplanen
      </button>
      <header className="rounded-2xl border border-border bg-surface p-6 shadow-soft-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-accent-blue/10 p-3 text-accent-blue"><PackageOpen className="h-6 w-6" /></div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">{plan.subject} · {plan.level} · {plan.school_year}</p>
            <h1 className="mt-1 font-display text-3xl tracking-tight">Lag PowerPoint og undervisningspakke</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">PowerPoint, læringsark, oppgaveark, fasit og lærerveiledning er valgt som standard. Bekreft innholdet og start én varig pakkejobb.</p>
          </div>
        </div>
        <div className="mt-5 rounded-xl bg-accent-blue/5 p-4 text-sm">
          <strong>{period.title}</strong><span className="text-text-muted"> · {period.theme || plan.subject} · {period.lesson_count} timer</span>
          <p className="mt-2 text-text-secondary">{period.overview || "Ingen ekstra periodebeskrivelse er registrert."}</p>
        </div>
      </header>

      {error && <div role="alert" className="card text-sm text-accent-red">{error}</div>}

      <section className="card space-y-5">
        <div><h2 className="text-lg font-semibold">1. Velg innhold i pakken</h2><p className="mt-1 text-sm text-text-muted">PowerPoint og resten av undervisningspakken er forhåndsvalgt. Du kan fjerne deler du ikke trenger.</p></div>
        <div className="grid gap-3 md:grid-cols-2">
          {allTypes.map((type) => {
            const checked = selected.includes(type);
            return <button key={type} type="button" aria-pressed={checked} className={`rounded-xl border p-4 text-left transition ${checked ? "border-accent-blue bg-accent-blue/5" : "border-border bg-bg/40"}`} onClick={() => setSelected((current) => checked ? current.filter((item) => item !== type) : [...current, type])}>
              <div className="flex items-start gap-3"><span className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded border ${checked ? "border-accent-blue bg-accent-blue text-white" : "border-border"}`}>{checked && <Check className="h-3.5 w-3.5" />}</span><span><strong className="text-sm">{labels[type].title}</strong><span className="mt-1 block text-xs leading-relaxed text-text-muted">{labels[type].description}</span></span></div>
            </button>;
          })}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm font-medium">Målgruppe og nivå
            <input className="input mt-2" value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="VG2-elever" />
          </label>
          <label className="text-sm font-medium">Kildetekst eller avgrensning
            <textarea className="input mt-2 min-h-24 resize-y" value={sourceBrief} onChange={(event) => setSourceBrief(event.target.value)} placeholder="Hva skal pakken legge vekt på?" />
          </label>
        </div>
        <label className="block text-sm font-medium">Kilde-URL-er <span className="font-normal text-text-muted">(én per linje, konkrete sider)</span>
          <textarea className="input mt-2 min-h-24 resize-y" value={sourceUrls} onChange={(event) => setSourceUrls(event.target.value)} placeholder="https://snl.no/..." />
        </label>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
          <p className="text-xs text-text-muted">Pakken lagres på perioden og får en egen revisjonshistorikk.</p>
          <button className="btn-primary" onClick={() => void start()} disabled={starting || selected.length === 0}>
            {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageOpen className="h-4 w-4" />} Opprett PowerPoint-pakke
          </button>
        </div>
      </section>
    </main>
  );
}

export default function NewTeachingPackagePage() {
  return <Suspense fallback={<div className="py-12 text-text-muted">Laster pakkeoppsettet …</div>}><NewTeachingPackageForm /></Suspense>;
}
