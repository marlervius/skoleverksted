/** Norwegian labels for pipeline agent keys (shared by progress + result). */

export const AGENT_LABELS: Record<string, string> = {
  pedagogue: "Pedagogen",
  author: "Forfatteren",
  math_verifier: "Matematikkverifisering",
  final_math_verifier: "Endelig fasitkontroll",
  editor: "Redaktøren",
  content_quality: "Innholdskontroll",
  tikz_validator: "Figur-kontroll (TikZ)",
  table_validator: "Tabell-kontroll",
  latex_validator: "LaTeX-kompilering",
  latex_fixer: "LaTeX-fikser",
  latex_fallback: "Forenklet dokument",
  layout: "Layout-kvalitet",
  math_blocked: "Fasit blokkert",
  "Henter ferdig materiale": "Henter ferdig materiale",
};

export function agentLabel(agentKey: string): string {
  return AGENT_LABELS[agentKey] || agentKey.replace(/_/g, " ");
}
