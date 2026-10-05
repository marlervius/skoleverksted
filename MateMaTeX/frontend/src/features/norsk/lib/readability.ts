import type { ReadabilityIssue, ReadabilityReport } from "./fovTypes";

/** How many offending sentences the preview lists before summarising the rest. */
export const MAX_VISIBLE_ISSUES = 5;

/** The panel is only meaningful for levels that have a sentence limit. */
export function shouldShowReadability(
  report: ReadabilityReport | null | undefined,
): report is ReadabilityReport {
  return Boolean(report && report.applicable && report.status !== "not_applicable");
}

export function visibleReadabilityIssues(report: ReadabilityReport): {
  shown: ReadabilityIssue[];
  hidden: number;
} {
  const shown = report.issues.slice(0, MAX_VISIBLE_ISSUES);
  // issue_count is the full total; the API caps the list it sends.
  return { shown, hidden: Math.max(0, report.issue_count - shown.length) };
}
