import { describe, expect, it } from "vitest";
import { LEVELS, sortLevelsByCefr } from "./fovConstants";

describe("language levels", () => {
  it("offers Pre-A1 as the first level", () => {
    expect(LEVELS[0].value).toBe("Pre-A1");
  });

  it("sorts Pre-A1 before the A1 sub-levels", () => {
    expect(sortLevelsByCefr(["A2.1", "Pre-A1", "A1.1"])).toEqual(["Pre-A1", "A1.1", "A2.1"]);
  });
});
