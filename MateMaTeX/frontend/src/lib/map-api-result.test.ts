import { describe, expect, it } from "vitest";
import { categorizeError, isSuccessfulStatus, mapApiResultToGenerationResult } from "./map-api-result";

describe("automatic mathematics release", () => {
  it("preserves review drafts without presenting them as approved", () => {
    const result = mapApiResultToGenerationResult({ status: "review_required", source_approved: false,
      full_document: "draft", pdf_available: false, math_verification: { claims_unparseable: 30 } });
    expect(result.status).toBe("review_required");
    expect(result.fullDocument).toBe("draft");
    expect(isSuccessfulStatus(result.status)).toBe(false);
    expect(result.sourceApproved).toBe(false);
  });
  it("retains compilation errors for a verified document", () => {
    expect(categorizeError("Den verifiserte teksten kunne ikke kompileres.", false, true)).toBe("latex");
  });
  it.each([
    { source_approved: false },
    { source_approved: true, math_verification: { claims_unparseable: 1 } },
    { source_approved: true, math_verification: { claims_incorrect: 1 } },
  ])("does not offer an old unresolved result as completed", (details) => {
    const result = mapApiResultToGenerationResult({ status: "completed_with_warnings", ...details });
    expect(result.status).toBe("failed");
    expect(result.error).toContain("automatisk reparasjon");
    expect(result.errorCategory).toBe("verification");
  });

  it("explains the production verification failure even when its message was sanitized", () => {
    const result = mapApiResultToGenerationResult({
      status: "failed", warning_reason: "verification",
      error: "KI-genereringen feilet midlertidig. Prøv igjen.",
      latex_compilation: { success: true },
      math_verification: { claims_checked: 34, claims_correct: 5, claims_unparseable: 29 },
    });
    expect(result.status).toBe("failed");
    expect(result.error).toContain("Eksport er stoppet");
    expect(result.errorCategory).toBe("verification");
  });

  it("keeps cancellation distinct from verification failure", () => {
    const result = mapApiResultToGenerationResult({
      status: "failed", warning_reason: "verification", error: "Avbrutt av bruker",
    });
    expect(result.error).toBe("Avbrutt av bruker");
    expect(result.errorCategory).toBe("aborted");
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
