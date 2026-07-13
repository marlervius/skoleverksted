"use client";

import React, { useState, useEffect, useRef } from "react";
import { BookOpen, Search, ChevronDown, ChevronUp, Loader2, X } from "lucide-react";
import { fetchCompetencyGoals, type CompetencyGoal } from "./api";

interface GrepPickerProps {
  subject: string;
  level: string;
  onSelect: (goal: CompetencyGoal) => void;
  selectedKode?: string;
}

export const GrepPicker = React.memo(function GrepPicker({
  subject,
  level,
  onSelect,
  selectedKode,
}: GrepPickerProps) {
  const [goals, setGoals] = useState<CompetencyGoal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch goals when subject/level changes
  useEffect(() => {
    if (!subject) return;
    setLoading(true);
    setError(null);
    fetchCompetencyGoals(subject, level)
      .then((data) => {
        setGoals(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Kunne ikke hente kompetansemål");
        setLoading(false);
      });
  }, [subject, level]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = query.trim()
    ? goals.filter((g) =>
        g.tittel.toLowerCase().includes(query.trim().toLowerCase()) ||
        g.kode.toLowerCase().includes(query.trim().toLowerCase())
      )
    : goals;

  const selected = goals.find((g) => g.kode === selectedKode);

  if (goals.length === 0 && !loading) return null;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="w-full flex items-center justify-between gap-2 px-3.5 py-2.5 bg-white border border-stone-300 hover:border-stone-400 rounded-lg text-sm text-stone-600 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/15 focus:border-accent-600"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 min-w-0">
          <BookOpen className="w-4 h-4 text-accent-600 shrink-0" aria-hidden="true" />
          {loading ? (
            <span className="flex items-center gap-1.5 text-stone-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Henter LK20-mål…
            </span>
          ) : selected ? (
            <span className="truncate text-stone-800" title={selected.tittel}>
              <span className="text-stone-400 font-mono text-xs mr-1.5">{selected.kode}</span>
              {selected.tittel}
            </span>
          ) : (
            <span className="text-stone-400">Velg kompetansemål (LK20) — valgfritt</span>
          )}
        </span>
        <span className="shrink-0 flex items-center gap-1">
          {selected && (
            <span
              role="button"
              tabIndex={0}
              aria-label="Fjern valgt kompetansemål"
              onClick={(e) => {
                e.stopPropagation();
                onSelect({ kode: "", tittel: "", laereplan: "" });
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.stopPropagation();
                  onSelect({ kode: "", tittel: "", laereplan: "" });
                }
              }}
              className="p-0.5 rounded hover:bg-stone-100 text-stone-400 hover:text-stone-700 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </span>
          )}
          {open ? (
            <ChevronUp className="w-4 h-4 text-stone-400" aria-hidden="true" />
          ) : (
            <ChevronDown className="w-4 h-4 text-stone-400" aria-hidden="true" />
          )}
        </span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1.5 w-full bg-white border border-stone-200 rounded-lg shadow-pop overflow-hidden">
          {/* Search */}
          <div className="p-2 border-b border-stone-100">
            <div className="flex items-center gap-2 px-2.5 py-1.5 bg-stone-100 rounded-md">
              <Search className="w-3.5 h-3.5 text-stone-400 shrink-0" aria-hidden="true" />
              <input
                autoFocus
                type="text"
                placeholder="Søk i kompetansemål…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1 bg-transparent text-sm text-stone-800 placeholder-stone-400 outline-none"
                aria-label="Søk i kompetansemål"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="text-stone-400 hover:text-stone-700"
                  aria-label="Tøm søk"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* List */}
          <ul
            role="listbox"
            aria-label="Kompetansemål"
            className="max-h-60 overflow-y-auto"
          >
            {error ? (
              <li className="px-3 py-2 text-sm text-red-600">{error}</li>
            ) : filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-stone-400">
                {query ? "Ingen treff" : "Ingen mål tilgjengelig"}
              </li>
            ) : (
              filtered.map((goal) => (
                <li key={goal.kode}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={goal.kode === selectedKode}
                    onClick={() => {
                      onSelect(goal);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={`w-full text-left px-3 py-2.5 text-sm hover:bg-stone-50 transition-colors flex gap-2 items-start ${
                      goal.kode === selectedKode ? "bg-accent-50 text-accent-800" : "text-stone-700"
                    }`}
                  >
                    <span className="font-mono text-xs text-stone-400 shrink-0 mt-0.5">
                      {goal.kode}
                    </span>
                    <span className="leading-snug">{goal.tittel}</span>
                  </button>
                </li>
              ))
            )}
          </ul>

          {/* Footer */}
          {goals.length > 0 && (
            <div className="px-3 py-1.5 border-t border-stone-100 text-xs text-stone-400 text-right">
              {filtered.length} av {goals.length} mål · LK20
            </div>
          )}
        </div>
      )}
    </div>
  );
});
