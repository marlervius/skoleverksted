import { useAppStore } from "@/lib/store";
import {
  closeActiveStream, getResult, isJobAborted, isTerminalGenerateStatus,
  startGeneration, streamProgress,
} from "@/lib/api";
import { appendHistory } from "@/lib/generation-history";
import { isSuccessfulStatus, mapApiResultToGenerationResult } from "@/lib/map-api-result";

/** Owned by the mathematics page, which stays mounted when the wizard exits. */
export function createGenerationController() {
  let revision = 0;
  let stopWatching: (() => void) | undefined;

  const dispose = () => {
    revision += 1;
    stopWatching?.();
    stopWatching = undefined;
  };

  const generate = async () => {
    const request = useAppStore.getState().request;
    if (!request.topic.trim()) return;
    const snapshot = {
      ...request,
      competencyGoals: [...request.competencyGoals],
      pdfStyle: { ...request.pdfStyle },
    };
    dispose();
    closeActiveStream();
    const run = revision;
    useAppStore.getState().startGeneration();
    const active = (jobId?: string) => run === revision
      && useAppStore.getState().isGenerating
      && (!jobId || (useAppStore.getState().currentJobId === jobId && !isJobAborted(jobId)));

    try {
      const response = await startGeneration({
        grade: snapshot.grade, topic: snapshot.topic,
        material_type: snapshot.materialType, language_level: snapshot.languageLevel,
        num_exercises: snapshot.numExercises, difficulty: snapshot.difficulty,
        include_theory: snapshot.includeTheory, include_examples: snapshot.includeExamples,
        include_exercises: snapshot.includeExercises, include_solutions: snapshot.includeSolutions,
        include_graphs: snapshot.includeGraphs, competency_goals: snapshot.competencyGoals,
        extra_instructions: snapshot.extraInstructions,
        pdf_style: {
          theme: snapshot.pdfStyle.theme, student_mode: snapshot.pdfStyle.studentMode,
          accessible: snapshot.pdfStyle.accessible, dyslexia: snapshot.pdfStyle.dyslexia,
          high_contrast: snapshot.pdfStyle.highContrast,
        },
      });
      if (!active()) return;
      const jobId = response.job_id;
      useAppStore.getState().setJobId(jobId);
      let loading = false;

      const loadResult = async (fallbackError?: string) => {
        if (!active(jobId) || loading) return;
        loading = true;
        useAppStore.getState().setCurrentAgent("Henter ferdig materiale");
        try {
          const raw = await getResult(jobId);
          if (!active(jobId)) return;
          const result = mapApiResultToGenerationResult(raw, snapshot);
          useAppStore.getState().setResult(result);
          if (isSuccessfulStatus(result.status)) {
            appendHistory({
              jobId, createdAt: new Date().toISOString(), topic: snapshot.topic,
              grade: snapshot.grade, materialType: snapshot.materialType, favorite: false,
              status: result.status === "completed_with_warnings" ? "completed_with_warnings" : "completed",
              warningReason: result.warningReason, request: snapshot,
            });
          }
        } catch (error) {
          if (active(jobId)) {
            useAppStore.getState().setError(
              fallbackError || (error instanceof Error ? error.message : "Kunne ikke hente resultat"), snapshot,
            );
          }
        } finally {
          if (run === revision) {
            stopWatching?.();
            stopWatching = undefined;
          }
        }
      };

      if (isTerminalGenerateStatus(response.status)) {
        await loadResult();
        return;
      }
      // streamProgress owns the SSE connection and its independent status poll.
      // This controller survives the wizard's exit animation and unmount.
      stopWatching = streamProgress(jobId, {
        onStep: (step) => {
          if (active(jobId)) useAppStore.getState().addStep({
            agent: step.agent, startedAt: step.started_at, completedAt: step.completed_at,
            durationSeconds: step.duration_seconds, outputSummary: step.output_summary,
            error: step.error, retries: step.retries,
          });
        },
        onCurrentAgent: (agent) => {
          if (active(jobId)) useAppStore.getState().setCurrentAgent(agent);
        },
        onComplete: () => { void loadResult(); },
        onError: (error) => { void loadResult(error); },
      });
    } catch (error) {
      if (active()) useAppStore.getState().setError(
        error instanceof Error ? error.message : "Kunne ikke starte genereringen", snapshot,
      );
    }
  };
  return { generate, dispose };
}
