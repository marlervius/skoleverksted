"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, Sparkles, Star, Trash2, Copy, FolderOpen } from "lucide-react";
import { listHistory, removeHistoryEntry, updateHistoryFavorite, type HistoryEntry } from "@/lib/generation-history";
import { warningReasonLabel } from "@/lib/map-api-result";
import { useAppStore } from "@/lib/store";
import { getResult } from "@/lib/api";
import { mapApiResultToGenerationResult } from "@/lib/map-api-result";
import { listPlatformJobs, type PlatformJob } from "@/lib/platform-api";

export default function HistoryPage() {
  const router = useRouter();
  const setRequest = useAppStore((s) => s.setRequest);
  const setResult = useAppStore((s) => s.setResult);
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [openError, setOpenError] = useState("");
  const [platformJobs, setPlatformJobs] = useState<PlatformJob[]>([]);

  useEffect(() => {
    setEntries(listHistory());
    listPlatformJobs().then(setPlatformJobs).catch(() => undefined);
  }, []);

  const refresh = () => setEntries(listHistory());

  const openJob = async (entry: HistoryEntry) => {
    setOpeningId(entry.jobId);
    setOpenError("");
    try {
      const raw = await getResult(entry.jobId);
      const mapped = mapApiResultToGenerationResult(raw, entry.request);
      setRequest({ ...entry.request });
      setResult(mapped);
      router.push("/matematikk");
    } catch (e: unknown) {
      setOpenError(
        e instanceof Error ? e.message : "Kunne ikke åpne jobben — den kan være utløpt."
      );
    } finally {
      setOpeningId(null);
    }
  };

  if (entries.length > 0 || platformJobs.length > 0) {
    return (
      <div className="max-w-content mx-auto">
        <div className="mb-6">
          <h1 className="font-display text-3xl mb-1">Historikk</h1>
          <p className="text-text-secondary text-sm">
            Gjenbruk tidligere innstillinger, åpne resultater, merk favoritter.
          </p>
          {openError && (
            <p className="text-sm text-accent-red mt-2" role="alert">
              {openError}
            </p>
          )}
        </div>
        <div className="space-y-3">
          {platformJobs.filter((job) => !entries.some((entry) => entry.jobId === job.id)).map((job) => (
            <div key={`platform-${job.id}`} className="card flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="badge bg-accent-blue/10 text-accent-blue">{job.module}</span>
                  <span className="text-xs text-text-muted">{job.id.slice(0, 8)}</span>
                </div>
                <p className="mt-2 text-sm font-medium">{job.message || "Generert læringsprodukt"}</p>
                <p className="mt-1 text-xs text-text-secondary">{new Date(job.updated_at).toLocaleString("nb-NO")} · {job.progress}%</p>
              </div>
              <div className="flex items-center gap-3">
                {typeof job.quality_passport?.score === "number" && <span className="text-xs text-text-muted">Kvalitet {job.quality_passport.score}/100</span>}
                <a href={`/${job.module === "platform" ? "projects" : job.module}`} className="btn-secondary">Arbeidsflate</a>
              </div>
            </div>
          ))}
          {entries.map((entry) => (
            <div key={entry.jobId} className="card flex items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-medium">{entry.topic}</h3>
                <p className="text-xs text-text-secondary mt-1">
                  {entry.grade} · {entry.materialType} ·{" "}
                  {new Date(entry.createdAt).toLocaleString("nb-NO")}
                </p>
                {entry.status && (
                  <span
                    className={`inline-block mt-2 text-[10px] font-medium px-2 py-0.5 rounded-full ${
                      entry.status === "completed"
                        ? "bg-accent-green/15 text-accent-green"
                        : entry.status === "completed_with_warnings"
                          ? "bg-accent-orange/15 text-accent-orange"
                          : "bg-accent-red/15 text-accent-red"
                    }`}
                  >
                    {entry.status === "completed"
                      ? "OK"
                      : entry.status === "completed_with_warnings"
                        ? "Advarsel"
                        : "Feilet"}
                  </span>
                )}
                {entry.status === "completed_with_warnings" && entry.warningReason && (
                  <p className="text-[11px] text-text-muted mt-1 max-w-md">
                    {warningReasonLabel(entry.warningReason)}
                  </p>
                )}
                {entry.request.competencyGoals.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {entry.request.competencyGoals.slice(0, 3).map((goal) => (
                      <span
                        key={goal}
                        className="badge text-[10px] !py-0.5 bg-accent-blue/10 text-accent-blue"
                      >
                        {goal}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  className="btn-ghost !p-2"
                  title="Merk som favoritt"
                  onClick={() => {
                    updateHistoryFavorite(entry.jobId, !entry.favorite);
                    refresh();
                  }}
                >
                  <Star
                    size={16}
                    className={
                      entry.favorite ? "fill-accent-orange text-accent-orange" : "text-text-muted"
                    }
                  />
                </button>
                <button
                  className="btn-secondary"
                  disabled={openingId === entry.jobId}
                  onClick={() => openJob(entry)}
                >
                  <FolderOpen size={14} />
                  {openingId === entry.jobId ? "Åpner…" : "Åpne"}
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setRequest({ ...entry.request });
                    router.push("/matematikk");
                  }}
                >
                  <Copy size={14} />
                  Lag lignende
                </button>
                <button
                  className="btn-ghost !p-2 text-accent-red"
                  title="Slett fra historikk"
                  onClick={() => {
                    removeHistoryEntry(entry.jobId);
                    refresh();
                  }}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <Clock size={48} className="text-text-muted opacity-20 mb-4" />
      <h2 className="font-display text-2xl mb-2">Ingen genereringer ennå</h2>
      <p className="text-text-secondary text-sm mb-6 max-w-sm">
        Alt du lager dukker opp her, sortert etter dato.
      </p>
      <a href="/matematikk" className="btn-primary">
        <Sparkles size={14} />
        Start din første generering
      </a>
    </div>
  );
}
