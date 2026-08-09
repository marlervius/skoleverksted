import { describe, expect, it } from "vitest";
import { SUBJECTS, YEAR_PLAN_LEVELS } from "./constants";

describe("årsplanfag", () => {
  it.each([
    "Matematikk",
    "Naturfag",
    "Samfunnsfag",
  ])("viser %s som valgbart fag", (subject) => {
    expect(SUBJECTS.some((item) => item.value === subject)).toBe(true);
  });

  it("viser FOV modul 4 som valgbart nivå", () => {
    expect(YEAR_PLAN_LEVELS.some((item) => item.value === "FOV modul 4")).toBe(true);
  });
});
