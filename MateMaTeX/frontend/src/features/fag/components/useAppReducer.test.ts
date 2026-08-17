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
        qualityQuarantine: [
          {
            id: "quarantine-1",
            claim_id: "claim-1",
            content_type: "fact",
            original_text: "Uverifisert påstand.",
            location: "fagtekst",
            reason: "Ingen autoritativ kilde ble funnet.",
            source_attempts: [],
            suggested_replacement: "",
            omission_consequence: "Påstanden utelates fra elevmaterialet.",
            status: "withheld",
            created_at: "2026-08-17T00:00:00Z",
          },
        ],
      },
    );

    expect(state.status).toBe("review");
    expect(state.showEditPanel).toBe(true);
    expect(state.previewBlob).toBeNull();
    expect(state.qualityStopReason).toBe("truth_layer_timeout");
    expect(state.qualityQuarantine).toHaveLength(1);
  });
});
