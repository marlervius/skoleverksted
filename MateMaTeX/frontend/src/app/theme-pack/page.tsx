"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, BookOpenText, Calculator, Languages, Loader2, PackageOpen, Sparkles } from "lucide-react";
import { QualityPassport } from "@/components/quality-passport";
import { createThemePack, type ThemePack, type ThemePackInput } from "@/lib/platform-api";

const initialForm: ThemePackInput = {
  title: "",
  theme: "",
  subject: "Naturfag",
  level: "VG1",
  norwegian_level: "B1",
  duration_lessons: 4,
  description: "",
  competency_goals: [],
  include_assessment: true,
  include_teacher_guide: true,
};

const moduleIcon = { fag: BookOpenText, norsk: Languages, matematikk: Calculator };

export default function ThemePackPage() {
  const [form, setForm] = useState(initialForm);
  const [goals, setGoals] = useState("");
  const [pack, setPack] = useState<ThemePack | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setPack(await createThemePack({
        ...form,
        competency_goals: goals.split("\n").map((goal) => goal.trim()).filter(Boolean),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke opprette temapakken.");
    } finally {
      setLoading(false);
    }
  }

  if (pack) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <div className="mb-2 flex items-center gap-2 text-sm text-accent-teal"><PackageOpen className="h-4 w-4" /> Temapakke klar</div>
          <h1 className="font-display text-4xl">{pack.project.title}</h1>
          <p className="mt-2 max-w-3xl text-text-secondary">
            Planen er lagret som ett prosjekt. Åpne delene i ønsket rekkefølge; tema, nivå og prosjekt-ID følger med.
          </p>
        </header>
        <div className="grid gap-4 md:grid-cols-3">
          {pack.tasks.map((task, index) => {
            const Icon = moduleIcon[task.module];
            return (
              <article key={task.id} className="card flex flex-col">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-blue/10 text-accent-blue"><Icon className="h-5 w-5" /></div>
                  <span className="badge bg-surface-elevated text-text-muted">Del {index + 1}</span>
                </div>
                <h2 className="font-semibold">{task.title}</h2>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-text-secondary">{task.brief}</p>
                <Link href={task.href} className="btn-primary mt-5 w-full">Åpne arbeidsflate <ArrowRight className="h-4 w-4" /></Link>
              </article>
            );
          })}
        </div>
        <QualityPassport passport={pack.quality_passport} />
        <div className="flex gap-3">
          <Link href={`/projects/${pack.project.id}`} className="btn-secondary">Se prosjektet</Link>
          <button className="btn-ghost" onClick={() => setPack(null)}>Lag en ny pakke</button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-8 text-center">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-text-secondary"><Sparkles className="h-3.5 w-3.5 text-accent-orange" /> Én idé, tre fagspesialister</div>
        <h1 className="font-display text-4xl">Lag en sammenhengende temapakke</h1>
        <p className="mx-auto mt-3 max-w-2xl text-text-secondary">Planlegg fagtekst, språktilpasning og matematikkoppgaver som ett lærerprosjekt.</p>
      </header>
      <form onSubmit={submit} className="card space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium">Prosjektnavn<input required className="input mt-2" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Klima og bærekraft" /></label>
          <label className="text-sm font-medium">Tema<input required className="input mt-2" value={form.theme} onChange={(e) => setForm({ ...form, theme: e.target.value })} placeholder="Klimaendringer i Norge" /></label>
          <label className="text-sm font-medium">Fagområde<select className="input mt-2" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}><option>Norsk</option><option>Engelsk</option><option>Samfunnsfag</option><option>Naturfag</option><option>Matematikk</option></select></label>
          <label className="text-sm font-medium">Nivå<select className="input mt-2" value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}><option>VG1</option><option>VG2</option><option>VG3</option></select></label>
          <label className="text-sm font-medium">Norsknivå<select className="input mt-2" value={form.norwegian_level} onChange={(e) => setForm({ ...form, norwegian_level: e.target.value })}><option>A2</option><option>B1</option><option>B2</option></select></label>
          <label className="text-sm font-medium">Antall undervisningstimer<input type="number" min={1} max={30} className="input mt-2" value={form.duration_lessons} onChange={(e) => setForm({ ...form, duration_lessons: Number(e.target.value) })} /></label>
        </div>
        <label className="block text-sm font-medium">Ramme og ønsket læringsutbytte<textarea className="input mt-2 min-h-24" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Hva skal elevene sitte igjen med? Hvilke kilder eller vinklinger skal brukes?" /></label>
        <label className="block text-sm font-medium">Kompetansemål, ett per linje<textarea className="input mt-2 min-h-20" value={goals} onChange={(e) => setGoals(e.target.value)} placeholder="Lim inn kode og/eller måltekst" /></label>
        <div className="flex flex-wrap gap-5 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={form.include_teacher_guide} onChange={(e) => setForm({ ...form, include_teacher_guide: e.target.checked })} /> Lærerveiledning</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={form.include_assessment} onChange={(e) => setForm({ ...form, include_assessment: e.target.checked })} /> Fasit og vurderingsgrunnlag</label>
        </div>
        {error && <div role="alert" className="rounded-lg border border-accent-red/30 bg-accent-red/5 p-3 text-sm text-accent-red">{error}</div>}
        <button disabled={loading} className="btn-primary w-full py-3">{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageOpen className="h-4 w-4" />} Opprett temapakke</button>
      </form>
    </div>
  );
}
