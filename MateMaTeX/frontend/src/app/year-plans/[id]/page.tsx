"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  BookOpenCheck,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Download,
  FileText,
  Layers3,
  Loader2,
  NotebookPen,
  PackageOpen,
  Pencil,
  Presentation,
  RefreshCw,
  Save,
  Sparkles,
  X,
} from "lucide-react";
import {
  approveYearPlan,
  getYearPlan,
  updateYearPlan,
  updateYearPlanMaterial,
  updateYearPlanPeriod,
  verifyYearPlan,
  yearPlanMaterialDownloadUrl,
  type MaterialKind,
  type MaterialStatus,
  type YearPlan,
  type YearPlanMaterial,
  type YearPlanPeriod,
  type YearPlanPeriodStatus,
} from "@/lib/platform-api";
import { isMathematicsSubject, mathematicsGenerationHref } from "@/lib/mathematics-year-plan";
import { TruthPassport } from "@/components/truth-passport";

const periodLabels: Record<YearPlanPeriodStatus, string> = {
  not_started: "Ikke startet",
  in_progress: "Under arbeid",
  ready: "Klar",
  completed: "Gjennomført",
  needs_revision: "Må revideres",
};

const materialLabels: Record<MaterialKind, string> = {
  learning_sheet: "Læringsark",
  student_sheet: "Læringsark og elevtekst",
  worksheet: "Oppgaveark",
  exercise_sheet: "Oppgaveark",
  answer_key: "Fasit",
  teacher_guide: "Lærerveiledning",
  lesson_sequence: "Undervisningssekvens",
  assessment: "Vurdering/prøve",
  presentation: "Presentasjon",
  source_task: "Kildeoppgave",
  differentiated: "Differensiert",
  compendium: "Kompendium",
  other: "Annet",
};

const requiredKinds: MaterialKind[] = ["learning_sheet", "worksheet", "assessment"];

function weekLabel(value: string): string {
  const match = value.match(/(\d{4})-W(\d{2})/);
  return match ? `uke ${Number(match[2])}` : value;
}

function weekRange(period: YearPlanPeriod): string {
  if (!period.week_start) return `${period.duration_weeks} uker`;
  const first = weekLabel(period.week_start);
  const last = weekLabel(period.week_end);
  return first === last ? first : `${first}–${last.replace("uke ", "")}`;
}

function progress(plan: YearPlan): number {
  if (!plan.periods.length) return 0;
  const points = plan.periods.reduce((sum, period) => {
    if (period.status === "completed") return sum + 1;
    if (period.status === "ready") return sum + 0.75;
    if (period.status === "in_progress") return sum + 0.4;
    return sum;
  }, 0);
  return Math.round((points / plan.periods.length) * 100);
}

function generationHref(
  plan: YearPlan,
  period: YearPlanPeriod,
  mode: "laeringsark" | "prove" | "sekvens",
  kind: MaterialKind,
): string {
  if (isMathematicsSubject(plan.subject)) {
    return mathematicsGenerationHref(plan, period, kind);
  }
  const query = new URLSearchParams({
    topic: period.theme || period.title,
    subject: plan.subject,
    level: plan.level,
    mode,
    yearPlan: plan.id,
    period: period.id,
    materialType: kind,
    description: [
      period.overview,
      period.learning_goals.length ? `Læringsmål: ${period.learning_goals.join("; ")}` : "",
      period.key_concepts.length ? `Sentrale begreper: ${period.key_concepts.join(", ")}` : "",
    ].filter(Boolean).join("\n"),
  });
  return `/fag?${query}`;
}

function MaterialRow({
  plan,
  period,
  material,
  onUpdated,
}: {
  plan: YearPlan;
  period: YearPlanPeriod;
  material: YearPlanMaterial;
  onUpdated: (plan: YearPlan) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [rowError, setRowError] = useState("");
  async function changeStatus(status: MaterialStatus) {
    setSaving(true);
    setRowError("");
    try {
      const result = await updateYearPlanMaterial(plan.id, period.id, material.id, { status });
      onUpdated(result.plan);
    } catch (err) {
      setRowError(err instanceof Error ? err.message : "Kunne ikke oppdatere status.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2.5">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{material.title}</div>
        <div className="mt-0.5 text-xs text-text-muted">
          {materialLabels[material.kind]} · versjon {material.version} · {Math.max(1, Math.round(material.size_bytes / 1024))} kB
        </div>
        {material.source_kind === "teaching_package" && (
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-accent-purple">
            <span className="badge bg-accent-purple/10 text-accent-purple">Fra undervisningspakke</span>
            {material.teaching_package_id && <Link href={`/teaching-packages/${material.teaching_package_id}`} className="underline">Åpne pakken</Link>}
          </div>
        )}
        {rowError && <div className="mt-1 text-xs text-accent-red">{rowError}</div>}
      </div>
      <div className="flex items-center gap-2">
        <select
          aria-label={`Status for ${material.title}`}
          className="rounded-lg border border-border bg-bg px-2 py-1.5 text-xs"
          value={material.status}
          disabled={saving || material.source_kind === "teaching_package"}
          onChange={(event) => void changeStatus(event.target.value as MaterialStatus)}
        >
          <option value="draft">Utkast</option>
          <option value="approved">Godkjent</option>
          <option value="used">Brukt</option>
          <option value="needs_revision">Må revideres</option>
        </select>
        <a
          href={yearPlanMaterialDownloadUrl(plan.id, material.id)}
          className="btn-ghost !px-2.5 !py-1.5"
          title="Last ned"
        >
          <Download className="h-4 w-4" />
        </a>
      </div>
    </div>
  );
}

export default function YearPlanPage({ params }: { params: { id: string } }) {
  const [plan, setPlan] = useState<YearPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState("");
  const [expanded, setExpanded] = useState("");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [periodDraft, setPeriodDraft] = useState<YearPlanPeriod | null>(null);

  useEffect(() => {
    getYearPlan(params.id)
      .then((loaded) => {
        setPlan(loaded);
        setExpanded(loaded.periods[0]?.id ?? "");
        setNotes(Object.fromEntries(loaded.periods.map((period) => [period.id, period.teacher_notes])));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste årsplanen."))
      .finally(() => setLoading(false));
  }, [params.id]);

  const stats = useMemo(() => {
    if (!plan) return { materials: 0, approved: 0, coveredGoals: 0 };
    const materials = plan.periods.flatMap((period) => period.materials);
    const covered = new Set(plan.periods.flatMap((period) => period.competency_goals));
    return {
      materials: materials.length,
      approved: materials.filter((material) => material.status === "approved" || material.status === "used").length,
      coveredGoals: plan.competency_goals.filter((goal) => covered.has(goal)).length,
    };
  }, [plan]);

  async function changePeriodStatus(period: YearPlanPeriod, status: YearPlanPeriodStatus) {
    if (!plan) return;
    setSavingId(period.id);
    setError("");
    try {
      setPlan(await updateYearPlanPeriod(plan.id, period.id, { status }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke oppdatere perioden.");
    } finally {
      setSavingId("");
    }
  }

  async function saveNotes(period: YearPlanPeriod) {
    if (!plan) return;
    setSavingId(period.id);
    try {
      setPlan(await updateYearPlanPeriod(plan.id, period.id, { teacher_notes: notes[period.id] ?? "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke lagre notatet.");
    } finally {
      setSavingId("");
    }
  }

  async function savePeriodDraft() {
    if (!plan || !periodDraft) return;
    setSavingId(periodDraft.id);
    setError("");
    try {
      const updated = await updateYearPlanPeriod(plan.id, periodDraft.id, {
        title: periodDraft.title,
        theme: periodDraft.theme,
        overview: periodDraft.overview,
        learning_goals: periodDraft.learning_goals,
        competency_goals: periodDraft.competency_goals,
        key_concepts: periodDraft.key_concepts,
        suggested_activities: periodDraft.suggested_activities,
        assessment: periodDraft.assessment,
      });
      setPlan(updated);
      setPeriodDraft(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke lagre periodeendringene.");
    } finally {
      setSavingId("");
    }
  }

  async function activatePlan() {
    if (!plan) return;
    setSavingId("plan");
    try {
      if (plan.status === "active") {
        setPlan(await updateYearPlan(plan.id, { status: "draft" }));
      } else {
        const passportIsCurrent = Boolean(
          plan.truth_passport?.status === "verified"
          && plan.truth_passport.version === "2.0"
          && plan.content_revision
          && plan.truth_passport.content_revision === plan.content_revision,
        );
        const verified = passportIsCurrent ? plan : await verifyYearPlan(plan.id);
        const approved = await approveYearPlan(verified.id);
        setPlan(await updateYearPlan(approved.id, { status: "active" }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke oppdatere årsplanen.");
    } finally {
      setSavingId("");
    }
  }

  if (loading) return <div className="flex items-center gap-2 py-12 text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster årsplan …</div>;
  if (!plan) return <div role="alert" className="card text-accent-red">{error || "Årsplanen finnes ikke."}</div>;

  const planProgress = progress(plan);
  const mathematicsPlan = isMathematicsSubject(plan.subject);
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <Link href="/year-plans" className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary">
        <ArrowLeft className="h-4 w-4" /> Alle årsplaner
      </Link>

      <header className="rounded-2xl border border-border bg-surface p-5 shadow-soft-sm sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-text-muted">
              {plan.subject} · {plan.level} · {plan.school_year}
            </div>
            <h1 className="mt-2 font-display text-3xl tracking-tight sm:text-4xl">{plan.title}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-text-secondary">{plan.notes}</p>
          </div>
          <button className={plan.status === "active" ? "btn-secondary" : "btn-primary"} onClick={() => void activatePlan()} disabled={savingId === "plan"}>
            {savingId === "plan" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {plan.status === "active" ? "Sett som utkast" : "Ta planen i bruk"}
          </button>
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center">
          <div>
            <div className="mb-2 flex justify-between text-xs text-text-muted"><span>Årsprogresjon</span><span>{planProgress}%</span></div>
            <div className="h-2.5 overflow-hidden rounded-full bg-surface-elevated">
              <div className="h-full rounded-full bg-accent-blue" style={{ width: `${planProgress}%` }} />
            </div>
          </div>
          <div className="text-sm"><strong>{plan.lessons_per_week}</strong> <span className="text-text-muted">t/uke</span></div>
          <div className="text-sm"><strong>{plan.teaching_weeks * plan.lessons_per_week}</strong> <span className="text-text-muted">timer</span></div>
          <div className="text-sm"><strong>{stats.approved}/{stats.materials}</strong> <span className="text-text-muted">godkjent</span></div>
        </div>
      </header>

      {plan.truth_passport ? (
        <TruthPassport passport={plan.truth_passport} />
      ) : (
        <div className="card border-accent-orange/30 text-sm text-accent-orange">
          Planen er eldre eller endret. Den globale kontrollen kjøres når du velger «Ta planen i bruk».
        </div>
      )}
      {(plan.quarantine?.length ?? 0) > 0 && (
        <div className="card border-accent-orange/30 text-sm">
          <h2 className="font-semibold">Utelatt fra årsplanen</h2>
          <ul className="mt-2 space-y-1">{plan.quarantine!.map((item) => <li key={item.id}>{item.original_text} — {item.reason}</li>)}</ul>
        </div>
      )}

      {error && <div role="alert" className="card flex items-center gap-2 border-accent-red/30 text-sm text-accent-red"><AlertCircle className="h-4 w-4" />{error}</div>}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-3">
          <div className="flex items-end justify-between gap-4">
            <div><h2 className="text-xl font-semibold">Perioder og temaer</h2><p className="mt-1 text-sm text-text-muted">{plan.periods.length} perioder i faglig progresjon</p></div>
          </div>

          {plan.periods.map((period, index) => {
            const isExpanded = expanded === period.id;
            const isEditing = periodDraft?.id === period.id;
            const approvedKinds = new Set(
              period.materials
                .filter((material) => material.status === "approved" || material.status === "used")
                .map((material) => material.kind),
            );
            const missing = requiredKinds.filter((kind) => !approvedKinds.has(kind));
            return (
              <article key={period.id} className="overflow-hidden rounded-xl border border-border bg-surface shadow-soft-sm">
                <div className="flex flex-wrap items-center gap-3 p-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-blue/10 text-sm font-semibold text-accent-blue">{index + 1}</div>
                  <button className="min-w-0 flex-1 text-left" onClick={() => setExpanded(isExpanded ? "" : period.id)} aria-expanded={isExpanded}>
                    <div className="text-xs text-text-muted">{weekRange(period)} · {period.lesson_count} timer</div>
                    <h3 className="truncate font-semibold">{period.title}</h3>
                  </button>
                  <div className="flex items-center gap-2">
                    {period.materials.length > 0 && <span className="badge bg-accent-purple/10 text-accent-purple">{period.materials.length} filer</span>}
                    <select
                      className="rounded-lg border border-border bg-bg px-2 py-1.5 text-xs"
                      value={period.status}
                      disabled={savingId === period.id}
                      onChange={(event) => void changePeriodStatus(period, event.target.value as YearPlanPeriodStatus)}
                      aria-label={`Status for ${period.title}`}
                    >
                      {Object.entries(periodLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <button className="btn-ghost !px-2 !py-1.5" onClick={() => setExpanded(isExpanded ? "" : period.id)} aria-label={isExpanded ? "Lukk periode" : "Åpne periode"}>
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-border bg-bg/40 p-4 sm:p-5">
                    <div className="mb-4 flex justify-end">
                      {isEditing ? (
                        <div className="flex gap-2">
                          <button className="btn-secondary" onClick={() => setPeriodDraft(null)} disabled={savingId === period.id}>
                            <X className="h-4 w-4" /> Avbryt
                          </button>
                          <button className="btn-primary" onClick={() => void savePeriodDraft()} disabled={savingId === period.id || !periodDraft.title.trim()}>
                            {savingId === period.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Lagre periode
                          </button>
                        </div>
                      ) : (
                        <button className="btn-secondary" onClick={() => setPeriodDraft({ ...period })}>
                          <Pencil className="h-4 w-4" /> Rediger periode
                        </button>
                      )}
                    </div>

                    {isEditing ? (
                      <div className="grid gap-4 rounded-xl border border-border bg-surface p-4 sm:grid-cols-2">
                        <label className="text-sm font-medium">Periodetittel
                          <input className="input mt-2" value={periodDraft.title} onChange={(event) => setPeriodDraft({ ...periodDraft, title: event.target.value })} />
                        </label>
                        <label className="text-sm font-medium">Tema
                          <input className="input mt-2" value={periodDraft.theme} onChange={(event) => setPeriodDraft({ ...periodDraft, theme: event.target.value })} />
                        </label>
                        <label className="text-sm font-medium sm:col-span-2">Kort beskrivelse
                          <textarea className="input mt-2 min-h-24 resize-y" value={periodDraft.overview} onChange={(event) => setPeriodDraft({ ...periodDraft, overview: event.target.value })} />
                        </label>
                        <label className="text-sm font-medium">Læringsmål <span className="font-normal text-text-muted">(ett per linje)</span>
                          <textarea className="input mt-2 min-h-32 resize-y" value={periodDraft.learning_goals.join("\n")} onChange={(event) => setPeriodDraft({ ...periodDraft, learning_goals: event.target.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean) })} />
                        </label>
                        <label className="text-sm font-medium">Kompetansemål <span className="font-normal text-text-muted">(ett per linje)</span>
                          <textarea className="input mt-2 min-h-32 resize-y" value={periodDraft.competency_goals.join("\n")} onChange={(event) => setPeriodDraft({ ...periodDraft, competency_goals: event.target.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean) })} />
                        </label>
                        <label className="text-sm font-medium">Sentrale begreper <span className="font-normal text-text-muted">(kommaseparert)</span>
                          <textarea className="input mt-2 min-h-24 resize-y" value={periodDraft.key_concepts.join(", ")} onChange={(event) => setPeriodDraft({ ...periodDraft, key_concepts: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} />
                        </label>
                        <label className="text-sm font-medium">Aktiviteter <span className="font-normal text-text-muted">(én per linje)</span>
                          <textarea className="input mt-2 min-h-24 resize-y" value={periodDraft.suggested_activities.join("\n")} onChange={(event) => setPeriodDraft({ ...periodDraft, suggested_activities: event.target.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean) })} />
                        </label>
                        <label className="text-sm font-medium sm:col-span-2">Vurdering
                          <textarea className="input mt-2 min-h-20 resize-y" value={periodDraft.assessment} onChange={(event) => setPeriodDraft({ ...periodDraft, assessment: event.target.value })} />
                        </label>
                      </div>
                    ) : (
                      <>
                        <p className="text-sm leading-relaxed text-text-secondary">{period.overview}</p>
                        <div className="mt-5 grid gap-5 md:grid-cols-2">
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Læringsmål</h4>
                        <ul className="mt-2 space-y-1.5 text-sm text-text-secondary">
                          {period.learning_goals.map((goal) => <li key={goal} className="flex gap-2"><span className="text-accent-blue">•</span>{goal}</li>)}
                        </ul>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Sentrale begreper</h4>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {period.key_concepts.length > 0
                            ? period.key_concepts.map((concept) => <span key={concept} className="badge bg-surface-elevated text-text-secondary">{concept}</span>)
                            : <span className="text-sm text-text-muted">Legges til når læremidlene produseres.</span>}
                        </div>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Aktiviteter</h4>
                        <ul className="mt-2 space-y-1.5 text-sm text-text-secondary">
                          {period.suggested_activities.map((activity) => <li key={activity}>• {activity}</li>)}
                        </ul>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Vurdering</h4>
                        <p className="mt-2 text-sm text-text-secondary">{period.assessment || "Ingen vurdering foreslått."}</p>
                      </div>
                        </div>
                      </>
                    )}

                    <div className="mt-6 rounded-xl border border-accent-blue/20 bg-accent-blue/5 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <h4 className="flex items-center gap-2 font-semibold"><Sparkles className="h-4 w-4 text-accent-blue" /> Produser til denne perioden</h4>
                          <p className="mt-1 text-xs text-text-muted">
                            {mathematicsPlan
                              ? "MateMaTeX fylles ut med tema, matematikkfag, nivå og kompetansemål."
                              : "Generatoren fylles ut med tema, fag, nivå og læringsmål."}
                          </p>
                        </div>
                        {missing.length === 0
                          ? <span className="badge bg-accent-green/10 text-accent-green">Grunnpakken er komplett</span>
                          : <span className="text-xs text-text-muted">Mangler: {missing.map((kind) => materialLabels[kind]).join(", ")}</span>}
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Link
                          className="btn-primary"
                          href={`/teaching-packages/new?${new URLSearchParams({ yearPlan: plan.id, period: period.id })}`}
                        >
                          <Presentation className="h-4 w-4" /> PowerPoint + undervisningspakke
                        </Link>
                        <Link className="btn-primary" href={generationHref(plan, period, "laeringsark", "learning_sheet")}><FileText className="h-4 w-4" /> {mathematicsPlan ? "Teori + oppgaver" : "Læringsark"}</Link>
                        <Link className="btn-secondary" href={generationHref(plan, period, "laeringsark", "worksheet")}><NotebookPen className="h-4 w-4" /> Oppgaveark</Link>
                        <Link className="btn-secondary" href={generationHref(plan, period, "prove", "assessment")}><ClipboardCheck className="h-4 w-4" /> Prøve</Link>
                        <Link className="btn-secondary" href={generationHref(plan, period, "sekvens", "lesson_sequence")}><Layers3 className="h-4 w-4" /> {mathematicsPlan ? "Hefte" : "Sekvens"}</Link>
                        {!mathematicsPlan && (
                          <Link
                            className="btn-secondary"
                            href={`/compendia/new?${new URLSearchParams({
                              topic: period.theme || period.title,
                              subject: plan.subject,
                              level: plan.level,
                              yearPlan: plan.id,
                              period: period.id,
                            })}`}
                          >
                            <FileText className="h-4 w-4" /> Kompendium
                          </Link>
                        )}
                      </div>
                    </div>

                    <div className="mt-5">
                      <div className="mb-2 flex items-center justify-between">
                        <h4 className="font-semibold">Lagrede læremidler</h4>
                        <span className="text-xs text-text-muted">{period.materials.length} totalt</span>
                      </div>
                      {period.materials.length === 0
                        ? <div className="rounded-lg border border-dashed border-border px-4 py-5 text-center text-sm text-text-muted">Ingen godkjente filer ennå.</div>
                        : <div className="space-y-2">{period.materials.map((material) => (
                          <MaterialRow key={material.id} plan={plan} period={period} material={material} onUpdated={setPlan} />
                        ))}</div>}
                    </div>

                    <div className="mt-5">
                      <label className="text-xs font-semibold uppercase tracking-wide text-text-muted" htmlFor={`notes-${period.id}`}>Lærerens notater</label>
                      <textarea
                        id={`notes-${period.id}`}
                        className="input mt-2 min-h-20 resize-y"
                        value={notes[period.id] ?? ""}
                        onChange={(event) => setNotes((current) => ({ ...current, [period.id]: event.target.value }))}
                        placeholder="Hva fungerte? Hva bør endres neste skoleår?"
                      />
                      <button className="btn-secondary mt-2" onClick={() => void saveNotes(period)} disabled={savingId === period.id}>
                        {savingId === period.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookOpenCheck className="h-4 w-4" />} Lagre notat
                      </button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>

        <aside className="space-y-4">
          <section className="card lg:sticky lg:top-24">
            <h2 className="flex items-center gap-2 font-semibold"><CalendarDays className="h-4 w-4 text-accent-blue" /> Dekning</h2>
            <div className="mt-4 space-y-3">
              <div className="flex justify-between text-sm"><span className="text-text-secondary">Perioder klare</span><strong>{plan.periods.filter((period) => period.status === "ready" || period.status === "completed").length}/{plan.periods.length}</strong></div>
              <div className="flex justify-between text-sm"><span className="text-text-secondary">Godkjente filer</span><strong>{stats.approved}</strong></div>
              <div className="flex justify-between text-sm"><span className="text-text-secondary">Kompetansemål</span><strong>{stats.coveredGoals}/{plan.competency_goals.length}</strong></div>
            </div>
            {plan.competency_goals.length === 0 ? (
              <div className="mt-4 rounded-lg bg-accent-orange/10 p-3 text-xs leading-relaxed text-text-secondary">
                Ingen offisielle kompetansemål er lagt inn. Planen er en faglig skisse, ikke dokumentasjon på full læreplandekning.
              </div>
            ) : (
              <div className="mt-4 space-y-2">
                {plan.competency_goals.map((goal) => {
                  const count = plan.periods.filter((period) => period.competency_goals.includes(goal)).length;
                  return <div key={goal} className="rounded-lg border border-border p-2.5 text-xs"><div className="line-clamp-3 text-text-secondary">{goal}</div><div className={`mt-1 font-medium ${count ? "text-accent-green" : "text-accent-red"}`}>{count ? `Dekkes i ${count} perioder` : "Ikke plassert"}</div></div>;
                })}
              </div>
            )}
            <button className="btn-ghost mt-4 w-full" onClick={() => window.location.reload()}><RefreshCw className="h-4 w-4" /> Oppdater oversikt</button>
          </section>
        </aside>
      </section>
    </div>
  );
}
