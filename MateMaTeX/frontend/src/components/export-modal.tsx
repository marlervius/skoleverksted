"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  FileSpreadsheet,
  Presentation,
  Loader2,
  X,
} from "lucide-react";
import { exportPdf, exportDocx, exportPptx, downloadBase64 } from "@/lib/api";
import type { PdfStyle } from "@/lib/store";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  latexContent: string;
  pdfStyle?: PdfStyle;
}

type ExportFormat = "pdf" | "docx" | "pptx";

const FORMAT_CONFIG = {
  pdf: { label: "PDF", icon: <FileText size={20} />, ext: ".pdf" },
  docx: { label: "Word", icon: <FileSpreadsheet size={20} />, ext: ".docx" },
  pptx: { label: "PowerPoint", icon: <Presentation size={20} />, ext: ".pptx" },
};

export function ExportModal({ isOpen, onClose, latexContent, pdfStyle }: ExportModalProps) {
  const [format, setFormat] = useState<ExportFormat>("pdf");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // PDF options
  const [includeSolutions, setIncludeSolutions] = useState(true);
  const [includeCover, setIncludeCover] = useState(false);
  const [printOptimized, setPrintOptimized] = useState(false);
  const [coverSchool, setCoverSchool] = useState("");
  const [coverTeacher, setCoverTeacher] = useState("");
  const [coverTopic, setCoverTopic] = useState("");

  // PPTX
  const [solutionsAs, setSolutionsAs] = useState<"speaker_notes" | "hidden_slides">("speaker_notes");

  const handleExport = async () => {
    setLoading(true);
    setError("");
    try {
      if (format === "pdf") {
        const res = await exportPdf({
          latex_content: latexContent,
          include_solutions: includeSolutions,
          include_cover: includeCover,
          cover_school: coverSchool,
          cover_teacher: coverTeacher,
          cover_topic: coverTopic,
          print_optimized: printOptimized,
          theme: pdfStyle?.theme,
          student_mode: pdfStyle?.studentMode,
          accessible: pdfStyle?.accessible,
          dyslexia: pdfStyle?.dyslexia,
          high_contrast: pdfStyle?.highContrast,
        });
        if (res.success) { downloadBase64(res.content_base64, res.filename, res.mime_type); onClose(); }
        else setError(res.errors.join(", "));
      } else if (format === "docx") {
        const res = await exportDocx(latexContent, coverTopic || "Oppgaveark", includeSolutions);
        if (res.success) { downloadBase64(res.content_base64, res.filename, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"); onClose(); }
        else setError(res.errors.join(", "));
      } else if (format === "pptx") {
        const res = await exportPptx(latexContent, coverTopic || "Matematikk", solutionsAs);
        if (res.success) { downloadBase64(res.content_base64, res.filename, "application/vnd.openxmlformats-officedocument.presentationml.presentation"); onClose(); }
        else setError(res.errors.join(", "));
      }
    } catch (e: any) {
      setError(e.message || "Eksport feilet");
    } finally {
      setLoading(false);
    }
  };

  const handleTeacherAndStudentPdf = async () => {
    setLoading(true);
    setError("");
    try {
      const common = {
        latex_content: latexContent,
        include_cover: includeCover,
        cover_school: coverSchool,
        cover_teacher: coverTeacher,
        cover_topic: coverTopic,
        print_optimized: printOptimized,
        theme: pdfStyle?.theme,
        accessible: pdfStyle?.accessible,
        dyslexia: pdfStyle?.dyslexia,
        high_contrast: pdfStyle?.highContrast,
      };
      const [student, teacher] = await Promise.all([
        exportPdf({ ...common, include_solutions: false, student_mode: true }),
        exportPdf({ ...common, include_solutions: true, student_mode: false }),
      ]);
      if (!student.success || !teacher.success) {
        setError(
          [...(student.errors || []), ...(teacher.errors || [])].join(", ") ||
            "Kunne ikke lage begge PDF-versjonene."
        );
        return;
      }
      downloadBase64(student.content_base64, "matematex-elevkopi.pdf", student.mime_type);
      downloadBase64(teacher.content_base64, "matematex-lærerkopi.pdf", teacher.mime_type);
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Eksport feilet");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 10 }}
          transition={{ duration: 0.2, type: "spring", bounce: 0.2 }}
          className="relative bg-surface border border-border rounded-xl shadow-soft-lg w-full max-w-lg mx-4 p-6"
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold">Eksporter dokument</h2>
            <button onClick={onClose} className="btn-ghost !p-1.5" aria-label="Lukk">
              <X size={16} />
            </button>
          </div>

          {/* Format selector */}
          <div className="grid grid-cols-3 gap-2 mb-6">
            {(Object.entries(FORMAT_CONFIG) as [ExportFormat, typeof FORMAT_CONFIG.pdf][]).map(
              ([key, cfg]) => (
                <button
                  key={key}
                  onClick={() => setFormat(key)}
                  className={`card-interactive !p-4 text-center ${
                    format === key ? "!border-accent-blue bg-accent-blue/5" : ""
                  }`}
                >
                  <div className="flex justify-center mb-1 text-text-secondary">
                    {cfg.icon}
                  </div>
                  <div className="text-sm font-medium">{cfg.label}</div>
                  <div className="text-[10px] text-text-muted">{cfg.ext}</div>
                </button>
              )
            )}
          </div>

          {/* Options */}
          <div className="space-y-3 mb-6">
            {format !== "pptx" && (
              <label className="flex items-center gap-3 text-sm cursor-pointer text-text-secondary">
                <input type="checkbox" checked={includeSolutions} onChange={(e) => setIncludeSolutions(e.target.checked)} className="rounded border-border" />
                Inkluder løsninger
              </label>
            )}

            {format === "pdf" && (
              <>
                <label className="flex items-center gap-3 text-sm cursor-pointer text-text-secondary">
                  <input type="checkbox" checked={printOptimized} onChange={(e) => setPrintOptimized(e.target.checked)} className="rounded border-border" />
                  Print-optimalisert (gråtoner)
                </label>
                <label className="flex items-center gap-3 text-sm cursor-pointer text-text-secondary">
                  <input type="checkbox" checked={includeCover} onChange={(e) => setIncludeCover(e.target.checked)} className="rounded border-border" />
                  Inkluder forside
                </label>
                <AnimatePresence>
                  {includeCover && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="ml-7 space-y-2"
                    >
                      <input value={coverSchool} onChange={(e) => setCoverSchool(e.target.value)} placeholder="Skolenavn" className="input" />
                      <input value={coverTeacher} onChange={(e) => setCoverTeacher(e.target.value)} placeholder="Lærernavn" className="input" />
                      <input value={coverTopic} onChange={(e) => setCoverTopic(e.target.value)} placeholder="Emne" className="input" />
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            )}

            {format === "pptx" && (
              <div>
                <label className="text-xs text-text-muted block mb-2">Løsninger som:</label>
                <div className="flex gap-2">
                  {(["speaker_notes", "hidden_slides"] as const).map((opt) => (
                    <button
                      key={opt}
                      onClick={() => setSolutionsAs(opt)}
                      className={`btn-ghost text-xs ${solutionsAs === opt ? "!bg-accent-blue/10 !text-accent-blue" : ""}`}
                    >
                      {opt === "speaker_notes" ? "Speaker notes" : "Skjulte slides"}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 px-3 py-2 bg-accent-red/5 border border-accent-red/20 rounded-lg text-xs text-accent-red">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="btn-secondary">Avbryt</button>
            {format === "pdf" && (
              <button
                onClick={handleTeacherAndStudentPdf}
                disabled={loading}
                className="btn-secondary"
              >
                Elev + lærer
              </button>
            )}
            <button onClick={handleExport} disabled={loading} className="btn-primary">
              {loading && <Loader2 size={14} className="animate-spin" />}
              Eksporter
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
