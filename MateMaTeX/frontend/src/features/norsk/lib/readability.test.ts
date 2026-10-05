import { describe, expect, it } from "vitest";
import type { ReadabilityReport } from "./fovTypes";
import {
  MAX_VISIBLE_ISSUES,
  shouldShowReadability,
  visibleReadabilityIssues,
} from "./readability";

function report(overrides: Partial<ReadabilityReport> = {}): ReadabilityReport {
  return {
    level: "A2.1",
    base_level: "A2",
    applicable: true,
    sentence_count: 10,
    word_count: 90,
    average_sentence_words: 9,
    longest_sentence_words: 12,
    limit_words: 14,
    issue_count: 0,
    issues: [],
    truncated: 0,
    status: "ok",
    summary: "Alle 10 setninger holder A2-grensen på 14 ord.",
    ...overrides,
  };
}

function issues(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    code: "sentence_too_long",
    sentence: `Setning ${index + 1}`,
    words: 20,
    limit: 14,
    message: "For lang.",
  }));
}

describe("shouldShowReadability", () => {
  it("hides the panel when there is no report", () => {
    expect(shouldShowReadability(undefined)).toBe(false);
    expect(shouldShowReadability(null)).toBe(false);
  });

  it("hides the panel for levels without a sentence limit", () => {
    expect(shouldShowReadability(report({ applicable: false, status: "not_applicable" }))).toBe(false);
  });

  it("shows the panel for an applicable report, passing or not", () => {
    expect(shouldShowReadability(report())).toBe(true);
    expect(shouldShowReadability(report({ status: "needs_attention", issue_count: 1, issues: issues(1) }))).toBe(true);
  });
});

describe("visibleReadabilityIssues", () => {
  it("lists every issue when there are few", () => {
    const result = visibleReadabilityIssues(report({ issue_count: 3, issues: issues(3) }));
    expect(result.shown).toHaveLength(3);
    expect(result.hidden).toBe(0);
  });

  it("caps the list and counts the rest, including issues the API truncated", () => {
    const result = visibleReadabilityIssues(report({ issue_count: 27, issues: issues(20), truncated: 7 }));
    expect(result.shown).toHaveLength(MAX_VISIBLE_ISSUES);
    expect(result.hidden).toBe(27 - MAX_VISIBLE_ISSUES);
  });
});
