"use client";

import { RefreshCw } from "lucide-react";

const ACTIONS = [
  ["kortere", "Lag en kortere og strammere versjon uten å miste læringsmålene."],
  ["enklere", "Lag en språklig enklere versjon med korte setninger og tydelige begrepsforklaringer."],
  ["flere oppgaver", "Behold fagteksten, men legg til flere varierte oppgaver med progresjon."],
] as const;

export function RevisionActions({ onSelect, disabled = false }: { onSelect: (instruction: string) => void; disabled?: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-surface-elevated p-3">
      <p className="mb-2 flex items-center gap-2 text-xs font-semibold text-text-primary"><RefreshCw size={14} /> Lag en målrettet ny versjon</p>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map(([label, instruction]) => (
          <button key={label} type="button" disabled={disabled} onClick={() => onSelect(instruction)} className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium hover:border-accent-blue hover:text-accent-blue disabled:opacity-50">{label}</button>
        ))}
      </div>
    </div>
  );
}
