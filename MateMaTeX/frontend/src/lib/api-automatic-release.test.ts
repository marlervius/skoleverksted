import { afterEach, describe, expect, it, vi } from "vitest";
import { createShare, downloadJobPdf, exportDocx, exportPdf, exportPptx } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("automatic mathematics release", () => {
  it("downloads the verified PDF without recording a teacher decision", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["%PDF"]) });
    const anchor = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
    vi.stubGlobal("fetch", fetcher);
    vi.stubGlobal("document", { createElement: () => anchor, body: { appendChild: vi.fn() } });
    await downloadJobPdf("verified-job");
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toMatch(/\/verified-job\/pdf$/);
    expect(fetcher.mock.calls[0][1]).toBeUndefined();
    expect(anchor.click).toHaveBeenCalledOnce();
  });

  it("shares without an implicit teacher approval", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
    vi.stubGlobal("fetch", fetcher);
    await createShare({ resource_type: "generation", resource_id: "verified-job" });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toMatch(/\/sharing$/);
  });

  it("asks the server to verify exports without sending a teacher checkbox", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
    vi.stubGlobal("fetch", fetcher);
    await exportPdf({ latex_content: "$2+2=4$" });
    await exportDocx("$2+2=4$");
    await exportPptx("$2+2=4$");
    for (const [, init] of fetcher.mock.calls) {
      expect(JSON.parse(init.body)).not.toHaveProperty("teacher_approved");
    }
  });
});
