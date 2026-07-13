import { describe, expect, it } from "vitest";
import type { StreamCompletePayload } from "./generation";

describe("generation stream types", () => {
  it("accepts complete payload shape", () => {
    const p: StreamCompletePayload = {
      status: "completed",
      total_duration: 1,
      total_steps: 5,
      math_checks: 10,
      math_correct: 8,
      latex_compiled: true,
      error: null,
    };
    expect(p.latex_compiled).toBe(true);
  });

  it("accepts completed_with_warnings status", () => {
    const p: StreamCompletePayload = {
      status: "completed_with_warnings",
      total_duration: 2,
      total_steps: 6,
      math_checks: 10,
      math_correct: 8,
      latex_compiled: true,
      error: null,
    };
    expect(p.status).toBe("completed_with_warnings");
  });
});
