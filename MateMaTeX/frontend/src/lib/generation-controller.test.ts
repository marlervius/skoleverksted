import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createGenerationController } from "./generation-controller";
import { useAppStore } from "./store";
import { getResult, startGeneration, streamProgress } from "./api";
import { appendHistory } from "./generation-history";

vi.mock("./api", () => ({
  startGeneration: vi.fn(), getResult: vi.fn(), streamProgress: vi.fn(),
  closeActiveStream: vi.fn(), isJobAborted: () => false,
  isTerminalGenerateStatus: (s: string) => ["completed", "completed_with_warnings", "failed"].includes(s),
}));
vi.mock("./generation-history", () => ({ appendHistory: vi.fn() }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("mathematics generation lifecycle", () => {
  let controller: ReturnType<typeof createGenerationController>;
  let callbacks: Parameters<typeof streamProgress>[1];
  const close = vi.fn();
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.getState().cancelGeneration();
    useAppStore.getState().setResult(null);
    useAppStore.getState().setRequest({ topic: "Funksjoner" });
    controller = createGenerationController();
    vi.mocked(startGeneration).mockResolvedValue({ job_id: "job", status: "pending", message: "" });
    vi.mocked(streamProgress).mockImplementation((_id, handlers) => { callbacks = handlers; return close; });
    vi.mocked(getResult).mockResolvedValue({
      job_id: "job", status: "completed_with_warnings", full_document: "verified material",
      pdf_available: true, math_verification: {}, latex_compilation: { success: true },
      steps: [], total_duration_seconds: 91, total_tokens: 0, error: "",
    });
  });
  afterEach(() => controller.dispose());

  it("loads the completed PDF result after the wizard has exited", async () => {
    const response = deferred<Awaited<ReturnType<typeof startGeneration>>>();
    vi.mocked(startGeneration).mockReturnValue(response.promise);
    const running = controller.generate();
    // This state removes GenerationWizard from the page. Its lifetime must
    // have no ownership of the pending request or completion watcher.
    expect(useAppStore.getState().isGenerating).toBe(true);
    response.resolve({ job_id: "job", status: "pending", message: "" });
    await running;
    callbacks.onCurrentAgent?.("latex_validator");
    expect(useAppStore.getState().currentAgent).toBe("latex_validator");
    callbacks.onComplete?.({ status: "completed_with_warnings", total_duration: 91, total_steps: 11, math_checks: 37, math_correct: 10, latex_compiled: true, error: null });
    await vi.waitFor(() => expect(useAppStore.getState().result?.jobId).toBe("job"));
    expect(useAppStore.getState().isGenerating).toBe(false);
    expect(useAppStore.getState().result?.latexCompiled).toBe(true);
    expect(appendHistory).toHaveBeenCalledOnce();
    expect(close).toHaveBeenCalledOnce();
  });

  it("fetches instant cached completion without opening a watcher", async () => {
    vi.mocked(startGeneration).mockResolvedValue({ job_id: "job", status: "completed", message: "" });
    await controller.generate();
    expect(getResult).toHaveBeenCalledWith("job");
    expect(streamProgress).not.toHaveBeenCalled();
    expect(useAppStore.getState().isGenerating).toBe(false);
  });

  it("does not update the UI when a start response arrives after page disposal", async () => {
    const response = deferred<Awaited<ReturnType<typeof startGeneration>>>();
    vi.mocked(startGeneration).mockReturnValue(response.promise);
    const running = controller.generate();
    controller.dispose();
    response.resolve({ job_id: "old", status: "pending", message: "" });
    await running;
    expect(streamProgress).not.toHaveBeenCalled();
    expect(useAppStore.getState().currentJobId).toBeNull();
  });

  it("ignores completion and an in-flight result after cancellation", async () => {
    const result = deferred<Awaited<ReturnType<typeof getResult>>>();
    vi.mocked(getResult).mockReturnValue(result.promise);
    await controller.generate();
    callbacks.onError?.("stream interrupted");
    useAppStore.getState().cancelGeneration();
    result.resolve({ job_id: "job", status: "completed", full_document: "late", math_verification: {}, latex_compilation: {}, steps: [], total_duration_seconds: 1, total_tokens: 0, error: "" });
    await Promise.resolve();
    expect(useAppStore.getState().result).toBeNull();
    expect(appendHistory).not.toHaveBeenCalled();
  });

  it("deduplicates completion while a result is loading and terminates on fetch failure", async () => {
    vi.mocked(getResult).mockRejectedValue(new Error("409: Resultat blokkert"));
    await controller.generate();
    callbacks.onError?.("Resultatet kunne ikke hentes");
    callbacks.onError?.("second event");
    await vi.waitFor(() => expect(useAppStore.getState().result?.status).toBe("failed"));
    expect(getResult).toHaveBeenCalledOnce();
    expect(useAppStore.getState().isGenerating).toBe(false);
    expect(close).toHaveBeenCalledOnce();
  });
});
