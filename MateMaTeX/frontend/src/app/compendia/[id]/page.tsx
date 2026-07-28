"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  BookCheck,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  FolderCheck,
  Loader2,
  Pencil,
  RefreshCw,
  Save,
  SearchCheck,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import {
  approveCompendium,
  compileCompendium,
  compendiumDownloadUrl,
  generateCompendiumChapter,
  getCompendium,
  repairCompendiumChapter,
  updateCompendium,
  updateCompendiumChapter,
  type Compendium,
  type CompendiumChapter,
  type CompendiumChapterStatus,
  type ScopeContract,
} from "@/lib/platform-api";

const chapterStatusLabels: Record<CompendiumChapterStatus, string> = {
  planned: "Planlagt",
  generated: "Klar til kontroll",
  approved: "Godkjent",
  needs_revision: "Må revideres",
};

const statusLabels = {
  outline: "Disposisjon",
  writing: "Under produksjon",
  review: "Til lærerkontroll",
  approved: "Godkjent",
  archived: "Arkivert",
};

function isTransientSource(url: string) {
  if (!url) return false;
  try {
    return new URL(url).hostname === "vertexaisearch.cloud.google.com";
  } catch {
    return true;
  }
}

function isMeaningfulScopeValue(value: string) {
  const normalized = value.trim().toLocaleLowerCase("nb");
  return Boolean(normalized)
    && !normalized.includes("ikke spesifisert")
    && !normalized.includes("avgrenses av læreren")
    && !normalized.includes("før produksjon");
}

function ChapterCard({
  compendium,
  chapter,
  expanded,
  busy,
  onToggle,
  onUpdated,
  onError,
}: {
  compendium: Compendium;
  chapter: CompendiumChapter;
  expanded: boolean;
  busy: boolean;
  onToggle: () => void;
  onUpdated: (value: Compendium) => void;
  onError: (message: string) => void;
}) {
  const [editingOutline, setEditingOutline] = useState(false);
  const [editingContent, setEditingContent] = useState(false);
  const [title, setTitle] = useState(chapter.title);
  const [purpose, setPurpose] = useState(chapter.purpose);
  const [questions, setQuestions] = useState(chapter.guiding_questions.join("\n"));
  const [content, setContent] = useState(chapter.content_markdown);
  const [localBusy, setLocalBusy] = useState("");
  const visibleSources = chapter.sources.filter((source) => !isTransientSource(source.url));

  useEffect(() => {
    setTitle(chapter.title);
    setPurpose(chapter.purpose);
    setQuestions(chapter.guiding_questions.join("\n"));
    setContent(chapter.content_markdown);
  }, [chapter.updated_at, chapter.title, chapter.purpose, chapter.guiding_questions, chapter.content_markdown]);

  async function run(action: string, operation: () => Promise<Compendium>) {
    setLocalBusy(action);
    onError("");
    try {
      onUpdated(await operation());
    } catch (err) {
      onError(err instanceof Error ? err.message : "Handlingen mislyktes.");
    } finally {
      setLocalBusy("");
    }
  }

  async function saveOutline() {
    await run("outline", () => updateCompendiumChapter(compendium.id, chapter.id, {
      title: title.trim(),
      purpose: purpose.trim(),
      guiding_questions: questions.split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
    }));
    setEditingOutline(false);
  }

  async function saveContent() {
    await run("content", () => updateCompendiumChapter(compendium.id, chapter.id, {
      content_markdown: content,
      status: "generated",
    }));
    setEditingContent(false);
  }

  const working = busy || Boolean(localBusy);
  const statusClass = chapter.status === "approved"
    ? "bg-accent-green/10 text-accent-green"
    : chapter.status === "needs_revision"
      ? "bg-accent-orange/10 text-accent-orange"
      : chapter.status === "generated"
        ? "bg-accent-blue/10 text-accent-blue"
        : "bg-surface-elevated text-text-muted";

  return (
    <article className="overflow-hidden rounded-xl border border-border bg-surface shadow-soft-sm">
      <div className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-teal/10 text-sm font-semibold text-accent-teal">{chapter.order + 1}</div>
        <button className="min-w-0 flex-1 text-left" onClick={onToggle} aria-expanded={expanded}>
          <h3 className="truncate font-semibold">{chapter.title}</h3>
          <p className="mt-0.5 truncate text-xs text-text-muted">{chapter.purpose}</p>
        </button>
        <span className={`badge ${statusClass}`}>{chapterStatusLabels[chapter.status]}</span>
        <button className="btn-ghost !px-2 !py-1.5" onClick={onToggle} aria-label={expanded ? "Lukk kapittel" : "Åpne kapittel"}>
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {expanded && (
        <div className="border-t border-border bg-bg/40 p-4 sm:p-5">
          <div className="flex flex-wrap justify-end gap-2">
            {!editingOutline && (
              <button className="btn-secondary" onClick={() => setEditingOutline(true)} disabled={working}>
                <Pencil className="h-4 w-4" /> Rediger ramme
              </button>
            )}
            <button
              className="btn-primary"
              disabled={working || compendium.status === "outline"}
              onClick={() => void run("generate", () => generateCompendiumChapter(compendium.id, chapter.id))}
              title={compendium.status === "outline" ? "Godkjenn disposisjonen først" : ""}
            >
              {localBusy === "generate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {chapter.content_markdown ? "Lag ny versjon" : "Produser kapittel"}
            </button>
            {chapter.status === "needs_revision" && chapter.content_markdown && chapter.verification_notes.length > 0 && (
              <button
                className="btn-primary !bg-accent-teal hover:!bg-accent-teal/90"
                disabled={working || compendium.status === "outline"}
                onClick={() => void run("repair", () => repairCompendiumChapter(compendium.id, chapter.id))}
                title="Undersøk kontrollmerknadene, rett teksten og kontroller resultatet på nytt"
              >
                {localBusy === "repair" ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchCheck className="h-4 w-4" />}
                {localBusy === "repair" ? "Sjekker og retter…" : "Sjekk og rett automatisk"}
              </button>
            )}
          </div>

          {editingOutline ? (
            <div className="mt-4 grid gap-4 rounded-xl border border-border bg-surface p-4">
              <label className="text-sm font-medium">Kapitteltittel
                <input className="input mt-2" value={title} onChange={(event) => setTitle(event.target.value)} />
              </label>
              <label className="text-sm font-medium">Kapittelformål
                <textarea className="input mt-2 min-h-20 resize-y" value={purpose} onChange={(event) => setPurpose(event.target.value)} />
              </label>
              <label className="text-sm font-medium">Styrende spørsmål <span className="font-normal text-text-muted">(ett per linje)</span>
                <textarea className="input mt-2 min-h-24 resize-y" value={questions} onChange={(event) => setQuestions(event.target.value)} />
              </label>
              <div className="flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => setEditingOutline(false)}><X className="h-4 w-4" /> Avbryt</button>
                <button className="btn-primary" onClick={() => void saveOutline()} disabled={localBusy === "outline" || title.trim().length < 2}>
                  {localBusy === "outline" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Lagre ramme
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div><h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Formål</h4><p className="mt-2 text-sm leading-relaxed text-text-secondary">{chapter.purpose}</p></div>
              <div><h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Styrende spørsmål</h4><ul className="mt-2 space-y-1 text-sm text-text-secondary">{chapter.guiding_questions.map((question) => <li key={question}>• {question}</li>)}</ul></div>
            </div>
          )}

          {chapter.content_markdown && (
            <div className="mt-5 rounded-xl border border-border bg-surface p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h4 className="font-semibold">Kapitteltekst</h4>
                <button className="btn-secondary" onClick={() => setEditingContent((value) => !value)}>
                  <Pencil className="h-4 w-4" /> {editingContent ? "Lukk redigering" : "Rediger tekst"}
                </button>
              </div>
              {editingContent ? (
                <>
                  <textarea className="input mt-4 min-h-[420px] resize-y font-mono text-sm leading-relaxed" value={content} onChange={(event) => setContent(event.target.value)} />
                  <div className="mt-3 flex justify-end">
                    <button className="btn-primary" onClick={() => void saveContent()} disabled={localBusy === "content" || content.trim().length < 100}>
                      {localBusy === "content" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Lagre redigert tekst
                    </button>
                  </div>
                </>
              ) : (
                <div className="mt-4 max-h-[520px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-bg px-4 py-4 text-sm leading-7 text-text-secondary">{chapter.content_markdown}</div>
              )}
            </div>
          )}

          {chapter.verification_notes.length > 0 && (
            <div className={`mt-4 rounded-lg border p-3 text-sm ${chapter.status === "needs_revision" ? "border-accent-orange/30 bg-accent-orange/10" : "border-accent-blue/20 bg-accent-blue/5"}`}>
              <h4 className="flex items-center gap-2 font-semibold">
                {chapter.status === "needs_revision" ? <ShieldAlert className="h-4 w-4 text-accent-orange" /> : <ShieldCheck className="h-4 w-4 text-accent-blue" />}
                {chapter.status === "needs_revision" ? "Kontrollmerknader" : "Ny kontroll"}
              </h4>
              <ul className="mt-2 space-y-1 text-text-secondary">{chapter.verification_notes.map((note) => <li key={note}>• {note}</li>)}</ul>
            </div>
          )}

          {chapter.revision_summary.length > 0 && (
            <div className="mt-4 rounded-lg border border-accent-green/25 bg-accent-green/5 p-3 text-sm">
              <h4 className="flex items-center gap-2 font-semibold">
                <CheckCircle2 className="h-4 w-4 text-accent-green" />
                Automatisk rettet
              </h4>
              <ul className="mt-2 space-y-1 text-text-secondary">
                {chapter.revision_summary.map((change) => <li key={change}>• {change}</li>)}
              </ul>
            </div>
          )}

          {chapter.previous_content_markdown && (
            <details className="mt-4 rounded-lg border border-border bg-surface">
              <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
                Sammenlign med forrige versjon
                <span className="ml-2 font-normal text-text-muted">Versjon {chapter.revision_count + 1}</span>
              </summary>
              <div className="grid gap-3 border-t border-border p-3 lg:grid-cols-2">
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">Før</h4>
                  <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-bg p-3 text-xs leading-6 text-text-secondary">
                    {chapter.previous_content_markdown}
                  </div>
                </div>
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">Etter</h4>
                  <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-bg p-3 text-xs leading-6 text-text-secondary">
                    {chapter.content_markdown}
                  </div>
                </div>
              </div>
            </details>
          )}

          {visibleSources.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Registrerte kilder</h4>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {visibleSources.map((source, index) => (
                  source.url
                    ? <a key={`${source.url}-${index}`} href={source.url} target="_blank" rel="noreferrer" className="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-secondary hover:border-accent-blue/40"><span className="font-medium text-text-primary">{source.title}</span>{source.publisher && <span className="mt-0.5 block text-text-muted">{source.publisher}</span>}</a>
                    : <div key={`${source.title}-${index}`} className="rounded-lg border border-border bg-surface px-3 py-2 text-xs">{source.title}</div>
                ))}
              </div>
            </div>
          )}

          {chapter.content_markdown && (
            <div className="mt-5 flex flex-wrap justify-end gap-2 border-t border-border pt-4">
              <button className="btn-secondary" disabled={working} onClick={() => void run("revision", () => updateCompendiumChapter(compendium.id, chapter.id, { status: "needs_revision" }))}>
                <RefreshCw className="h-4 w-4" /> Må revideres
              </button>
              <button className="btn-primary" disabled={working || chapter.status === "approved"} onClick={() => void run("approve", () => updateCompendiumChapter(compendium.id, chapter.id, { status: "approved" }))}>
                {localBusy === "approve" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                {chapter.status === "approved" ? "Kapittel godkjent" : "Godkjenn kapittel"}
              </button>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default function CompendiumPage({ params }: { params: { id: string } }) {
  const [compendium, setCompendium] = useState<Compendium | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [expanded, setExpanded] = useState("");
  const [scopeEditing, setScopeEditing] = useState(false);
  const [scopeDraft, setScopeDraft] = useState<ScopeContract | null>(null);
  const [batchProgress, setBatchProgress] = useState("");

  useEffect(() => {
    getCompendium(params.id)
      .then((loaded) => {
        setCompendium(loaded);
        setExpanded(loaded.chapters[0]?.id ?? "");
        setScopeDraft(loaded.scope_contract);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste kompendiet."))
      .finally(() => setLoading(false));
  }, [params.id]);

  const stats = useMemo(() => {
    if (!compendium) return { approved: 0, produced: 0, sources: 0 };
    const sourceKeys = new Set(compendium.chapters.flatMap((chapter) => chapter.sources
      .filter((source) => !isTransientSource(source.url))
      .map((source) => source.url || source.title)));
    return {
      approved: compendium.chapters.filter((chapter) => chapter.status === "approved").length,
      produced: compendium.chapters.filter((chapter) => chapter.content_markdown.trim()).length,
      sources: sourceKeys.size,
    };
  }, [compendium]);

  async function run(actionName: string, operation: () => Promise<Compendium>) {
    setAction(actionName);
    setError("");
    try {
      const updated = await operation();
      setCompendium(updated);
      setScopeDraft(updated.scope_contract);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Handlingen mislyktes.");
    } finally {
      setAction("");
    }
  }

  async function approveOutline() {
    if (!compendium) return;
    await run("outline", () => updateCompendium(compendium.id, { status: "writing" }));
  }

  async function saveScope() {
    if (!compendium || !scopeDraft) return;
    await run("scope", () => updateCompendium(compendium.id, { scope_contract: scopeDraft }));
    setScopeEditing(false);
  }

  async function generateAll() {
    if (!compendium) return;
    const chapters = compendium.chapters.filter((chapter) => chapter.status === "planned" || chapter.status === "needs_revision");
    if (!chapters.length) return;
    setAction("batch");
    setError("");
    try {
      for (let index = 0; index < chapters.length; index += 1) {
        setBatchProgress(`Produserer kapittel ${index + 1} av ${chapters.length}: ${chapters[index].title}`);
        const updated = await generateCompendiumChapter(compendium.id, chapters[index].id);
        setCompendium(updated);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kapittelproduksjonen stoppet.");
    } finally {
      setAction("");
      setBatchProgress("");
    }
  }

  if (loading) return <div className="flex items-center gap-2 py-12 text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster kompendiet …</div>;
  if (!compendium) return <div role="alert" className="card text-accent-red">{error || "Kompendiet finnes ikke."}</div>;

  const allApproved = stats.approved === compendium.chapters.length && compendium.chapters.length > 0;
  const canCompile = allApproved && !action;
  const scope = compendium.scope_contract;
  const scopeReady = isMeaningfulScopeValue(scope.reference_date)
    && isMeaningfulScopeValue(scope.geography);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <Link href="/compendia" className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"><ArrowLeft className="h-4 w-4" /> Fagbibliotek</Link>

      <header className="rounded-2xl border border-border bg-surface p-5 shadow-soft-sm sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide text-text-muted">
              <span>{compendium.subject} · {compendium.level}</span>
              <span className="badge bg-accent-teal/10 text-accent-teal">{statusLabels[compendium.status]}</span>
              <span>{compendium.target_pages} sider · {compendium.chapters.length} kapitler</span>
            </div>
            <h1 className="mt-3 font-display text-3xl tracking-tight sm:text-4xl">{compendium.title}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-text-secondary">{compendium.purpose || compendium.topic}</p>
          </div>
          {compendium.status === "outline" && (
            <button className="btn-primary" onClick={() => void approveOutline()} disabled={action === "outline"}>
              {action === "outline" ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookCheck className="h-4 w-4" />} Godkjenn disposisjonen
            </button>
          )}
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center">
          <div>
            <div className="mb-2 flex justify-between text-xs text-text-muted"><span>Kapittelprogresjon</span><span>{stats.approved}/{compendium.chapters.length} godkjent</span></div>
            <div className="h-2.5 overflow-hidden rounded-full bg-surface-elevated"><div className="h-full rounded-full bg-accent-teal" style={{ width: `${Math.round((stats.approved / Math.max(1, compendium.chapters.length)) * 100)}%` }} /></div>
          </div>
          <div className="text-sm"><strong>{stats.produced}</strong> <span className="text-text-muted">produsert</span></div>
          <div className="text-sm"><strong>{stats.sources}</strong> <span className="text-text-muted">kilder</span></div>
          <div className="text-sm"><strong>v{compendium.artifact_version}</strong> <span className="text-text-muted">dokument</span></div>
        </div>
      </header>

      {error && <div role="alert" className="card flex items-start gap-2 border-accent-red/30 text-sm text-accent-red"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <section className="rounded-xl border border-accent-teal/20 bg-accent-teal/5 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h2 className="flex items-center gap-2 font-semibold"><SearchCheck className="h-5 w-5 text-accent-teal" /> Rammer for innholdet</h2><p className="mt-1 text-xs text-text-muted">Tidsrom og geografi gjør sluttproduktet tydeligere og mer presist.</p></div>
              {!scopeEditing && <button className="btn-secondary" onClick={() => setScopeEditing(true)}><Pencil className="h-4 w-4" /> Rediger</button>}
            </div>
            {scopeEditing && scopeDraft ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-medium">Referansetid<input className="input mt-2" value={scopeDraft.reference_date} onChange={(event) => setScopeDraft({ ...scopeDraft, reference_date: event.target.value })} /></label>
                <label className="text-sm font-medium">Geografi<input className="input mt-2" value={scopeDraft.geography} onChange={(event) => setScopeDraft({ ...scopeDraft, geography: event.target.value })} /></label>
                <label className="text-sm font-medium">Tas med <span className="font-normal text-text-muted">(ett per linje)</span><textarea className="input mt-2 min-h-24" value={scopeDraft.inclusion_criteria.join("\n")} onChange={(event) => setScopeDraft({ ...scopeDraft, inclusion_criteria: event.target.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean) })} /></label>
                <label className="text-sm font-medium">Tas ikke med <span className="font-normal text-text-muted">(ett per linje)</span><textarea className="input mt-2 min-h-24" value={scopeDraft.exclusions.join("\n")} onChange={(event) => setScopeDraft({ ...scopeDraft, exclusions: event.target.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean) })} /></label>
                <label className="text-sm font-medium">Dekningsnivå<select className="input mt-2" value={scopeDraft.completeness_label} onChange={(event) => setScopeDraft({ ...scopeDraft, completeness_label: event.target.value as ScopeContract["completeness_label"] })}><option value="selected">Faglig utvalg</option><option value="documented">Dokumentert oversikt</option><option value="complete">Fullstendig innen kriteriene</option></select></label>
                <label className="text-sm font-medium">Presisering<textarea className="input mt-2 min-h-24" value={scopeDraft.completeness_note} onChange={(event) => setScopeDraft({ ...scopeDraft, completeness_note: event.target.value })} /></label>
                <div className="flex justify-end gap-2 sm:col-span-2"><button className="btn-secondary" onClick={() => { setScopeEditing(false); setScopeDraft(scope); }}><X className="h-4 w-4" /> Avbryt</button><button className="btn-primary" onClick={() => void saveScope()} disabled={action === "scope"}>{action === "scope" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Lagre avgrensning</button></div>
              </div>
            ) : (
              <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                <div><div className="text-xs font-semibold uppercase tracking-wide text-text-muted">Referansetid</div><p className="mt-1 text-text-secondary">{scope.reference_date || "Ikke spesifisert"}</p></div>
                <div><div className="text-xs font-semibold uppercase tracking-wide text-text-muted">Geografi</div><p className="mt-1 text-text-secondary">{scope.geography || "Ikke spesifisert"}</p></div>
                <div><div className="text-xs font-semibold uppercase tracking-wide text-text-muted">Tas med</div><ul className="mt-1 text-text-secondary">{scope.inclusion_criteria.map((item) => <li key={item}>• {item}</li>)}</ul></div>
                <div><div className="text-xs font-semibold uppercase tracking-wide text-text-muted">Tas ikke med</div><ul className="mt-1 text-text-secondary">{scope.exclusions.map((item) => <li key={item}>• {item}</li>)}</ul></div>
                <p className="rounded-lg bg-surface p-3 text-text-secondary sm:col-span-2"><strong className="text-text-primary">Dekningsnivå:</strong> {scope.completeness_note}</p>
              </div>
            )}
          </section>

          <div className="flex flex-wrap items-end justify-between gap-3">
            <div><h2 className="text-xl font-semibold">Kapitler</h2><p className="mt-1 text-sm text-text-muted">Research, kontroller og godkjenn ett kapittel om gangen.</p></div>
            <button className="btn-primary" disabled={compendium.status === "outline" || action === "batch" || !compendium.chapters.some((chapter) => chapter.status === "planned" || chapter.status === "needs_revision")} onClick={() => void generateAll()}>
              {action === "batch" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Produser gjenstående
            </button>
          </div>
          {batchProgress && <div className="rounded-lg border border-accent-blue/20 bg-accent-blue/5 px-4 py-3 text-sm text-text-secondary">{batchProgress}</div>}
          {compendium.chapters.map((chapter) => (
            <ChapterCard
              key={chapter.id}
              compendium={compendium}
              chapter={chapter}
              expanded={expanded === chapter.id}
              busy={action === "batch"}
              onToggle={() => setExpanded(expanded === chapter.id ? "" : chapter.id)}
              onUpdated={setCompendium}
              onError={setError}
            />
          ))}
        </div>

        <aside className="space-y-4">
          <section className="card lg:sticky lg:top-24">
            <h2 className="flex items-center gap-2 font-semibold"><FolderCheck className="h-5 w-5 text-accent-purple" /> Sluttprodukt</h2>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-text-secondary">Godkjente kapitler</span><strong>{stats.approved}/{compendium.chapters.length}</strong></div>
              <div className="flex justify-between"><span className="text-text-secondary">Kilder</span><strong>{stats.sources}</strong></div>
              <div className="flex justify-between"><span className="text-text-secondary">Bilde</span><strong>{compendium.image_mode === "commons" ? "Commons" : compendium.image_mode === "ai" ? "KI-merket" : "Nei"}</strong></div>
              <div className="flex justify-between"><span className="text-text-secondary">Årsplankobling</span><strong>{compendium.period_ids.length || "Nei"}</strong></div>
            </div>

            {!allApproved && (
              <div className="mt-4 rounded-lg bg-accent-orange/10 p-3 text-xs leading-relaxed text-text-secondary">
                Alle kapitler må leses og godkjennes av læreren før PDF og Word bygges.
              </div>
            )}

            <div className="mt-4 rounded-lg border border-border bg-bg p-3 text-xs leading-relaxed">
              <div className="font-semibold text-text-primary">Automatisk eksportkontroll</div>
              <ul className="mt-2 space-y-1.5 text-text-secondary">
                <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-green" /> Tekniske koder og rå søkelenker fjernes.</li>
                <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-green" /> Lærerens kontrollmerknader holdes utenfor elevutgaven.</li>
                <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-green" /> Kilder vises med ryddige, klikkbare titler.</li>
                <li className="flex gap-2">
                  {scopeReady ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-green" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-orange" />}
                  {scopeReady ? "Tidsrom og geografi er presisert." : "Uavklarte rammefelt skjules i elevutgaven. Fyll dem ut for best resultat."}
                </li>
              </ul>
            </div>

            <button className="btn-primary mt-5 w-full" disabled={!canCompile} onClick={() => void run("compile", () => compileCompendium(compendium.id))}>
              {action === "compile" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {compendium.artifact_version ? "Bygg ny elevversjon" : "Bygg PDF og Word"}
            </button>

            {compendium.artifact_version > 0 && (
              <div className="mt-3 grid gap-2">
                <a className="btn-secondary w-full" href={compendiumDownloadUrl(compendium.id, "pdf")}><Download className="h-4 w-4" /> Last ned PDF · v{compendium.artifact_version}</a>
                <a className="btn-secondary w-full" href={compendiumDownloadUrl(compendium.id, "docx")}><Download className="h-4 w-4" /> Last ned Word</a>
              </div>
            )}

            {compendium.status === "review" && (
              <button className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-4 py-3 text-sm font-semibold text-accent-green transition hover:bg-accent-green/15" disabled={action === "approve"} onClick={() => void run("approve", () => approveCompendium(compendium.id))}>
                {action === "approve" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Godkjenn sluttproduktet
              </button>
            )}
            {compendium.status === "approved" && (
              <div className="mt-4 rounded-lg border border-accent-green/30 bg-accent-green/10 p-3 text-sm text-accent-green">
                <div className="flex items-center gap-2 font-semibold"><CheckCircle2 className="h-4 w-4" /> Godkjent fagressurs</div>
                <p className="mt-1 text-xs">Versjonen er lagret i biblioteket{compendium.period_ids.length ? " og knyttet til årsplanen" : ""}.</p>
              </div>
            )}
          </section>
        </aside>
      </section>
    </div>
  );
}
