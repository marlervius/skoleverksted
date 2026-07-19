"use client";

import { Image as ImageIcon, Sparkles, X } from "lucide-react";

export type ImageMode = "none" | "commons" | "ai";

interface ImageModePickerProps {
  value: ImageMode;
  onChange: (mode: ImageMode) => void;
  disabled?: boolean;
  compact?: boolean;
}

const choices: Array<{
  value: ImageMode;
  label: string;
  description: string;
  icon: typeof ImageIcon;
}> = [
  {
    value: "none",
    label: "Uten bilde",
    description: "Raskest og helt uten bildekall",
    icon: X,
  },
  {
    value: "commons",
    label: "Frie bilder",
    description: "Kvalitetssjekket fra Wikimedia Commons",
    icon: ImageIcon,
  },
  {
    value: "ai",
    label: "Lag AI-bilde",
    description: "Én tydelig merket illustrasjon fra Google",
    icon: Sparkles,
  },
];

export function ImageModePicker({
  value,
  onChange,
  disabled = false,
  compact = false,
}: ImageModePickerProps) {
  return (
    <fieldset>
      <legend className="field-label">
        <ImageIcon className="h-4 w-4 text-accent-600" aria-hidden="true" />
        Bilder i PDF-en
      </legend>
      <div className={`grid gap-2 ${compact ? "grid-cols-1 sm:grid-cols-3" : "grid-cols-1 md:grid-cols-3"}`}>
        {choices.map((choice) => {
          const Icon = choice.icon;
          const selected = value === choice.value;
          return (
            <button
              key={choice.value}
              type="button"
              onClick={() => onChange(choice.value)}
              disabled={disabled}
              aria-pressed={selected}
              className={`rounded-lg border px-3 py-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/25 disabled:cursor-not-allowed disabled:opacity-60 ${
                selected
                  ? "border-accent-500 bg-accent-50 text-accent-900"
                  : "border-stone-200 bg-white text-stone-700 hover:border-stone-400"
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-semibold">
                <Icon className="h-4 w-4" aria-hidden="true" />
                {choice.label}
              </span>
              <span className="mt-1 block text-xs leading-snug text-stone-500">
                {choice.description}
              </span>
            </button>
          );
        })}
      </div>
      {value === "ai" && (
        <p className="mt-2 text-xs text-amber-700">
          Eksperimentell modus. Google-kallet kan koste penger, og illustrasjonen merkes tydelig som KI-generert.
        </p>
      )}
      {value === "commons" && (
        <p className="mt-2 text-xs text-stone-500">
          Bildecrewet kan velge å utelate bildet dersom ingen kandidat er faglig trygg nok.
        </p>
      )}
    </fieldset>
  );
}
