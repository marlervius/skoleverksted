import { describe, expect, it } from "vitest";
import { isProgressComplete, nextPollDelayMs, progressErrorMessage } from "./polling";

describe("preview polling", () => {
  it("does not treat an intermediate image-search step as complete", () => {
    expect(isProgressComplete(2, 3)).toBe(false);
    expect(isProgressComplete(3, 3)).toBe(true);
  });

  it("rejects invalid and failed progress values", () => {
    expect(isProgressComplete(-1, 3)).toBe(false);
    expect(isProgressComplete(undefined, 3)).toBe(false);
  });

  it("caps the polling delay", () => {
    expect(nextPollDelayMs(100)).toBe(8000);
  });

  it("recognizes a failed lifecycle even when the last step is stale", () => {
    expect(
      progressErrorMessage({
        step: 1,
        total_steps: 4,
        job_status: "failed",
        message: "Noe gikk galt under generering.",
      }),
    ).toBe("Noe gikk galt under generering.");
  });

  it("returns no error for a running progress update", () => {
    expect(
      progressErrorMessage({
        step: 1,
        total_steps: 4,
        job_status: "running",
        message: "Skriver pedagogisk tekst...",
      }),
    ).toBeNull();
  });
});
