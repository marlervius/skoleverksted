import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { closeActiveStream, streamProgress } from "./api";

describe("status polling when SSE is silent", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", class {
      addEventListener = vi.fn();
      close = vi.fn();
    });
  });
  afterEach(() => {
    closeActiveStream();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it.each(["completed", "review_required"])("delivers terminal %s without SSE events", async (status) => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ready: false, current_agent: "latex_validator" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ready: false, current_agent: "latex_fixer" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ready: true, status, latex_compiled: status === "completed" }) });
    vi.stubGlobal("fetch", fetcher);
    const onCurrentAgent = vi.fn();
    const onComplete = vi.fn();
    streamProgress("progress-test", { onCurrentAgent, onComplete });
    await vi.advanceTimersByTimeAsync(0);
    expect(onCurrentAgent).toHaveBeenLastCalledWith("latex_validator");
    await vi.advanceTimersByTimeAsync(500);
    expect(onCurrentAgent).toHaveBeenLastCalledWith("latex_fixer");
    await vi.advanceTimersByTimeAsync(500);
    expect(onComplete).toHaveBeenCalledOnce();
    expect(onComplete.mock.calls[0][0].status).toBe(status);
  });

  it("ignores an in-flight status response after the watcher is closed", async () => {
    let resolve!: (value: unknown) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise((done) => { resolve = done; })));
    const onCurrentAgent = vi.fn();
    const close = streamProgress("closed-progress-test", { onCurrentAgent });
    close();
    resolve({ ok: true, json: async () => ({ ready: false, current_agent: "latex_fixer" }) });
    await vi.advanceTimersByTimeAsync(0);
    expect(onCurrentAgent).not.toHaveBeenCalled();
  });
});
