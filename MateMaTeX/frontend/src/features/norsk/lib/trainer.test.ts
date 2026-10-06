import { describe, expect, it } from "vitest";
import { canOfferTrainer, trainerUrl } from "./trainer";

describe("trainerUrl", () => {
  it("points at the download-trainer endpoint", () => {
    expect(trainerUrl("https://api.example", "abc-123")).toBe("https://api.example/download-trainer/abc-123");
  });

  it("asks for the watermarked draft with preview=true", () => {
    expect(trainerUrl("https://api.example", "abc-123", true)).toBe(
      "https://api.example/download-trainer/abc-123?preview=true",
    );
  });

  it("encodes the id so it cannot change the path", () => {
    expect(trainerUrl("https://api.example", "a/b?c")).toBe("https://api.example/download-trainer/a%2Fb%3Fc");
  });
});

describe("canOfferTrainer", () => {
  const base = { isDual: false, vocabularyTasks: true };

  it("is offered for a single-level sheet that is ready or awaiting review", () => {
    expect(canOfferTrainer({ ...base, status: "success" })).toBe(true);
    expect(canOfferTrainer({ ...base, status: "needs_teacher_review" })).toBe(true);
  });

  it("is not offered while generating, on error or before anything exists", () => {
    for (const status of ["idle", "loading", "error"] as const) {
      expect(canOfferTrainer({ ...base, status })).toBe(false);
    }
  });

  it("is not offered for ZIP runs, which hold several sheets", () => {
    expect(canOfferTrainer({ ...base, isDual: true, status: "success" })).toBe(false);
  });

  it("is not offered when the sheet has no word tasks", () => {
    expect(canOfferTrainer({ ...base, vocabularyTasks: false, status: "success" })).toBe(false);
  });
});
