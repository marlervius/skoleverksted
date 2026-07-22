"use client";

import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { submitGenerationFeedback, type PlatformJob } from "@/lib/platform-api";

export function GenerationFeedback({ module, artifactId = "", projectId }: {
  module: PlatformJob["module"];
  artifactId?: string;
  projectId?: string | null;
}) {
  const [sent, setSent] = useState<"up" | "down" | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function vote(rating: "up" | "down") {
    setBusy(true);
    try {
      await submitGenerationFeedback({ module, artifact_id: artifactId, project_id: projectId, rating });
      setSent(rating);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  if (sent) return <p role="status" className="text-xs text-text-muted">Takk — vurderingen er lagret og brukes i kvalitetsarbeidet.</p>;
  return (
    <div className="flex items-center gap-2 text-xs text-text-muted">
      <span>Var dette nyttig?</span>
      <button type="button" disabled={busy} onClick={() => void vote("up")} className="rounded-lg border border-border p-2 hover:bg-surface-elevated" aria-label="Nyttig resultat"><ThumbsUp size={14} /></button>
      <button type="button" disabled={busy} onClick={() => void vote("down")} className="rounded-lg border border-border p-2 hover:bg-surface-elevated" aria-label="Resultatet trenger forbedring"><ThumbsDown size={14} /></button>
      {failed && <span role="alert" className="text-accent-red">Kunne ikke lagre nå.</span>}
    </div>
  );
}
