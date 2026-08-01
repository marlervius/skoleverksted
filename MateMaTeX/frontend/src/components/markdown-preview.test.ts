import { describe, expect, it } from "vitest";
import { parseMarkdownBlocks } from "./markdown-preview";

describe("parseMarkdownBlocks", () => {
  it("preserves headings, lists and tables as structured blocks", () => {
    const blocks = parseMarkdownBlocks(
      "## Oversikt\n\nDette er **fagtekst**.\n\n- Første punkt\n- Andre punkt\n\n| Navn | År |\n| --- | --- |\n| Norge | 1905 |",
    );

    expect(blocks.map((block) => block.type)).toEqual(["heading", "paragraph", "ul", "table"]);
    expect(blocks[0]).toMatchObject({ level: 2, text: "Oversikt" });
    expect(blocks[3]).toMatchObject({ headers: ["Navn", "År"], rows: [["Norge", "1905"]] });
  });

  it("does not treat unsafe links as links", () => {
    const [paragraph] = parseMarkdownBlocks("[Ikke åpne](javascript:alert(1))");
    expect(paragraph).toMatchObject({ type: "paragraph" });
  });
});
