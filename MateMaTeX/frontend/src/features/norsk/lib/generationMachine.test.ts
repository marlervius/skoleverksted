import { describe, expect, it } from "vitest";

import {
  generationReducer,
  getGenerationControls,
  initialGenerationState,
  isGenerating,
  isPollingExpired,
} from "./generationMachine";

describe("Norsklæring generation state machine", () => {
  it("always leaves generating and clears progress after a backend failure", () => {
    const started = generationReducer(initialGenerationState, {
      type: "started",
      jobId: "job-1",
      requestId: "request-1",
      totalSteps: 4,
    });
    const failed = generationReducer(started, {
      type: "terminal_received",
      jobId: "job-1",
      status: "failed",
      message: "Tekstgeneratoren svarte ikke innen tidsgrensen. Innholdet ble ikke lagret. Du kan prøve igjen.",
      requestId: "request-1",
      stepName: "Genererer og strukturerer læringsinnhold",
      errorCode: "model_timeout",
    });

    expect(isGenerating(failed)).toBe(false);
    expect(failed.status).toBe("failed");
    expect(failed.progress).toBeNull();
    expect(failed.requestId).toBe("request-1");
    expect(failed.failedStepName).toContain("læringsinnhold");

    const controls = getGenerationControls(failed, true);
    expect(controls.primaryLabel).toBe("Generer PDF");
    expect(controls.primaryDisabled).toBe(false);
    expect(controls.previewDisabled).toBe(false);
  });

  it("shows the spinner label and disables both starts only while generating", () => {
    const started = generationReducer(initialGenerationState, {
      type: "started",
      jobId: "job-active",
      totalSteps: 4,
    });
    expect(getGenerationControls(started, true)).toEqual({
      primaryLabel: "Genererer...",
      primaryDisabled: true,
      previewDisabled: true,
    });
  });

  it("ignores a late response from an older job", () => {
    const active = generationReducer(initialGenerationState, {
      type: "started",
      jobId: "job-new",
      totalSteps: 4,
    });
    const late = generationReducer(active, {
      type: "terminal_received",
      jobId: "job-old",
      status: "completed",
      message: "Ferdig",
    });
    expect(late).toEqual(active);
  });

  it("keeps the image recovery actions without pretending the job failed", () => {
    const started = generationReducer(initialGenerationState, {
      type: "started",
      jobId: "job-image",
      totalSteps: 4,
    });
    const action = generationReducer(started, {
      type: "terminal_received",
      jobId: "job-image",
      status: "needs_user_action",
      message: "Læringsinnholdet er klart, men KI-bildet kunne ikke lages.",
      availableActions: [
        "retry_image",
        "continue_without_image",
        "choose_commons",
        "upload_image",
        "cancel",
      ],
    });
    expect(isGenerating(action)).toBe(false);
    expect(action.status).toBe("needs_user_action");
    expect(action.availableActions).toContain("continue_without_image");
  });

  it("stops a never-ending polling loop at the configured deadline", () => {
    expect(isPollingExpired(1_000, 1_000 + 6 * 60_000 + 1)).toBe(true);
    expect(isPollingExpired(1_000, 2_000)).toBe(false);
  });

  it("returns to idle for a safe retry while retaining form state outside the machine", () => {
    const failed = {
      ...initialGenerationState,
      status: "failed" as const,
      jobId: "broken",
      errorMessage: "Feil",
    };
    const reset = generationReducer(failed, { type: "reset" });
    expect(reset.status).toBe("idle");
    expect(reset.jobId).toBeNull();
  });
});
