import { describe, expect, it } from "vitest";
import { isProgressComplete, nextPollDelayMs } from "./polling";

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
});
