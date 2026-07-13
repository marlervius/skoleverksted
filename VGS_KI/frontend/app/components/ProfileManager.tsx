"use client";

import { useState } from "react";
import { Plus, Pencil, Trash2, Check, X } from "lucide-react";
import type { StudentProfile } from "./constants";
import { LANGUAGE_LEVELS } from "./constants";
import { OptionToggle } from "./OptionToggle";

const MAX_PROFILES = 8;

function profileSummary(p: StudentProfile): string {
  const parts: string[] = [];
  if (p.languageLevel !== "none") parts.push(p.languageLevel);
  if (p.readingFriendly) parts.push("lesevennlig");
  if (p.interest.trim()) parts.push(p.interest.trim());
  return parts.length > 0 ? parts.join(" · ") : "standard";
}

interface ProfileManagerProps {
  profiles: StudentProfile[];
  onChange: (profiles: StudentProfile[]) => void;
  disabled?: boolean;
}

/** Manage saved student-group profiles (label + adaptation axes). */
export function ProfileManager({ profiles, onChange, disabled }: ProfileManagerProps) {
  const [draft, setDraft] = useState<StudentProfile | null>(null);

  const startNew = () =>
    setDraft({
      id: typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `p-${Date.now()}`,
      label: "",
      languageLevel: "none",
      readingFriendly: false,
      interest: "",
    });

  const saveDraft = () => {
    if (!draft || !draft.label.trim()) return;
    const trimmed = { ...draft, label: draft.label.trim(), interest: draft.interest.trim() };
    const exists = profiles.some((p) => p.id === trimmed.id);
    onChange(exists ? profiles.map((p) => (p.id === trimmed.id ? trimmed : p)) : [...profiles, trimmed]);
    setDraft(null);
  };

  const removeProfile = (id: string) => onChange(profiles.filter((p) => p.id !== id));

  return (
    <div>
      {profiles.length > 0 && (
        <ul className="space-y-1.5 mb-2.5">
          {profiles.map((p) => (
            <li
              key={p.id}
              className="flex items-center gap-2 px-3 py-2 bg-white border border-stone-200 rounded-lg text-sm"
            >
              <span className="font-medium text-stone-800 truncate">{p.label}</span>
              <span className="text-xs text-stone-400 truncate flex-1">{profileSummary(p)}</span>
              <button
                type="button"
                onClick={() => setDraft({ ...p })}
                disabled={disabled}
                className="p-1 text-stone-400 hover:text-accent-700 hover:bg-stone-100 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30"
                aria-label={`Rediger ${p.label}`}
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => removeProfile(p.id)}
                disabled={disabled}
                className="p-1 text-stone-400 hover:text-red-600 hover:bg-stone-100 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-red-300"
                aria-label={`Slett ${p.label}`}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {draft ? (
        <div className="p-3 bg-white border border-accent-200 rounded-lg space-y-3">
          <div>
            <label htmlFor="profile-label" className="block text-xs font-medium text-stone-600 mb-1">
              Navn på gruppen
            </label>
            <input
              id="profile-label"
              type="text"
              value={draft.label}
              onChange={(e) => e.target.value.length <= 60 && setDraft({ ...draft, label: e.target.value })}
              placeholder="F.eks. Gruppe A, Lesegruppe, Amir og Sara..."
              className="input-field text-sm"
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="profile-lang" className="block text-xs font-medium text-stone-600 mb-1">
              Språknivå
            </label>
            <select
              id="profile-lang"
              value={draft.languageLevel}
              onChange={(e) => setDraft({ ...draft, languageLevel: e.target.value })}
              className="input-field text-sm"
            >
              {LANGUAGE_LEVELS.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label} — {l.description}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="profile-interest" className="block text-xs font-medium text-stone-600 mb-1">
              Interesser <span className="text-stone-400 font-normal">(valgfritt)</span>
            </label>
            <input
              id="profile-interest"
              type="text"
              value={draft.interest}
              onChange={(e) => e.target.value.length <= 200 && setDraft({ ...draft, interest: e.target.value })}
              placeholder="F.eks. fotball, gaming, musikk..."
              className="input-field text-sm"
            />
          </div>
          <OptionToggle
            label="Lesevennlig modus"
            checked={draft.readingFriendly}
            onChange={(val) => setDraft({ ...draft, readingFriendly: val })}
            description="Tydeligere struktur, kortere setninger, mer luft"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={saveDraft}
              disabled={!draft.label.trim()}
              className="flex-1 py-2 px-3 rounded-md text-xs font-semibold bg-accent-700 hover:bg-accent-800 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-accent-600/30 flex items-center justify-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" aria-hidden="true" />
              Lagre gruppe
            </button>
            <button
              type="button"
              onClick={() => setDraft(null)}
              className="py-2 px-3 rounded-md text-xs font-medium bg-white text-stone-600 border border-stone-300 hover:bg-stone-50 transition-colors focus:outline-none focus:ring-2 focus:ring-stone-300 flex items-center gap-1.5"
            >
              <X className="w-3.5 h-3.5" aria-hidden="true" />
              Avbryt
            </button>
          </div>
        </div>
      ) : (
        profiles.length < MAX_PROFILES && (
          <button
            type="button"
            onClick={startNew}
            disabled={disabled}
            className="w-full py-2 px-3 rounded-lg text-xs font-medium text-accent-700 border border-dashed border-accent-300 hover:bg-accent-50 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30 flex items-center justify-center gap-1.5 disabled:opacity-50"
          >
            <Plus className="w-3.5 h-3.5" aria-hidden="true" />
            {profiles.length === 0 ? "Lag elevgrupper for tilpassede versjoner" : "Ny gruppe"}
          </button>
        )
      )}
    </div>
  );
}
