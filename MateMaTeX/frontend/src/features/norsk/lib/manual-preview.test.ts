import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterAll, expect, it, vi } from "vitest";
import { PreviewModal } from "../components/PreviewModal";
import type { LessonResponse } from "./fovTypes";

// Vitest's classic JSX transform needs the same React binding Next provides.
vi.stubGlobal("React", React);
afterAll(() => vi.unstubAllGlobals());

it("shows editable material and manual review without automated source warnings", () => {
  const lesson: LessonResponse = {
    topic: "Et tema", subject: "Norsk", level: "A2.1", review_mode: "teacher-v1",
    text: "Lærerens tekst.", worksheet: "Lærerens oppgave.", teacher_key_content: "Lærerens fasit.",
    quality_stop_reason: "incomplete_claim_register",
  };
  const html = renderToStaticMarkup(React.createElement(PreviewModal, {
    previewData: lesson, formDisabled: false, isGenerating: false,
    onClose: vi.fn(), onGeneratePdf: vi.fn(), onSelectImage: vi.fn(), onEditContent: vi.fn(),
  }));
  expect(html).toContain("Rediger tekstutkast");
  expect(html).toContain("Rediger oppgaveutkast");
  expect(html).toContain("Rediger fasit");
  expect(html).toContain("Generer PDF nå");
  expect(html).toContain("kontroller innholdet");
  expect(html).not.toContain("kildekontroll");
  expect(html).not.toContain("KILDEGODKJENT");
  expect(html).not.toContain("incomplete_claim_register");
});
