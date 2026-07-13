"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpenText, Calculator, Languages, Loader2 } from "lucide-react";
import { formatProjectDate, getProject, listPlatformJobs, projectTasks, type PlatformJob, type Project } from "@/lib/platform-api";

const moduleIcon = { fag: BookOpenText, norsk: Languages, matematikk: Calculator };

export default function ProjectPage({ params }: { params: { id: string } }) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState<PlatformJob[]>([]);
  useEffect(() => {
    Promise.all([getProject(params.id), listPlatformJobs(100, params.id)])
      .then(([loadedProject, loadedJobs]) => { setProject(loadedProject); setJobs(loadedJobs); })
      .catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste prosjektet."));
  }, [params.id]);
  if (error) return <div role="alert" className="card text-accent-red">{error}</div>;
  if (!project) return <div className="flex items-center gap-2 text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster prosjekt …</div>;
  const tasks = projectTasks(project);
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link href="/projects" className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary"><ArrowLeft className="h-4 w-4" /> Alle prosjekter</Link>
      <header><div className="text-xs uppercase tracking-wide text-text-muted">{project.subject} · {project.level} · oppdatert {formatProjectDate(project.updated_at)}</div><h1 className="mt-2 font-display text-4xl">{project.title}</h1><p className="mt-3 max-w-3xl text-text-secondary">{project.description || project.theme}</p></header>
      {project.competency_goals.length > 0 && <section className="card"><h2 className="font-semibold">Kompetansemål</h2><ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-text-secondary">{project.competency_goals.map((goal) => <li key={goal}>{goal}</li>)}</ul></section>}
      <div className="grid gap-4 md:grid-cols-3">
        {tasks.map((task) => { const Icon = moduleIcon[task.module]; const job = jobs.find((item) => item.module === task.module); return <article key={task.id} className="card flex flex-col"><div className="flex items-center justify-between"><Icon className="h-5 w-5 text-accent-blue" />{job && <span className="badge bg-accent-teal/10 text-accent-teal">{job.status} · {job.progress}%</span>}</div><h2 className="mt-4 font-semibold">{task.title}</h2><p className="mt-2 flex-1 text-sm text-text-secondary">{task.brief}</p>{typeof job?.quality_passport?.score === "number" && <p className="mt-3 text-xs text-text-muted">Kvalitet {job.quality_passport.score}/100</p>}<Link className="btn-secondary mt-5" href={task.href}>Åpne <ArrowRight className="h-4 w-4" /></Link></article>; })}
      </div>
    </div>
  );
}
