"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, FolderOpen, Loader2, PackagePlus } from "lucide-react";
import { formatProjectDate, listProjects, projectTasks, type Project } from "@/lib/platform-api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    listProjects().then(setProjects).catch((err) => setError(err instanceof Error ? err.message : "Kunne ikke laste prosjekter.")).finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="font-display text-4xl">Prosjekter</h1><p className="mt-2 text-text-secondary">Varige lærerprosjekter på tvers av alle arbeidsflatene.</p></div>
        <Link href="/theme-pack" className="btn-primary"><PackagePlus className="h-4 w-4" /> Ny temapakke</Link>
      </div>
      {loading && <div className="flex items-center gap-2 text-sm text-text-muted"><Loader2 className="h-4 w-4 animate-spin" /> Laster prosjekter …</div>}
      {error && <div role="alert" className="card text-accent-red">{error}</div>}
      {!loading && !error && projects.length === 0 && <div className="card py-12 text-center"><FolderOpen className="mx-auto h-8 w-8 text-text-muted" /><h2 className="mt-3 font-semibold">Ingen prosjekter ennå</h2><p className="mt-1 text-sm text-text-secondary">Start med en temapakke, så lagres planen automatisk her.</p></div>}
      <div className="grid gap-4 md:grid-cols-2">
        {projects.map((project) => (
          <Link key={project.id} href={`/projects/${project.id}`} className="card-interactive block">
            <div className="flex items-start justify-between gap-3"><div><div className="text-xs uppercase tracking-wide text-text-muted">{project.subject || "Prosjekt"} · {project.level}</div><h2 className="mt-1 text-lg font-semibold">{project.title}</h2></div><span className="badge bg-accent-teal/10 text-accent-teal">{project.status}</span></div>
            <p className="mt-3 line-clamp-2 text-sm text-text-secondary">{project.description || project.theme}</p>
            <div className="mt-5 flex items-center justify-between text-xs text-text-muted"><span>{projectTasks(project).length} arbeidsflater</span><span className="inline-flex items-center gap-1">{formatProjectDate(project.updated_at)} <ArrowRight className="h-3.5 w-3.5" /></span></div>
          </Link>
        ))}
      </div>
    </div>
  );
}
