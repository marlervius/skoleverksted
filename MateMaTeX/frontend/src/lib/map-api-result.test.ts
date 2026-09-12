import { describe, expect, it } from "vitest";
import { mapApiResultToGenerationResult } from "./map-api-result";

describe("automatic mathematics release", () => {
  it.each([
    { source_approved: false },
    { source_approved: true, math_verification: { claims_unparseable: 1 } },
    { source_approved: true, math_verification: { claims_incorrect: 1 } },
  ])("does not offer an old unresolved result as completed", (details) => {
    const result = mapApiResultToGenerationResult({ status: "completed_with_warnings", ...details });
    expect(result.status).toBe("failed");
    expect(result.error).toContain("automatisk reparasjon");
  });

  it("keeps verified figure fallback deliverable", () => {
    const result = mapApiResultToGenerationResult({
      status: "completed_with_warnings", source_approved: true, warning_reason: "fallback",
      math_verification: { claims_incorrect: 0, claims_unparseable: 0, all_correct: true },
    });
    expect(result.status).toBe("completed_with_warnings");
    expect(result.error).toBe("");
  });
});
