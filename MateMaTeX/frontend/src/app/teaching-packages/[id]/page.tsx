"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Download, FileText, Loader2, RefreshCw, Save, ShieldCheck, XCircle } from "lucide-react";
import {
  approveTeachingArtifact,
  approveTeachingPackage,
  generateTeachingPackage,
  getTeachingPackage,
  regenerateTeachingArtifact,
  teachingArtifactDownloadUrl,
  teachingPackageZipDownloadUrl,
  updateTeachingArtifact,
  verifyTeachingArtifact,
  type TeachingArtifact,
  type TeachingArtifactStatus,
  type TeachingPackage,
} from "@/lib/platform-api";

const statusLabels: Record<TeachingArtifactStatus | string, string> = {
  planned: "Ikke startet",
  generating: "Arbeider …",
  generated: "Utkast klart",
  needs_review: "Krever lærerreview",
  needs_revision: "Må revideres",
  reviewed_with_issues: "Gjennomgått med åpne problemer",
  approved: "Godkjent",
  generation_incomplete: "Genereringen ble ikke ferdig",
  parse_failure: "Kunne ikke lese resultatet",
  language_quality_failed: "Språkkontroll blokkerte",
  source_grounding_failed: "Kildesjekken blokkerte",
  verification_failed: "Faktapasset feilet",
  superseded: "Foreldet av nyere redigering",
  cancelled: "Avbrutt",
};

const typeLabels: Record<string, string> = {
  presentation: "PowerPoint-presentasjon",
  student_sheet: "Læringsark og elevtekst",
  exercise_sheet: "Oppgaveark",
  answer_key: "Fasit",
  teacher_guide: "Lærerveiledning",
};

function artifactReasons(artifact: TeachingArtifact): string[] {
  const reasons: string[] = [];
  if (!artifact.content_markdown.trim()) reasons.push("innhold mangler");
  if (!artifact.truth_passport) reasons.push("faktapass mangler");
  else if (artifact.truth_passport.status !== "verified") reasons.push("faktapasset er ikke grønt");
  else if (artifact.truth_passport.content_revision !== artifact.content_revision) reasons.push("faktapasset gjelder eldre tekst");
  if (!artifact.quality_passport) reasons.push("kvalitetspass mangler");
  else if (artifact.quality_passport.overall_status === "failed") reasons.push("kvalitetspass har blokkert kontroll");
  if (artifact.source_quality_notes.length) reasons.push("kildesjekken har merknader");
  if (!artifact.files.length) reasons.push("fil mangler");
  if (artifact.status === "generating") reasons.push("generering pågår");
  if (artifact.status !== "approved") reasons.push("artefaktet er ikke lærer-godkjent");
  return reasons;
}

export default function TeachingPackagePage({ params }: { params: { id: string } }) {
  const [pkg, setPkg] = useState<TeachingPackage | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState("");
  const [teacher, setTeacher] = useState("local-teacher");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const loaded = await getTeachingPackage(params.id);
    setPkg(loaded);
    setSelectedId((current) => current || loaded.artifacts[0]?.id || "");
    const selected = loaded.artifacts.find((artifact) => artifact.id === selectedId) || loaded.artifacts[0];
    if (selected && !draft) setDraft(selected.content_markdown);
  }

  useEffect(() => {
    getTeachingPackage(params.id)
      .then((loaded) => {
        setPkg(loaded);
        setSelectedId(loaded.artifacts[0]?.id || "");
        setDraft(loaded.artifacts[0]?.content_markdown || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste pakken."))
      .finally(() => setLoading(false));
  }, [params.id]);

  useEffect(() => {
    if (!pkg) return;
    const active = pkg.status === "planning" || pkg.status === "generating" || pkg.artifacts.some((artifact) => artifact.status === "generating");
    if (!active) return;
    const timer = window.setTimeout(() => { void refresh().catch(() => undefined); }, 1600);
    return () => window.clearTimeout(timer);
  }, [pkg]);

  const selected = useMemo(() => pkg?.artifacts.find((artifact) => artifact.id === selectedId) || pkg?.artifacts[0] || null, [pkg, selectedId]);
  const packageReasons = useMemo(() => {
    if (!pkg) return [];
    return pkg.artifacts.filter((artifact) => artifact.required).flatMap((artifact) => artifactReasons(artifact).map((reason) => `${artifact.title}: ${reason}`));
  }, [pkg]);

  async function action(label: string, work: () => Promise<TeachingPackage>) {
    setBusy(label);
    setError("");
    try { setPkg(await work()); } catch (err) { setError(err instanceof Error ? err.message : "Handlingen kunne ikke fullføres."); } finally { setBusy(""); }
  }

  async function saveDraft() {
    if (!pkg || !selected) return;
    await action("save", async () => {
      const updated = await updateTeachingArtifact(pkg.id, selected.id, draft);
      setDraft(updated.artifacts.find((artifact) => artifact.id === selected.id)?.content_markdown || draft);
      return updated;
    });
  }

  function choose(id: string) {
    const artifact = pkg?.artifacts.find((item) => item.id === id);
    setSelectedId(id);
    setDraft(artifact?.content_markdown || "");
  }

  if (loading) return <div className="flex items-center gap-2 py-12 text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster undervisningspakken …</div>;
  if (!pkg) return <div role="alert" className="card text-accent-red">{error || "Pakken finnes ikke."}</div>;

  const anyActive = pkg.status === "planning" || pkg.status === "generating" || pkg.artifacts.some((artifact) => artifact.status === "generating");
  const approvedCount = pkg.artifacts.filter((artifact) => artifact.status === "approved").length;
  return (
    <main className="mx-auto max-w-7xl space-y-6">
      <Link href={`/year-plans/${pkg.year_plan_id}`} className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"><ArrowLeft className="h-4 w-4" /> Tilbake til årsplanen</Link>
      <header className="rounded-2xl border border-border bg-surface p-6 shadow-soft-sm">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div><p className="text-xs font-medium uppercase tracking-wide text-text-muted">{pkg.subject} · {pkg.level} · {pkg.plan.period_title}</p><h1 className="mt-1 font-display text-3xl tracking-tight">{pkg.title}</h1><p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary">{pkg.plan.overview || "Pakken bygger på den frosne perioden og kan redigeres før godkjenning."}</p></div>
          <div className="flex flex-wrap items-center gap-2"><span className="badge bg-accent-blue/10 text-accent-blue">{statusLabels[pkg.status] || pkg.status}</span><span className="text-xs text-text-muted">Pakkerevisjon {pkg.package_revision}</span></div>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          {pkg.status === "draft" || pkg.status === "needs_revision" || pkg.status === "needs_review" ? <button className="btn-primary" onClick={() => void action("generate", async () => { await generateTeachingPackage(pkg.id); return getTeachingPackage(pkg.id); })} disabled={anyActive || busy !== ""}><RefreshCw className="h-4 w-4" /> Start generering</button> : null}
          <button className="btn-secondary" onClick={() => void refresh()} disabled={busy !== ""}><RefreshCw className="h-4 w-4" /> Oppdater status</button>
          <label className="ml-auto flex items-center gap-2 text-xs text-text-muted">Godkjenner<input className="input !w-44 !py-1.5" value={teacher} onChange={(event) => setTeacher(event.target.value)} /></label>
        </div>
        {anyActive && <p className="mt-3 rounded-lg bg-accent-blue/5 px-3 py-2 text-xs text-text-secondary">Genereringen fortsetter på serveren. Du kan lukke siden og finne igjen statusen senere.</p>}
      </header>

      {error && <div role="alert" className="card border-accent-red/30 text-sm text-accent-red">{error}</div>}

      <section className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-3">
          <div className="card"><h2 className="font-semibold">Artefakter</h2><p className="mt-1 text-xs text-text-muted">{approvedCount}/{pkg.artifacts.length} godkjent</p><div className="mt-4 space-y-2">{pkg.artifacts.map((artifact) => <button key={artifact.id} className={`w-full rounded-lg border px-3 py-3 text-left ${selected?.id === artifact.id ? "border-accent-blue bg-accent-blue/5" : "border-border"}`} onClick={() => choose(artifact.id)}><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{typeLabels[artifact.artifact_type]}</span><span className={`h-2 w-2 rounded-full ${artifact.status === "approved" ? "bg-accent-green" : artifact.status === "generating" ? "animate-pulse bg-accent-blue" : "bg-accent-orange"}`} /></div><div className="mt-1 text-xs text-text-muted">{statusLabels[artifact.status] || artifact.status}</div>{artifact.artifact_job_id && <div className="mt-1 truncate text-[10px] text-text-muted">Jobb: {artifact.artifact_job_id}</div>}</button>)}</div></div>
          <div className="card"><h2 className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4 text-accent-blue" /> Kvalitetsport</h2><p className="mt-2 text-xs leading-relaxed text-text-secondary">Grønt faktapass gjelder nøyaktig tekst- og pakkerevisjon. Åpne problemer må håndteres av læreren.</p>{pkg.sources.length === 0 && <p className="mt-3 rounded-lg bg-accent-orange/10 p-3 text-xs text-text-secondary">Ingen konkrete kilder er registrert. Godkjenning vil bli blokkert til faktagrunnlaget er på plass.</p>}</div>
        </aside>

        {selected && <article className="card space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-text-muted">{typeLabels[selected.artifact_type]}</p><h2 className="mt-1 text-xl font-semibold">{selected.title}</h2><p className="mt-1 text-xs text-text-muted">Status: {statusLabels[selected.status] || selected.status} · innholdsrevisjon {selected.content_revision.slice(0, 12)}</p></div><div className="flex flex-wrap gap-2">{selected.files.map((file) => <a key={file.format} href={teachingArtifactDownloadUrl(pkg.id, selected.id, file.format)} className={`btn-ghost !px-2.5 !py-1.5 ${pkg.status !== "approved" ? "pointer-events-none opacity-40" : ""}`}><Download className="h-4 w-4" /> {file.format.toUpperCase()}</a>)}</div></div>
          <div className="rounded-xl border border-border bg-bg/40 p-4"><textarea className="min-h-[28rem] w-full resize-y border-0 bg-transparent p-0 text-sm leading-6 outline-none" value={draft} onChange={(event) => setDraft(event.target.value)} aria-label={`Rediger ${selected.title}`} /><div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3"><button className="btn-secondary" onClick={() => void saveDraft()} disabled={busy !== "" || selected.status === "generating"}><Save className="h-4 w-4" /> Lagre redigering</button><button className="btn-secondary" onClick={() => void action("verify", async () => { await verifyTeachingArtifact(pkg.id, selected.id); return getTeachingPackage(pkg.id); })} disabled={busy !== "" || !selected.content_markdown.trim() || selected.status === "generating"}><ShieldCheck className="h-4 w-4" /> Kjør faktapass</button><button className="btn-secondary" onClick={() => void action("retry", async () => { await regenerateTeachingArtifact(pkg.id, selected.id); return getTeachingPackage(pkg.id); })} disabled={busy !== "" || selected.status === "generating"}><RefreshCw className="h-4 w-4" /> Prøv artefakt på nytt</button></div></div>
          <div className="grid gap-4 md:grid-cols-2"><div className="rounded-xl border border-border p-4"><h3 className="font-semibold">Faktapass</h3>{selected.truth_passport ? <><p className={`mt-2 text-sm ${selected.truth_passport.status === "verified" && selected.truth_passport.content_revision === selected.content_revision ? "text-accent-green" : "text-accent-orange"}`}>{selected.truth_passport.verified_claims} av {selected.truth_passport.total_claims} påstander verifisert · {selected.truth_passport.status}</p><ul className="mt-2 space-y-1 text-xs text-text-secondary">{selected.truth_passport.limitations.slice(0, 4).map((item) => <li key={item}>• {item}</li>)}</ul></> : <p className="mt-2 text-sm text-accent-orange">Faktapasset er ikke kjørt for denne teksten.</p>}</div><div className="rounded-xl border border-border p-4"><h3 className="font-semibold">Neste handling</h3>{artifactReasons(selected).length ? <ul className="mt-2 space-y-1 text-xs text-text-secondary">{artifactReasons(selected).slice(0, 6).map((reason) => <li key={reason} className="flex gap-2"><XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-orange" />{reason}</li>)}</ul> : <p className="mt-2 text-sm text-accent-green">Artefaktet oppfyller maskinporten og kan godkjennes av læreren.</p>}{selected.source_quality_notes.length > 0 && <p className="mt-3 text-xs text-accent-orange">Kildesjekk: {selected.source_quality_notes.join("; ")}</p>}</div></div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"><button className="btn-primary" onClick={() => void action("approve-artifact", () => approveTeachingArtifact(pkg.id, selected.id, teacher))} disabled={busy !== "" || artifactReasons(selected).length > 0 || selected.status === "approved"}><CheckCircle2 className="h-4 w-4" /> Godkjenn artefakt</button><span className="text-xs text-text-muted">Godkjenning registreres med lærer, tidspunkt, revisjon og digest.</span></div>
        </article>}
      </section>

      <section className="card flex flex-wrap items-center justify-between gap-4 border-accent-blue/30"><div><h2 className="text-lg font-semibold">Godkjenn hele pakken</h2><p className="mt-1 text-sm text-text-secondary">Alle obligatoriske artefakter må være godkjent på samme pakkerevisjon før de projiseres til årsplanen.</p>{packageReasons.length > 0 && <p className="mt-2 text-xs text-accent-orange">Åpne krav: {packageReasons.slice(0, 4).join(" · ")}</p>}</div><div className="flex flex-wrap gap-2"><button className="btn-primary" onClick={() => void action("approve-package", () => approveTeachingPackage(pkg.id, teacher))} disabled={busy !== "" || packageReasons.length > 0 || pkg.status === "approved"}><CheckCircle2 className="h-4 w-4" /> Godkjenn og legg i årsplanen</button>{pkg.status === "approved" && <a className="btn-secondary" href={teachingPackageZipDownloadUrl(pkg.id)}><Download className="h-4 w-4" /> Last ned ZIP</a>}</div></section>
    </main>
  );
}
