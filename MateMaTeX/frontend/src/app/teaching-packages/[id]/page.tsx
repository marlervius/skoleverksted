"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Loader2,
  Pencil,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  approveTeachingArtifact,
  approveTeachingPackage,
  approveTeachingPackageWithOmissions,
  generateTeachingPackage,
  getTeachingPackage,
  regenerateTeachingArtifact,
  removeTeachingClaim,
  repairTeachingArtifact,
  teachingArtifactDownloadUrl,
  teachingPackageZipDownloadUrl,
  updateTeachingArtifact,
  updateTeachingPackage,
  verifyTeachingArtifact,
  type TeachingArtifact,
  type TeachingPackage,
} from "@/lib/platform-api";

const statusLabels: Record<string, string> = {
  draft: "Ikke startet",
  planning: "Planlegger",
  generating: "AI-crewet arbeider",
  generated: "Utkast klart",
  needs_review: "Krever lærervurdering",
  needs_revision: "Krever ny kontroll",
  reviewed_with_issues: "Gjennomgått med åpne problemer",
  approved: "Godkjent av lærer",
  user_approved_with_exceptions: "Godkjent med eget ansvar",
  generation_incomplete: "Genereringen ble ikke ferdig",
  parse_failure: "Kunne ikke lese resultatet",
  language_quality_failed: "Språkkontroll krever vurdering",
  source_grounding_failed: "Krever lærervurdering",
  source_unavailable: "Krever lærervurdering",
  verification_failed: "Kontrollen kunne ikke fullføres",
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

function unresolvedClaims(artifact: TeachingArtifact) {
  return artifact.truth_passport?.claims.filter((claim) => claim.status !== "verified") || [];
}

function artifactMachineReasons(artifact: TeachingArtifact): string[] {
  const reasons: string[] = [];
  if (!artifact.content_markdown.trim()) reasons.push("innhold mangler");
  if (!artifact.truth_passport) reasons.push("faktapass mangler");
  else if (artifact.truth_passport.status !== "verified") reasons.push("faktapasset er ikke grønt");
  else if (artifact.truth_passport.content_revision !== artifact.content_revision) reasons.push("faktapasset gjelder eldre tekst");
  if (unresolvedClaims(artifact).length) reasons.push(`${unresolvedClaims(artifact).length} påstand(er) krever lærervurdering`);
  if (!artifact.quality_passport) reasons.push("kvalitetspass mangler");
  else if (artifact.quality_passport.overall_status === "failed") reasons.push("kvalitetspass har blokkert kontroll");
  if (artifact.source_quality_notes.length) reasons.push("kildesjekken har merknader");
  if (!artifact.files.length) reasons.push("fil mangler");
  if (artifact.status === "generating") reasons.push("generering pågår");
  return reasons;
}

function artifactReasons(artifact: TeachingArtifact): string[] {
  const reasons = artifactMachineReasons(artifact);
  if (artifact.status !== "approved") reasons.push("artefaktet er ikke lærer-godkjent");
  return reasons;
}

function sourceAttemptLabel(status: string): string {
  if (status === "supported") return "støtter påstanden";
  if (status === "unavailable") return "kunne ikke åpnes";
  return "støtter ikke påstanden";
}

export default function TeachingPackagePage({ params }: { params: { id: string } }) {
  const [pkg, setPkg] = useState<TeachingPackage | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState("");
  const [teacher, setTeacher] = useState("local-teacher");
  const [exceptionReason, setExceptionReason] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const selected = useMemo(
    () => pkg?.artifacts.find((artifact) => artifact.id === selectedId) || pkg?.artifacts[0] || null,
    [pkg, selectedId],
  );

  async function refresh() {
    const loaded = await getTeachingPackage(params.id);
    setPkg(loaded);
    const nextId = selectedId || loaded.artifacts[0]?.id || "";
    setSelectedId(nextId);
    const next = loaded.artifacts.find((artifact) => artifact.id === nextId) || loaded.artifacts[0];
    if (next && !editing) setDraft(next.content_markdown);
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

  const packageReasons = useMemo(() => {
    if (!pkg) return [];
    return pkg.artifacts
      .filter((artifact) => artifact.required)
      .flatMap((artifact) => artifactReasons(artifact).map((reason) => `${artifact.title}: ${reason}`));
  }, [pkg]);

  async function action(label: string, work: () => Promise<TeachingPackage>) {
    setBusy(label);
    setError("");
    try {
      setPkg(await work());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Handlingen kunne ikke fullføres.");
    } finally {
      setBusy("");
    }
  }

  async function saveDraft() {
    if (!pkg || !selected) return;
    await action("save", async () => {
      const updated = await updateTeachingArtifact(pkg.id, selected.id, draft);
      setEditing(false);
      setDraft(updated.artifacts.find((artifact) => artifact.id === selected.id)?.content_markdown || draft);
      return updated;
    });
  }

  async function runVerification(label: string, work: () => Promise<unknown>) {
    if (!pkg || !selected) return;
    setBusy(label);
    setError("");
    try {
      await work();
      setPkg(await getTeachingPackage(pkg.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kontrollen kunne ikke startes.");
    } finally {
      setBusy("");
    }
  }

  async function addSourceAndVerify() {
    if (!pkg || !selected || !sourceUrl.trim()) return;
    setBusy("source");
    setError("");
    try {
      const source = {
        title: sourceTitle.trim() || sourceUrl.trim(), url: sourceUrl.trim(), publisher: "",
        source_tier: "other" as const, published_at: "", retrieved_at: new Date().toISOString(),
        origin: "teacher" as const, fetch_status: "provided" as const,
      };
      const updated = await updateTeachingPackage(pkg.id, { sources: [...pkg.sources, source] });
      await verifyTeachingArtifact(updated.id, selected.id);
      setPkg(await getTeachingPackage(updated.id));
      setSourceUrl("");
      setSourceTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kilden kunne ikke legges til.");
    } finally {
      setBusy("");
    }
  }

  function choose(id: string) {
    const artifact = pkg?.artifacts.find((item) => item.id === id);
    setSelectedId(id);
    setEditing(false);
    setDraft(artifact?.content_markdown || "");
  }

  if (loading) return <div className="flex items-center gap-2 py-12 text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster undervisningspakken …</div>;
  if (!pkg) return <div role="alert" className="card text-accent-red">{error || "Pakken finnes ikke."}</div>;

  const anyActive = pkg.status === "planning" || pkg.status === "generating" || pkg.artifacts.some((artifact) => artifact.status === "generating");
  const approvedCount = pkg.artifacts.filter((artifact) => artifact.status === "approved").length;
  const unresolvedCount = pkg.artifacts.reduce((sum, artifact) => sum + unresolvedClaims(artifact).length, 0);
  const quarantinedCount = pkg.artifacts.reduce((sum, artifact) => sum + artifact.quarantine.filter((item) => item.status === "withheld").length, 0);
  const latestRound = selected?.quality_rounds[selected.quality_rounds.length - 1];
  const finalApproved = pkg.status === "approved" || pkg.status === "user_approved_with_exceptions";

  return (
    <main className="mx-auto max-w-7xl space-y-6">
      <Link href={`/year-plans/${pkg.year_plan_id}`} className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"><ArrowLeft className="h-4 w-4" /> Tilbake til årsplanen</Link>
      <header className="rounded-2xl border border-border bg-surface p-6 shadow-soft-sm">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div><p className="text-xs font-medium uppercase tracking-wide text-text-muted">{pkg.subject} · {pkg.level} · {pkg.plan.period_title}</p><h1 className="mt-1 font-display text-3xl tracking-tight">{pkg.title}</h1><p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary">{pkg.plan.overview || "Pakken bygger på den frosne perioden og kan redigeres før godkjenning."}</p></div>
          <div className="flex flex-wrap items-center gap-2"><span className="badge bg-accent-blue/10 text-accent-blue">{statusLabels[pkg.status] || pkg.status}</span><span className="text-xs text-text-muted">Pakkerevisjon {pkg.package_revision}</span></div>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          {(pkg.status === "draft" || pkg.status === "needs_revision" || pkg.status === "needs_review") && <button className="btn-primary" onClick={() => void action("generate", async () => { await generateTeachingPackage(pkg.id); return getTeachingPackage(pkg.id); })} disabled={anyActive || busy !== ""}><RefreshCw className="h-4 w-4" /> Start generering</button>}
          <button className="btn-secondary" onClick={() => void refresh()} disabled={busy !== ""}><RefreshCw className="h-4 w-4" /> Oppdater status</button>
          <label className="ml-auto flex items-center gap-2 text-xs text-text-muted">Godkjenner<input className="input !w-44 !py-1.5" value={teacher} onChange={(event) => setTeacher(event.target.value)} /></label>
        </div>
        {anyActive && <p className="mt-3 rounded-lg bg-accent-blue/5 px-3 py-2 text-xs text-text-secondary">AI-crewet arbeider videre på serveren. Status, kontrollrunde og påstandstall oppdateres automatisk.</p>}
      </header>

      {error && <div role="alert" className="card border-accent-red/30 text-sm text-accent-red">{error}</div>}

      <section className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-3">
          <div className="card"><h2 className="font-semibold">Artefakter</h2><p className="mt-1 text-xs text-text-muted">{approvedCount}/{pkg.artifacts.length} lærer-godkjent</p><div className="mt-4 space-y-2">{pkg.artifacts.map((artifact) => <button key={artifact.id} className={`w-full rounded-lg border px-3 py-3 text-left ${selected?.id === artifact.id ? "border-accent-blue bg-accent-blue/5" : "border-border"}`} onClick={() => choose(artifact.id)}><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{typeLabels[artifact.artifact_type]}</span><span className={`h-2 w-2 rounded-full ${artifact.status === "approved" ? "bg-accent-green" : artifact.status === "generating" ? "animate-pulse bg-accent-blue" : "bg-accent-orange"}`} /></div><div className="mt-1 text-xs text-text-muted">{statusLabels[artifact.status] || artifact.status}</div>{artifact.artifact_job_id && <div className="mt-1 truncate text-[10px] text-text-muted">Jobb: {artifact.artifact_job_id}</div>}</button>)}</div></div>
          <div className="card"><h2 className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4 text-accent-blue" /> Kvalitetsport</h2><p className="mt-2 text-xs leading-relaxed text-text-secondary">Kildegodkjent og lærer-godkjent er separate beslutninger. Legg til en kilde og kjør valgt artefakt gjennom hele kontrollen på nytt.</p>{pkg.sources.length === 0 && <p className="mt-3 rounded-lg bg-accent-orange/10 p-3 text-xs text-text-secondary">Ingen konkrete kilder er registrert. Faktapasset vil vise hvilke påstander læreren må vurdere.</p>}<div className="mt-3 space-y-2"><input className="input !py-1.5 text-xs" value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} placeholder="Kildetittel" /><input className="input !py-1.5 text-xs" type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://…" /><button className="btn-secondary w-full !py-1.5 text-xs" onClick={() => void addSourceAndVerify()} disabled={busy !== "" || !sourceUrl.trim()}>Legg til kilde og kontroller valgt</button></div></div>
        </aside>

        {selected && <article className="card space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-text-muted">{typeLabels[selected.artifact_type]}</p><h2 className="mt-1 text-xl font-semibold">{selected.title}</h2><p className="mt-1 text-xs text-text-muted">Status: {statusLabels[selected.status] || selected.status} · innholdsrevisjon {selected.content_revision.slice(0, 12)}</p></div><div className="flex flex-wrap gap-2">{selected.files.map((file) => <a key={file.format} href={teachingArtifactDownloadUrl(pkg.id, selected.id, file.format)} className={`btn-ghost !px-2.5 !py-1.5 ${finalApproved ? "" : "pointer-events-none opacity-40"}`}><Download className="h-4 w-4" /> {file.format.toUpperCase()}</a>)}</div></div>

          <section className="rounded-xl border border-border bg-bg/40 p-4"><div className="grid gap-3 sm:grid-cols-4"><Metric label="Kildegodkjent" value={`${selected.truth_passport?.verified_claims || 0}/${selected.truth_passport?.total_claims || 0}`} /><Metric label="Automatisk rettet" value={String(selected.quality_rounds.reduce((sum, round) => sum + round.corrected_count, 0))} /><Metric label="Krever lærervurdering" value={String(unresolvedClaims(selected).length + selected.quarantine.filter((item) => item.status === "withheld").length)} /><Metric label="Kontrollrunder" value={String(selected.quality_run_count || selected.quality_rounds.length)} /></div>{latestRound && <p className="mt-3 text-xs text-text-secondary">Siste runde {latestRound.round_number}: {latestRound.summary || "Kontroll gjennomført."} · {latestRound.changed ? "målbar endring registrert" : "ingen endring registrert"}</p>}{selected.quality_stop_reason && <p className="mt-1 text-xs text-accent-orange">Kontrollen stoppet: {selected.quality_stop_reason}</p>}</section>

          <div className="rounded-xl border border-border bg-bg/40 p-4"><textarea className="min-h-[24rem] w-full resize-y border-0 bg-transparent p-0 text-sm leading-6 outline-none" value={draft} onChange={(event) => { setDraft(event.target.value); setEditing(true); }} aria-label={`Rediger ${selected.title}`} /><div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3"><button className="btn-secondary" onClick={() => void saveDraft()} disabled={busy !== "" || selected.status === "generating" || !editing}><Save className="h-4 w-4" /> Lagre redigering</button><button className="btn-secondary" onClick={() => void runVerification("verify", () => verifyTeachingArtifact(pkg.id, selected.id))} disabled={busy !== "" || !selected.content_markdown.trim() || selected.status === "generating"}><ShieldCheck className="h-4 w-4" /> Kjør faktasjekk på nytt</button><button className="btn-primary" onClick={() => void runVerification("repair", () => repairTeachingArtifact(pkg.id, selected.id))} disabled={busy !== "" || !selected.content_markdown.trim() || selected.status === "generating"}><Sparkles className="h-4 w-4" /> La AI rette og kildekontrollere</button><button className="btn-secondary" onClick={() => void action("retry", async () => { await regenerateTeachingArtifact(pkg.id, selected.id); return getTeachingPackage(pkg.id); })} disabled={busy !== "" || selected.status === "generating"}><RefreshCw className="h-4 w-4" /> Prøv artefakt på nytt</button></div></div>

          {unresolvedClaims(selected).length > 0 && <section className="rounded-xl border border-accent-orange/30 bg-accent-orange/5 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Uløste påstander – krever lærervurdering</h3><p className="mt-1 text-xs text-text-secondary">AI-crewet fant ikke nok dokumentasjon. Dette er ikke kildegodkjent, men du kan redigere, fjerne eller kontrollere hver påstand.</p></div><span className="badge bg-accent-orange/15 text-accent-orange">{unresolvedClaims(selected).length} åpne</span></div><div className="mt-3 space-y-3">{unresolvedClaims(selected).map((claim) => <article key={claim.id} className="rounded-lg border border-border bg-surface p-3"><p className="text-xs font-medium">{claim.location || "Ukjent seksjon"} · {claim.content_type}</p><p className="mt-1 text-sm font-medium">{claim.claim}</p><p className="mt-2 text-xs text-text-secondary"><span className="font-semibold">Hvorfor:</span> {claim.evidence || "Ingen dokumentert støtte ble funnet."}</p>{claim.source_attempts.length > 0 && <details className="mt-2 text-xs text-text-secondary"><summary>Kildeforsøk ({claim.source_attempts.length})</summary><ul className="mt-1 space-y-1">{claim.source_attempts.map((attempt, index) => <li key={`${attempt.url}-${index}`}>{attempt.title || "Uten tittel"}: {sourceAttemptLabel(attempt.status)}{attempt.url ? ` · ${attempt.url}` : ""}{attempt.evidence ? ` · ${attempt.evidence}` : ""}</li>)}</ul></details>}{claim.replacement && <p className="mt-2 text-xs text-text-secondary"><span className="font-semibold">AI-forslag:</span> {claim.replacement}</p>}<div className="mt-3 flex flex-wrap gap-2"><button className="btn-secondary !px-2.5 !py-1.5" onClick={() => { setEditing(true); setDraft(selected.content_markdown); }}><Pencil className="h-3.5 w-3.5" /> Rediger</button><button className="btn-secondary !px-2.5 !py-1.5" onClick={() => void runVerification("remove", () => removeTeachingClaim(pkg.id, selected.id, claim.id))} disabled={busy !== ""}><Trash2 className="h-3.5 w-3.5" /> Fjern påstand</button><button className="btn-secondary !px-2.5 !py-1.5" onClick={() => void runVerification("verify-claim", () => verifyTeachingArtifact(pkg.id, selected.id))} disabled={busy !== ""}><RefreshCw className="h-3.5 w-3.5" /> Kontroller på nytt</button></div></article>)}</div></section>}

          {selected.quarantine.filter((item) => item.status === "withheld").length > 0 && <section className="rounded-xl border border-accent-orange/30 bg-accent-orange/5 p-4"><h3 className="font-semibold">Utelatt fra eksport</h3><p className="mt-1 text-xs text-text-secondary">Disse påstandene er tatt ut av den kontrollerte teksten og beholdes her for sporbarhet.</p><div className="mt-3 space-y-3">{selected.quarantine.filter((item) => item.status === "withheld").map((item) => <article key={item.id} className="rounded-lg border border-border bg-surface p-3"><p className="text-xs font-medium">{item.location} · {item.content_type}</p><p className="mt-1 text-sm">{item.original_text}</p><p className="mt-2 text-xs text-text-secondary">Hvorfor: {item.reason}</p>{item.suggested_replacement && <p className="mt-1 text-xs text-text-secondary">AI-forslag: {item.suggested_replacement}</p>}<p className="mt-1 text-xs font-medium text-accent-orange">{item.omission_consequence}</p>{item.source_attempts.length > 0 && <details className="mt-2 text-xs text-text-secondary"><summary>Kildeforsøk ({item.source_attempts.length})</summary><ul className="mt-1 space-y-1">{item.source_attempts.map((attempt, index) => <li key={`${attempt.url}-${index}`}>{attempt.title || "Uten tittel"}: {sourceAttemptLabel(attempt.status)}{attempt.url ? ` · ${attempt.url}` : ""}</li>)}</ul></details>}</article>)}</div></section>}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"><button className="btn-primary" onClick={() => void action("approve-artifact", () => approveTeachingArtifact(pkg.id, selected.id, teacher))} disabled={busy !== "" || artifactMachineReasons(selected).length > 0 || selected.status === "approved"}><CheckCircle2 className="h-4 w-4" /> {selected.artifact_type === "presentation" ? "Godkjenn presentasjonen" : "Godkjenn artefakt"}</button><span className="text-xs text-text-muted">Kildegodkjenning og lærerens beslutning logges separat.</span></div>
        </article>}
      </section>

      <section className="card flex flex-wrap items-center justify-between gap-4 border-accent-blue/30"><div><h2 className="text-lg font-semibold">Godkjenn hele pakken</h2><p className="mt-1 text-sm text-text-secondary">Alle obligatoriske artefakter må være kildekontrollert og lærer-godkjent på samme revisjon. Uløste punkter kan bare eksporteres etter tydelig ansvarsovertakelse.</p>{packageReasons.length > 0 && <p className="mt-2 text-xs text-accent-orange">Åpne krav: {packageReasons.slice(0, 5).join(" · ")}</p>}{(unresolvedCount + quarantinedCount) > 0 && <p className="mt-2 text-xs text-accent-orange">{unresolvedCount + quarantinedCount} punkt(er) krever lærervurdering eller er utelatt fra eksport.</p>}{pkg.approval_history?.length > 0 && <p className="mt-2 text-xs text-text-muted">Siste beslutning: {statusLabels[pkg.approval_history[pkg.approval_history.length - 1].action] || pkg.approval_history[pkg.approval_history.length - 1].action} · {pkg.approval_history[pkg.approval_history.length - 1].reason}</p>}{(unresolvedCount + quarantinedCount) > 0 && !finalApproved && <div className="mt-3 w-full rounded-lg border border-accent-orange/30 bg-accent-orange/5 p-3"><p className="text-xs font-semibold text-accent-orange">Uløste punkter følger med i kontrollrapporten. Ved ansvarsgodkjenning tar du ansvar for at de utelates eller brukes.</p><textarea className="mt-2 min-h-20 w-full rounded-lg border border-border bg-surface p-2 text-sm" value={exceptionReason} onChange={(event) => setExceptionReason(event.target.value)} placeholder="Skriv hvorfor du tar ansvar for å bruke pakken …" aria-label="Begrunnelse for ansvarsgodkjenning" /></div>}</div><div className="flex flex-wrap gap-2"><button className="btn-primary" onClick={() => void action("approve-package", () => approveTeachingPackage(pkg.id, teacher))} disabled={busy !== "" || packageReasons.length > 0 || unresolvedCount + quarantinedCount > 0 || finalApproved}><CheckCircle2 className="h-4 w-4" /> Godkjenn og legg i årsplanen</button>{(unresolvedCount + quarantinedCount) > 0 && !finalApproved && <button className="btn-secondary" onClick={() => void action("approve-exceptions", () => approveTeachingPackageWithOmissions(pkg.id, teacher, exceptionReason.trim()))} disabled={busy !== "" || !exceptionReason.trim()}><ShieldCheck className="h-4 w-4" /> Godkjenn med eget ansvar</button>}{finalApproved && <a className="btn-secondary" href={teachingPackageZipDownloadUrl(pkg.id)}><Download className="h-4 w-4" /> Last ned ZIP</a>}</div></section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border bg-surface p-3"><p className="text-xs text-text-muted">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></div>;
}
