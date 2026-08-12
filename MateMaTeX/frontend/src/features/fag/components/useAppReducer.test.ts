import { describe, expect, it } from "vitest";
import { appReducer, initialState } from "./useAppReducer";

describe("fag generation review state", () => {
  it("opens the editable control view without a PDF", () => {
    const state = appReducer(
      { ...initialState, status: "loading", basisText: null, worksheetText: null },
      {
        type: "GENERATION_REVIEW",
        basisText: "Kontrollerbar fagtekst.",
        worksheetText: "Oppgave.",
        qualityStopReason: "truth_layer_timeout",
        quarantine: [{ original_text: "Uverifisert påstand." }],
      },
    );

    expect(state.status).toBe("review");
    expect(state.showEditPanel).toBe(true);
    expect(state.previewBlob).toBeNull();
    expect(state.qualityStopReason).toBe("truth_layer_timeout");
    expect(state.quarantine).toHaveLength(1);
  });
});
