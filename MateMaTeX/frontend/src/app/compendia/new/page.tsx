"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BookCopy,
  Bot,
  Database,
  Image as ImageIcon,
  LibraryBig,
  Loader2,
  SearchCheck,
  Sparkles,
} from "lucide-react";
import { SUBJECTS, LEVELS } from "@/features/fag/components/constants";
import {
  createCompendiumOutline,
  listYearPlans,
  type CompendiumImageMode,
  type CompendiumKind,
  type YearPlan,
} from "@/lib/platform-api";

const kinds: Array<{ value: CompendiumKind; label: string; description: string }> = [
  { value: "thematic", label: "Tematisk fordypning", description: "Forklarer et tema grundig og sammenhengende." },
  { value: "chronological", label: "Kronologisk oversikt", description: "Ordner utvikling, hendelser og vendepunkter over tid." },
  { value: "reference", label: "Oppslagsverk", description: "Systematiserer mange enheter, steder, personer eller begreper." },
  { value: "comparative", label: "Sammenlignende", description: "Sammenholder samfunn, perioder eller modeller etter faste kriterier." },
  { value: "source_collection", label: "Kildesamling", description: "Kontekstualiserer og organiserer primær- og sekundærkilder." },
  { value: "appendix", label: "Appendiks", description: "Utdyper et eksisterende tema uten å gjenta hovedmaterialet." },
];

const imageChoices: Array<{ value: CompendiumImageMode; label: string; description: string; icon: typeof ImageIcon }> = [
  { value: "none", label: "Uten bilde", description: "Et rent, tekstbasert dokument.", icon: BookCopy },
  { value: "commons", label: "Verifisert Commons", description: "Et fritt bilde med lisens og kildekreditering.", icon: Database },
  { value: "ai", label: "KI-illustrasjon", description: "Pedagogisk illustrasjon, tydelig merket som KI-generert.", icon: Bot },
];

export default function NewCompendiumPage() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("Historie");
  const [level, setLevel] = useState("VG2");
  const [kind, setKind] = useState<CompendiumKind>("thematic");
  const [purpose, setPurpose] = useState("");
  const [audience, setAudience] = useState("Elever i videregående skole");
  const [targetPages, setTargetPages] = useState(16);
  const [chapterCount, setChapterCount] = useState(6);
  const [goals, setGoals] = useState("");
  const [sourceBrief, setSourceBrief] = useState("");
  const [includeTimeline, setIncludeTimeline] = useState(true);
  const [includeTables, setIncludeTables] = useState(true);
  const [includeGlossary, setIncludeGlossary] = useState(true);
  const [includeTasks, setIncludeTasks] = useState(false);
  const [imageMode, setImageMode] = useState<CompendiumImageMode>("none");
  const [yearPlans, setYearPlans] = useState<YearPlan[]>([]);
  const [yearPlanId, setYearPlanId] = useState("");
  const [periodIds, setPeriodIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listYearPlans().then(setYearPlans).catch(() => undefined);
    const params = new URLSearchParams(window.location.search);
    const queryTopic = params.get("topic");
    const querySubject = params.get("subject");
    const queryLevel = params.get("level");
    const queryPlan = params.get("yearPlan");
    const queryPeriod = params.get("period");
    if (queryTopic) setTopic(queryTopic);
    if (querySubject) setSubject(querySubject);
    if (queryLevel) setLevel(queryLevel);
    if (queryPlan) setYearPlanId(queryPlan);
    if (queryPeriod) setPeriodIds([queryPeriod]);
  }, []);

  const selectedPlan = yearPlans.find((plan) => plan.id === yearPlanId);
  const wordsPerChapter = useMemo(
    () => Math.round((targetPages * 420) / chapterCount),
    [targetPages, chapterCount],
  );

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const compendium = await createCompendiumOutline({
        title: title.trim() || undefined,
        topic: topic.trim(),
        subject,
        level,
        kind,
        purpose: purpose.trim(),
        audience: audience.trim(),
        target_pages: targetPages,
        chapter_count: chapterCount,
        competency_goals: goals.split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
        source_brief: sourceBrief.trim(),
        include_timeline: includeTimeline,
        include_tables: includeTables,
        include_glossary: includeGlossary,
        include_reflection_tasks: includeTasks,
        image_mode: imageMode,
        year_plan_id: yearPlanId || null,
        period_ids: yearPlanId ? periodIds : [],
        use_ai: true,
      });
      router.push(`/compendia/${compendium.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke lage disposisjonen.");
      setLoading(false);
    }
  }

  function togglePeriod(periodId: string) {
    setPeriodIds((current) => current.includes(periodId)
      ? current.filter((id) => id !== periodId)
      : [...current, periodId]);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link href="/compendia" className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary">
        <ArrowLeft className="h-4 w-4" /> Kompendier
      </Link>
      <header>
        <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-accent-teal/10 px-3 py-1 text-xs font-medium text-accent-teal">
          <SearchCheck className="h-3.5 w-3.5" /> Disposisjon og avgrensning først
        </div>
        <h1 className="font-display text-4xl">Nytt kompendium</h1>
        <p className="mt-2 max-w-3xl text-text-secondary">
          Først lager verkstedet en avgrensningskontrakt og innholdsfortegnelse. Ingen kapitler produseres før du har godkjent strukturen.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-5">
        <section className="card">
          <h2 className="flex items-center gap-2 font-semibold"><LibraryBig className="h-5 w-5 text-accent-teal" /> Grunnlag</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium sm:col-span-2">Tema
              <input className="input mt-2" required minLength={2} value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="For eksempel: Kongedømmer i Europa omkring 1450" />
            </label>
            <label className="text-sm font-medium">Egen tittel <span className="font-normal text-text-muted">(valgfritt)</span>
              <input className="input mt-2" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Lages automatisk hvis feltet står tomt" />
            </label>
            <label className="text-sm font-medium">Målgruppe
              <input className="input mt-2" value={audience} onChange={(event) => setAudience(event.target.value)} />
            </label>
            <label className="text-sm font-medium">Fag
              <select className="input mt-2" value={subject} onChange={(event) => setSubject(event.target.value)}>
                {SUBJECTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">Nivå
              <select className="input mt-2" value={level} onChange={(event) => setLevel(event.target.value)}>
                {LEVELS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium sm:col-span-2">Formål
              <textarea className="input mt-2 min-h-24 resize-y" value={purpose} onChange={(event) => setPurpose(event.target.value)} placeholder="Hva skal elevene bruke dokumentet til, og hva skal det utdype?" />
            </label>
          </div>
        </section>

        <section className="card">
          <h2 className="font-semibold">Dokumentform</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {kinds.map((item) => (
              <label key={item.value} className={`cursor-pointer rounded-xl border p-4 transition ${kind === item.value ? "border-accent-teal bg-accent-teal/10" : "border-border hover:border-text-muted/40"}`}>
                <input className="sr-only" type="radio" name="kind" value={item.value} checked={kind === item.value} onChange={() => setKind(item.value)} />
                <span className="text-sm font-semibold">{item.label}</span>
                <span className="mt-1 block text-xs leading-relaxed text-text-muted">{item.description}</span>
              </label>
            ))}
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium">Omtrentlig sidetall
              <input className="input mt-2" type="number" min={4} max={60} value={targetPages} onChange={(event) => setTargetPages(Number(event.target.value))} />
            </label>
            <label className="text-sm font-medium">Antall kapitler
              <input className="input mt-2" type="number" min={2} max={14} value={chapterCount} onChange={(event) => setChapterCount(Number(event.target.value))} />
            </label>
          </div>
          <p className="mt-3 text-xs text-text-muted">Planlagt omfang: omtrent {wordsPerChapter} ord per kapittel. Du kan redigere hvert kapittel separat.</p>
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {[
              [includeTimeline, setIncludeTimeline, "Tidslinje der det er faglig relevant"],
              [includeTables, setIncludeTables, "Tabeller og systematiske sammenligninger"],
              [includeGlossary, setIncludeGlossary, "Begrepsliste"],
              [includeTasks, setIncludeTasks, "Refleksjons- og fordypningsoppgaver"],
            ].map(([checked, setter, label]) => (
              <label key={String(label)} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm">
                <input type="checkbox" checked={checked as boolean} onChange={(event) => (setter as (value: boolean) => void)(event.target.checked)} />
                {String(label)}
              </label>
            ))}
          </div>
        </section>

        <section className="card">
          <h2 className="flex items-center gap-2 font-semibold"><ImageIcon className="h-5 w-5 text-accent-purple" /> Bildevalg</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {imageChoices.map((choice) => {
              const Icon = choice.icon;
              return (
                <label key={choice.value} className={`cursor-pointer rounded-xl border p-4 transition ${imageMode === choice.value ? "border-accent-purple bg-accent-purple/10" : "border-border"}`}>
                  <input className="sr-only" type="radio" name="imageMode" checked={imageMode === choice.value} onChange={() => setImageMode(choice.value)} />
                  <Icon className="h-5 w-5 text-accent-purple" />
                  <span className="mt-3 block text-sm font-semibold">{choice.label}</span>
                  <span className="mt-1 block text-xs text-text-muted">{choice.description}</span>
                </label>
              );
            })}
          </div>
        </section>

        <section className="card space-y-5">
          <div>
            <label className="text-sm font-medium">Kompetansemål <span className="font-normal text-text-muted">(ett per linje)</span>
              <textarea className="input mt-2 min-h-28 resize-y" value={goals} onChange={(event) => setGoals(event.target.value)} placeholder="Målene beholdes ordrett og brukes som ramme." />
            </label>
          </div>
          <div>
            <label className="text-sm font-medium">Kildegrunnlag og lærerens rammer
              <textarea className="input mt-2 min-h-36 resize-y" value={sourceBrief} onChange={(event) => setSourceBrief(event.target.value)} placeholder="Lim inn kildenotater, avgrensninger, litteraturliste eller tekst som skal være primærgrunnlag." />
            </label>
            <p className="mt-2 text-xs text-text-muted">Kildedata behandles som innhold, aldri som instruksjoner til modellen.</p>
          </div>
        </section>

        {yearPlans.length > 0 && (
          <section className="card">
            <h2 className="font-semibold">Koble til årsplan <span className="font-normal text-text-muted">(valgfritt)</span></h2>
            <select className="input mt-4" value={yearPlanId} onChange={(event) => { setYearPlanId(event.target.value); setPeriodIds([]); }}>
              <option value="">Ikke koble til årsplan nå</option>
              {yearPlans.map((plan) => <option key={plan.id} value={plan.id}>{plan.title}</option>)}
            </select>
            {selectedPlan && (
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {selectedPlan.periods.map((period) => (
                  <label key={period.id} className="flex items-start gap-2 rounded-lg border border-border px-3 py-2 text-sm">
                    <input className="mt-0.5" type="checkbox" checked={periodIds.includes(period.id)} onChange={() => togglePeriod(period.id)} />
                    <span><span className="font-medium">{period.title}</span><span className="block text-xs text-text-muted">{period.theme}</span></span>
                  </label>
                ))}
              </div>
            )}
          </section>
        )}

        {error && <div role="alert" className="card border-accent-red/30 text-sm text-accent-red">{error}</div>}
        <div className="flex flex-wrap justify-end gap-3">
          <Link href="/compendia" className="btn-secondary">Avbryt</Link>
          <button type="submit" className="btn-primary min-w-52" disabled={loading || topic.trim().length < 2}>
            {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Lager avgrensning …</> : <><Sparkles className="h-4 w-4" /> Lag disposisjon</>}
          </button>
        </div>
      </form>
    </div>
  );
}
