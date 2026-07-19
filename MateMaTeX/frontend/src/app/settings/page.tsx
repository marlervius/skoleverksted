"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import {
  loadPreferences,
  savePreferences,
  DEFAULT_PREFERENCES,
} from "@/lib/user-preferences";

const GRADES = [
  "8. trinn",
  "9. trinn",
  "10. trinn",
  "VG1 1T",
  "VG2 R1",
];

const LANGUAGE_LEVELS = [
  { value: "standard", label: "Standard norsk" },
  { value: "b2", label: "Forenklet (B2)" },
  { value: "b1", label: "Enklere (B1)" },
];

export default function SettingsPage() {
  const setRequest = useAppStore((s) => s.setRequest);
  const [grade, setGrade] = useState(DEFAULT_PREFERENCES.grade);
  const [languageLevel, setLanguageLevel] = useState(DEFAULT_PREFERENCES.languageLevel);

  useEffect(() => {
    const prefs = loadPreferences();
    setGrade(prefs.grade);
    setLanguageLevel(prefs.languageLevel);
  }, []);

  const updateGrade = (value: string) => {
    setGrade(value);
    savePreferences({ grade: value });
    setRequest({ grade: value });
  };

  const updateLanguageLevel = (value: string) => {
    setLanguageLevel(value);
    savePreferences({ languageLevel: value });
    setRequest({ languageLevel: value });
  };

  return (
    <div className="max-w-reading mx-auto">
      <h1 className="font-display text-3xl mb-8">Innstillinger</h1>

      <div className="space-y-6">
        <div className="card">
          <h2 className="text-sm font-medium mb-4">Standard-innstillinger</h2>
          <p className="text-xs text-text-secondary mb-4">
            Disse verdiene brukes som utgangspunkt i genereringsveiviseren.
          </p>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-text-muted block mb-1">
                Standard klassetrinn
              </label>
              <select
                className="input !w-auto"
                value={grade}
                onChange={(e) => updateGrade(e.target.value)}
              >
                {GRADES.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">
                Standard språknivå
              </label>
              <select
                className="input !w-auto"
                value={languageLevel}
                onChange={(e) => updateLanguageLevel(e.target.value)}
              >
                {LANGUAGE_LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="text-sm font-medium mb-2">Data og funksjoner</h2>
          <p className="text-xs text-text-secondary leading-relaxed">
            Oppgavebank, historikk på tvers av økter og skolefunksjoner krever at
            backend er satt opp med <code className="text-text-primary">DATABASE_URL</code>{" "}
            (PostgreSQL). Med Supabase kan du også sette{" "}
            <code className="text-text-primary">SUPABASE_JWT_SECRET</code> for
            brukerspesifikk lagring. Uten database fungerer generering og redigering
            som vanlig, med lokal fil-lagring som fallback.
          </p>
        </div>

        <div className="card">
          <h2 className="text-sm font-medium mb-2">Om MateMaTeX</h2>
          <p className="text-xs text-text-muted">
            Versjon 2.0 — AI-drevet matematikkverksted for norske lærere.
            Bygget med LangGraph, SymPy, FastAPI og Next.js.
          </p>
        </div>
      </div>
    </div>
  );
}
