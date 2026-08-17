import test from "node:test";
import assert from "node:assert/strict";

import {
  generationReducer,
  initialGenerationState,
} from "./generationState";

const artifact = {
  id: "job-a:student_pdf:abc",
  job_id: "job-a",
  kind: "student_pdf" as const,
  filename: "Arbeidsliv.pdf",
  content_type: "application/pdf" as const,
  size_bytes: 1024,
  preview_url: "/preview",
  download_url: "/download",
};

test("ignores a status response from an older job", () => {
  const state = generationReducer(initialGenerationState, {
    type: "started",
    jobId: "job-new",
  });
  const next = generationReducer(state, {
    type: "status_received",
    jobId: "job-old",
    step: 4,
    totalSteps: 4,
    message: "gammel",
    jobStatus: "completed",
    artifact,
  });
  assert.equal(next.status, "generating");
  assert.equal(next.jobId, "job-new");
});

test("does not mark a full progress bar as complete without done plus an artifact", () => {
  let state = generationReducer(initialGenerationState, {
    type: "started",
    jobId: "job-a",
  });
  state = generationReducer(state, {
    type: "status_received",
    jobId: "job-a",
    step: 4,
    totalSteps: 4,
    message: "Artefakt bygges",
    jobStatus: "running",
  });
  assert.equal(state.status, "building_artifact");

  state = generationReducer(state, {
    type: "status_received",
    jobId: "job-a",
    step: 4,
    totalSteps: 4,
    message: "Ferdig",
    eventType: "done",
    jobStatus: "completed",
    artifact,
  });
  assert.equal(state.status, "completed");

  const late = generationReducer(state, {
    type: "status_received",
    jobId: "job-a",
    step: 1,
    totalSteps: 4,
    message: "sen progress",
    jobStatus: "running",
  });
  assert.equal(late.status, "completed");
  assert.equal(late.artifact?.id, artifact.id);
});
