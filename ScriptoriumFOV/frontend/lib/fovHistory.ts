import { DEFAULT_ACCESSIBILITY, DEFAULT_OPTIONS } from "./fovConstants";
import type { AccessibilityState, HistoryItem, OptionsState } from "./fovTypes";

const OPTION_LABELS: { key: keyof OptionsState; label: string }[] = [
  { key: "deep_dive", label: "Fordypning" },
  { key: "comprehension_tasks", label: "Faktaoppgaver" },
  { key: "grammar_tasks", label: "Grammatikk" },
  { key: "vocabulary_tasks", label: "Ordoppgaver" },
  { key: "discussion_tasks", label: "Diskusjon" },
  { key: "teacher_key", label: "Fasit" },
  { key: "role_play", label: "Rollespill" },
  { key: "image_description", label: "Bildebeskrivelse" },
  { key: "writing_frame", label: "Skriveramme" },
  { key: "cultural_comparison", label: "Kulturblikk" },
  { key: "real_case", label: "Virkelig case" },
];

/** Compared to defaults: what was toggled (e.g. "Fasit · Rollespill" or "Standard tilpassing"). */
export function summarizeOptions(o: OptionsState): string {
  const parts: string[] = [];
  for (const { key, label } of OPTION_LABELS) {
    if (o[key] !== DEFAULT_OPTIONS[key]) {
      parts.push(o[key] ? label : `uten ${label.toLowerCase()}`);
    }
  }
  if (parts.length === 0) return "Standard tilpassing";
  return parts.join(" · ");
}

export function summarizeAccessibility(a: AccessibilityState): string {
  const parts: string[] = [];
  if (a.dyslexia_font) parts.push("Dysleksi-font");
  if (a.high_contrast) parts.push("Høy kontrast");
  if (a.large_print) parts.push("Stor skrift");
  return parts.join(" · ");
}

export function summarizeHistoryMeta(item: HistoryItem): string {
  const opt = summarizeOptions(item.options);
  const acc = summarizeAccessibility(item.accessibility || DEFAULT_ACCESSIBILITY);
  const bits = [opt];
  if (acc) bits.push(acc);
  if (item.series) {
    bits.push(
      `Serie ${item.series.lesson_number}/${item.series.total_lessons}${
        item.series.series_theme ? `: ${item.series.series_theme}` : ""
      }`
    );
  }
  return bits.join(" · ");
}
