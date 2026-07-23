"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Download,
  Pencil,
  Layers,
  Share2,
  Star,
  ChevronDown,
  FileText,
  FileSpreadsheet,
  Presentation,
  Printer,
  CheckCircle2,
  XCircle,
  Clock,
  Cpu,
  Plus,
  RefreshCw,
  AlertTriangle,
  CheckSquare,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import {
  exportPdf,
  exportDocx,
  exportPptx,
  downloadBase64,
  ingestExercises,
  differentiate,
  createShare,
  downloadJobPdf,
  fetchJobPdfObjectUrl,
} from "@/lib/api";
import {
  isJobFavorite,
  updateHistoryFavorite,
} from "@/lib/generation-history";
import {
  errorCategoryLabel,
  isSuccessfulStatus,
  warningReasonLabel,
} from "@/lib/map-api-result";
import { agentLabel } from "@/lib/agent-labels";
import { PdfViewer } from "@/components/pdf-viewer";
import { ExportModal } from "@/components/export-modal";

type Tab = "document" | "editor" | "differentiation";

export function ResultView() {
  const result = useAppStore((s) => s.result);
  const request = useAppStore((s) => s.request);
  const setRequest = useAppStore((s) => s.setRequest);
  const lastFailedRequest = useAppStore((s) => s.lastFailedRequest);
  const clearLastFailedRequest = useAppStore((s) => s.clearLastFailedRequest);
  const toggleLatexEditor = useAppStore((s) => s.toggleLatexEditor);
  const setResult = useAppStore((s) => s.setResult);
  const [activeTab, setActiveTab] = useState<Tab>("document");
  const [showLatex, setShowLatex] = useState(false);
  const [showDownloads, setShowDownloads] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const [includeSolutionsExport, setIncludeSolutionsExport] = useState(true);
  const [approvalChecks, setApprovalChecks] = useState({
    reviewed: false,
    language: false,
    classFit: false,
    mathReviewed: false,
  });

  // Differentiation
  const [diffData, setDiffData] = useState<{
    success: boolean;
    basic_latex?: string;
    standard_latex?: string;
    advanced_latex?: string;
    basic_exercise_count?: number;
    standard_exercise_count?: number;
    advanced_exercise_count?: number;
    basic_quality?: {
      score: number;
      passed: boolean;
      math_verified: boolean;
      issue_count: number;
      summary: string;
    } | null;
    standard_quality?: {
      score: number;
      passed: boolean;
      math_verified: boolean;
      issue_count: number;
      summary: string;
    } | null;
    advanced_quality?: {
      score: number;
      passed: boolean;
      math_verified: boolean;
      issue_count: number;
      summary: string;
    } | null;
    errors?: string[];
  } | null>(null);
  const [diffError, setDiffError] = useState("");
  const [diffLoading, setDiffLoading] = useState(false);
  const [activeLevel, setActiveLevel] = useState<"basic" | "standard" | "advanced">("standard");
  const [diffShowLatex, setDiffShowLatex] = useState(false);
  // PDF preview per differentiation level (object URLs)
  const [diffPdfUrls, setDiffPdfUrls] = useState<Record<string, string>>({});
  const [diffPdfLoading, setDiffPdfLoading] = useState<string>("");
  const [diffPdfError, setDiffPdfError] = useState("");

  // Export
  const [exportLoading, setExportLoading] = useState("");
  const [exportError, setExportError] = useState("");
  const [ingestStatus, setIngestStatus] = useState("");

  // Live PDF preview
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewError, setPdfPreviewError] = useState<string>("");
  const [pdfPreviewLoading, setPdfPreviewLoading] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [shareLoading, setShareLoading] = useState(false);
  const [shareError, setShareError] = useState("");

  useEffect(() => {
    if (!result?.jobId) return;
    setIsFavorite(isJobFavorite(result.jobId));
  }, [result?.jobId]);

  const selectedCompetencyGoals = useMemo(
    () => result?.generationMeta?.competencyGoals || [],
    [result?.generationMeta]
  );

  useEffect(() => {
    let cancelled = false;
    let revoke: string | null = null;
    setPdfPreviewError("");
    setPdfPreviewUrl(null);

    if (
      !result?.jobId ||
      !isSuccessfulStatus(result.status) ||
      !result.latexCompiled ||
      result.pdfBase64
    ) {
      return;
    }

    setPdfPreviewLoading(true);
    fetchJobPdfObjectUrl(result.jobId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        revoke = url;
        setPdfPreviewUrl(url);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setPdfPreviewError(err.message || "Kunne ikke laste PDF for forhåndsvisning");
        }
      })
      .finally(() => {
        if (!cancelled) setPdfPreviewLoading(false);
      });

    return () => {
      cancelled = true;
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [result?.jobId, result?.status, result?.latexCompiled, result?.fullDocument]);

  // Auto-compile a PDF preview for the active differentiation level on demand.
  useEffect(() => {
    if (!diffData?.success) return;
    if (diffPdfUrls[activeLevel] || diffPdfLoading) return;
    const latex =
      activeLevel === "basic"
        ? diffData.basic_latex
        : activeLevel === "standard"
        ? diffData.standard_latex
        : diffData.advanced_latex;
    if (!latex) return;

    let cancelled = false;
    setDiffPdfError("");
    setDiffPdfLoading(activeLevel);
    exportPdf({ latex_content: latex })
      .then((res) => {
        if (cancelled) return;
        if (!res.success || !res.content_base64) {
          setDiffPdfError(
            (res.errors || []).join("\n").trim() || "Kunne ikke lage PDF for dette nivået."
          );
          return;
        }
        const bytes = Uint8Array.from(atob(res.content_base64), (c) => c.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
        setDiffPdfUrls((prev) => ({ ...prev, [activeLevel]: url }));
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setDiffPdfError(e instanceof Error ? e.message : "Kunne ikke lage PDF.");
        }
      })
      .finally(() => {
        if (!cancelled) setDiffPdfLoading("");
      });

    return () => {
      cancelled = true;
    };
  }, [diffData, activeLevel, diffPdfUrls, diffPdfLoading]);

  // Revoke differentiation PDF object URLs on unmount to avoid leaks.
  useEffect(() => {
    return () => {
      Object.values(diffPdfUrls).forEach((u) => URL.revokeObjectURL(u));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!result) return null;

  const isSuccess = isSuccessfulStatus(result.status);
  const hasWarnings = result.status === "completed_with_warnings";
  const hasUnparseable = result.mathVerification.claimsUnparseable > 0;
  const hasIncorrect = result.mathVerification.claimsIncorrect > 0;
  const isVerifiedFasit =
    result.mathVerification.claimsChecked > 0 &&
    !hasIncorrect &&
    !hasUnparseable &&
    result.mathVerification.allCorrect;
  const hasMathIssues = hasUnparseable || hasIncorrect;
  const canShare =
    approvalChecks.reviewed &&
    approvalChecks.language &&
    approvalChecks.classFit &&
    (!hasMathIssues || approvalChecks.mathReviewed);

  /* ---- Export handlers ---- */
  const handleExport = async (format: string) => {
    setExportLoading(format);
    setExportError("");
    try {
      let res: { success: boolean; content_base64: string; filename: string; mime_type?: string; errors?: string[] } | null = null;

      if (format === "pdf" || format === "pdf-print") {
        if (format === "pdf" && includeSolutionsExport && result.jobId) {
          await downloadJobPdf(result.jobId);
          return;
        }
        res = await exportPdf({
          latex_content: result.fullDocument,
          print_optimized: format === "pdf-print",
          include_solutions: includeSolutionsExport,
          theme: result.generationMeta?.pdfStyle.theme,
          student_mode: result.generationMeta?.pdfStyle.studentMode,
          accessible: result.generationMeta?.pdfStyle.accessible,
          dyslexia: result.generationMeta?.pdfStyle.dyslexia,
          high_contrast: result.generationMeta?.pdfStyle.highContrast,
        });
      } else if (format === "docx") {
        res = await exportDocx(result.fullDocument, "Oppgaveark", includeSolutionsExport);
      } else if (format === "pptx") {
        res = await exportPptx(result.fullDocument);
      }

      if (!res) return;
      if (res.success) {
        const mime =
          res.mime_type ||
          (format === "docx"
            ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            : format === "pptx"
            ? "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            : "application/pdf");
        downloadBase64(res.content_base64, res.filename, mime);
      } else {
        const detail = (res.errors || []).join("\n").trim();
        setExportError(
          detail ||
            "Eksport feilet. Prøv «Last ned» igjen, eller åpne editor for å se etter feil i LaTeX-en."
        );
      }
    } catch (err: any) {
      setExportError(
        err?.message ||
          "Nettverksfeil under eksport. Sjekk forbindelsen og at backend er tilgjengelig."
      );
    } finally {
      setExportLoading("");
      setShowDownloads(false);
    }
  };

  const countExercises = (latex: string): number =>
    (latex.match(/\\begin\{(oppgave|taskbox|exercise)\}|\\subsection\*?\{Oppgave/g) || [])
      .length;

  // The pipeline already produces basic/advanced versions for "differensiert"
  // materials — reuse them instead of paying for another LLM round-trip.
  const hydrateDiffFromPipeline = (): boolean => {
    if (!result.differentiatedBasic || !result.differentiatedAdvanced) return false;
    const bodyMatch = result.fullDocument.match(
      /\\begin\{document\}([\s\S]*?)\\end\{document\}/
    );
    const body = bodyMatch ? bodyMatch[1] : result.fullDocument;
    const stdMatch = body.match(
      /\\section\*\{Standard\}([\s\S]*?)(?=\\section\*\{Avansert\}|$)/
    );
    const standard = (stdMatch ? stdMatch[1] : body).trim();
    setDiffData({
      success: true,
      basic_latex: result.differentiatedBasic,
      standard_latex: standard,
      advanced_latex: result.differentiatedAdvanced,
      basic_exercise_count: countExercises(result.differentiatedBasic),
      standard_exercise_count: countExercises(standard),
      advanced_exercise_count: countExercises(result.differentiatedAdvanced),
      errors: [],
    });
    return true;
  };

  const handleDifferentiate = async () => {
    setDiffError("");
    setActiveTab("differentiation");
    if (!diffData && hydrateDiffFromPipeline()) return;
    setDiffLoading(true);
    try {
      const res = await differentiate(
        result.fullDocument,
        request?.topic ?? "",
        request?.grade ?? ""
      );
      if (res.success) {
        setDiffData(res);
      } else {
        setDiffError((res.errors || []).join("; ") || "Differensiering feilet");
      }
    } catch (e: unknown) {
      setDiffError(e instanceof Error ? e.message : "Differensiering feilet");
    } finally {
      setDiffLoading(false);
    }
  };

  const diffLevelQuality = (level: "basic" | "standard" | "advanced") =>
    level === "basic"
      ? diffData?.basic_quality
      : level === "standard"
      ? diffData?.standard_quality
      : diffData?.advanced_quality;

  const diffLevelLatex = (level: "basic" | "standard" | "advanced"): string =>
    (level === "basic"
      ? diffData?.basic_latex
      : level === "standard"
      ? diffData?.standard_latex
      : diffData?.advanced_latex) || "";

  const ensureDiffPdf = async (
    level: "basic" | "standard" | "advanced"
  ): Promise<string | null> => {
    if (diffPdfUrls[level]) return diffPdfUrls[level];
    const latex = diffLevelLatex(level);
    if (!latex) {
      setDiffPdfError("Mangler innhold for dette nivået.");
      return null;
    }
    setDiffPdfError("");
    setDiffPdfLoading(level);
    try {
      const res = await exportPdf({ latex_content: latex });
      if (!res.success || !res.content_base64) {
        setDiffPdfError(
          (res.errors || []).join("\n").trim() || "Kunne ikke lage PDF for dette nivået."
        );
        return null;
      }
      const bytes = Uint8Array.from(atob(res.content_base64), (c) => c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
      setDiffPdfUrls((prev) => ({ ...prev, [level]: url }));
      return url;
    } catch (e: unknown) {
      setDiffPdfError(e instanceof Error ? e.message : "Kunne ikke lage PDF.");
      return null;
    } finally {
      setDiffPdfLoading("");
    }
  };

  const handleDiffDownloadPdf = async (
    level: "basic" | "standard" | "advanced"
  ) => {
    const url = await ensureDiffPdf(level);
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = `oppgaver_${level}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const handleIngest = async () => {
    setIngestStatus("loading");
    try {
      const res = await ingestExercises(
        result.fullDocument,
        result.generationMeta?.topic || request.topic,
        result.generationMeta?.grade || request.grade,
        result.jobId
      );
      setIngestStatus(`${res.ingested} oppgaver lagret`);
    } catch {
      setIngestStatus("Feil");
    }
  };

  const goToWizardWithSameSettings = () => {
    const base = lastFailedRequest || result.generationMeta || request;
    setRequest({ ...base });
    setResult(null);
    clearLastFailedRequest();
  };

  const handleShare = async () => {
    if (!canShare || !result.jobId) return;
    setShareLoading(true);
    setShareError("");
    try {
      const res = await createShare({
        resource_type: "generation",
        resource_id: result.jobId,
        expires_hours: 168,
      });
      const fullUrl = `${window.location.origin}${res.share_url}`;
      setShareUrl(fullUrl);
      await navigator.clipboard.writeText(fullUrl);
    } catch (e: unknown) {
      setShareError(e instanceof Error ? e.message : "Kunne ikke opprette delingslenke");
    } finally {
      setShareLoading(false);
    }
  };

  const toggleFavorite = () => {
    const next = !isFavorite;
    setIsFavorite(next);
    if (result.jobId) {
      updateHistoryFavorite(result.jobId, next);
    }
  };

  return (
    <div className="max-w-content mx-auto pb-24">
      {/* Status banner */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`card mb-6 ${
          isSuccess
            ? hasWarnings
              ? "!border-accent-orange/30 bg-accent-orange/5"
              : "!border-accent-green/30 bg-accent-green/5"
            : "!border-accent-red/30 bg-accent-red/5"
        }`}
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              {isSuccess ? (
                <CheckCircle2 size={20} className="text-accent-green" />
              ) : (
                <AlertTriangle size={20} className="text-accent-red" />
              )}
              {isSuccess
                ? hasWarnings
                  ? "Materiale generert — krever gjennomgang"
                  : "Materiale generert"
                : "Generering feilet"}
            </h2>
            <p className="mt-1 break-words text-sm text-text-secondary">
              {isSuccess
                ? `${result.fromCache ? "Hentet fra hurtigbuffer · " : ""}Ferdig på ${result.totalDuration.toFixed(1)} sekunder`
                : result.error}
            </p>
            {!isSuccess && (
              <p className="text-xs text-text-muted mt-1">
                Feilkategori: {errorCategoryLabel(result.errorCategory || "unknown")}
              </p>
            )}
            {isSuccess && hasWarnings && (
              <p className="text-xs text-accent-orange mt-1">
                {warningReasonLabel(result.warningReason)}
              </p>
            )}
          </div>
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
            {!isSuccess && (
              <button
                onClick={goToWizardWithSameSettings}
                className="btn-secondary w-full justify-center sm:w-auto"
              >
                <RefreshCw size={14} />
                Prøv igjen
              </button>
            )}
            <button
              onClick={() => {
                setResult(null);
              }}
              className="btn-ghost w-full justify-center sm:w-auto"
            >
              <Plus size={16} className="rotate-45" />
              Ny generering
            </button>
          </div>
        </div>
      </motion.div>

      {isSuccess && (
        <>
          {selectedCompetencyGoals.length > 0 && (
            <div className="card mb-6">
              <h3 className="text-sm font-medium mb-2">Koblet til LK20-mål</h3>
              <p className="text-xs text-text-muted mb-2">
                Sjekk at dokumentet dekker disse målene før du deler med elever.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {selectedCompetencyGoals.map((goal) => (
                  <span key={goal} className="badge text-[10px] !py-0.5 bg-accent-blue/10 text-accent-blue">
                    {goal}
                  </span>
                ))}
              </div>
            </div>
          )}

          {(result.differentiatedBasic || result.differentiatedAdvanced) && (
            <div className="card mb-6 !border-accent-blue/20 bg-accent-blue/5">
              <h3 className="text-sm font-medium mb-1">Differensiert materiale</h3>
              <p className="text-xs text-text-secondary">
                Dokumentet inneholder seksjonene Grunnleggende, Standard og Avansert.
              </p>
            </div>
          )}

          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard
              icon={<CheckCircle2 size={16} />}
              label="Matte-sjekk"
              value={
                isVerifiedFasit
                  ? "SymPy OK"
                  : hasIncorrect
                  ? "Feil funnet"
                  : hasUnparseable
                  ? `${result.mathVerification.claimsCorrect}/${result.mathVerification.claimsChecked} (+ uverif.)`
                  : result.mathVerification.allCorrect
                  ? "Alt korrekt"
                  : `${result.mathVerification.claimsCorrect}/${result.mathVerification.claimsChecked}`
              }
              color={isVerifiedFasit ? "green" : hasIncorrect ? "red" : hasUnparseable ? "orange" : "orange"}
            />
            <StatCard
              icon={<FileText size={16} />}
              label="LaTeX"
              value={result.latexCompiled ? "Kompilert" : "Feil"}
              color={result.latexCompiled ? "green" : "red"}
            />
            <StatCard
              icon={<Cpu size={16} />}
              label="Agenter"
              value={`${result.steps.length} steg`}
              color="blue"
            />
            <StatCard
              icon={<Clock size={16} />}
              label="Tid"
              value={`${result.totalDuration.toFixed(1)}s`}
              color="purple"
            />
          </div>

          {isVerifiedFasit && (
            <div className="card mb-6 !border-accent-green/30 bg-accent-green/5">
              <h3 className="text-sm font-semibold text-accent-green mb-1">SymPy-verifisert fasit</h3>
              <p className="text-xs text-text-secondary">
                Alle utregninger som kunne kontrolleres maskinelt, er sjekket før utlevering (grunnlov §1).
              </p>
            </div>
          )}

          {hasUnparseable && !hasIncorrect && (
            <div className="card mb-6 !border-accent-orange/30 bg-accent-orange/5">
              <h3 className="text-sm font-semibold mb-2">Lærer kontroll anbefales</h3>
              <p className="text-xs text-text-secondary mb-3">
                Noen oppgaver kunne ikke verifiseres automatisk. De er merket i PDF-en — kontroller fasit manuelt.
              </p>
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {result.mathVerification.unparseableClaims.map((c) => (
                  <div key={c.claimId} className="rounded-lg border border-accent-orange/20 bg-accent-orange/5 p-2">
                    <div className="text-[11px] font-mono text-accent-orange mb-1">{c.latexExpression || c.claimId}</div>
                    <div className="text-xs text-text-secondary">Kunne ikke parses automatisk</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasIncorrect && (
            <div className="card mb-6 !border-accent-red/30 bg-accent-red/5">
              <h3 className="text-sm font-semibold text-accent-red mb-2">Feil i fasit</h3>
              <p className="text-xs text-text-secondary mb-3">
                SymPy fant utregninger som ikke stemmer. Slikt materiale leveres normalt ikke (grunnlov §1).
              </p>
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {result.mathVerification.incorrectClaims.map((c) => (
                  <div key={c.claimId} className="rounded-lg border border-accent-red/20 bg-accent-red/5 p-2">
                    <div className="text-[11px] font-mono text-accent-red mb-1">{c.latexExpression || c.claimId}</div>
                    <div className="text-xs text-text-secondary">{c.errorMessage || "Feil i påstand"}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.contentQuality && (
            <div
              className={`card mb-6 ${
                result.contentQuality.passed
                  ? "!border-accent-green/30 bg-accent-green/5"
                  : "!border-accent-orange/30 bg-accent-orange/5"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold">Innholdskvalitet og pensumdekning</h3>
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    result.contentQuality.passed
                      ? "bg-accent-green/15 text-accent-green"
                      : "bg-accent-orange/15 text-accent-orange"
                  }`}
                >
                  {result.contentQuality.score}/100
                </span>
              </div>
              {result.contentQuality.passed ? (
                <p className="text-xs text-text-secondary">
                  Struktur og valgte pensumområder bestod den automatiske innholdskontrollen.
                  {result.contentQuality.semanticScore !== undefined &&
                    result.contentQuality.semanticScore < 100 && (
                      <span className="block mt-1">
                        Semantisk vurdering: {result.contentQuality.semanticScore}/100
                        {result.contentQuality.semanticSummary
                          ? ` — ${result.contentQuality.semanticSummary}`
                          : ""}
                      </span>
                    )}
                </p>
              ) : (
                <>
                  <p className="text-xs text-text-secondary mb-3">
                    Kontroller disse punktene før materialet brukes:
                  </p>
                  {result.contentQuality.semanticScore !== undefined &&
                    result.contentQuality.semanticScore < 100 && (
                      <p className="text-xs text-text-secondary mb-3 rounded-md border border-accent-purple/20 bg-accent-purple/5 px-2 py-1.5">
                        Semantisk vurdering: {result.contentQuality.semanticScore}/100
                        {result.contentQuality.semanticSummary
                          ? ` — ${result.contentQuality.semanticSummary}`
                          : ""}
                      </p>
                    )}
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {result.contentQuality.issues.slice(0, 12).map((issue, index) => (
                      <div
                        key={`${issue.code}-${index}`}
                        className="text-xs text-text-secondary rounded-md border border-accent-orange/20 px-2 py-1"
                      >
                        {issue.message}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {(result.layoutFixAttempts ?? 0) > 0 && (
            <p className="text-xs text-accent-blue mb-4 px-3 py-2 rounded-lg border border-accent-blue/20 bg-accent-blue/5">
              Layout ble automatisk justert (figurstørrelse/linjebryting) før PDF ble levert.
            </p>
          )}

          {result.layoutReport && result.layoutReport.issues.length > 0 && (
            <div className="card mb-6 !border-accent-blue/30 bg-accent-blue/5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold">Layout-kvalitet</h3>
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    result.layoutReport.score >= 90
                      ? "bg-accent-green/15 text-accent-green"
                      : result.layoutReport.score >= 70
                        ? "bg-accent-orange/15 text-accent-orange"
                        : "bg-accent-red/15 text-accent-red"
                  }`}
                >
                  {result.layoutReport.score}/100
                </span>
              </div>
              <p className="text-xs text-text-secondary mb-3">
                {result.layoutReport.summary}
              </p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {result.layoutReport.issues
                  .filter((i) => i.severity !== "info")
                  .slice(0, 12)
                  .map((i, idx) => (
                    <div
                      key={idx}
                      className="text-xs text-text-secondary rounded-md border border-border/60 px-2 py-1"
                    >
                      {i.detail}
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Tabs */}
          <div
            className="flex items-center gap-1 border-b border-border mb-6"
            role="tablist"
            aria-label="Resultatfaner"
          >
            {([
              { id: "document" as Tab, label: "Dokument" },
              { id: "editor" as Tab, label: "Rediger" },
              { id: "differentiation" as Tab, label: "Differensiering" },
            ]).map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                id={`tab-${tab.id}`}
                aria-selected={activeTab === tab.id}
                aria-controls={`panel-${tab.id}`}
                onClick={() => {
                  if (tab.id === "differentiation" && !diffData && !diffLoading) {
                    handleDifferentiate();
                  } else {
                    setActiveTab(tab.id);
                  }
                }}
                className={`relative px-4 py-2.5 text-sm transition-colors ${
                  activeTab === tab.id
                    ? "text-accent-blue"
                    : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {tab.label}
                {activeTab === tab.id && (
                  <motion.div
                    layoutId="tab-indicator"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-blue rounded-full"
                  />
                )}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <AnimatePresence mode="wait">
            {activeTab === "document" && (
              <motion.div
                key="doc"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-6"
              >
                {result.usedLatexFallback && (
                  <div className="card mb-4 !border-accent-orange/30 bg-accent-orange/5">
                    <p className="text-sm text-text-secondary">
                      <strong>Forenklet versjon:</strong> Noen figurer (f.eks. TikZ) ble
                      fjernet fordi LaTeX ikke kompilerte. Oppgavene og teksten er beholdt.
                      Eksporter PDF for å se layout.
                    </p>
                  </div>
                )}

                {!result.fullDocument && result.latexCompiled && (
                  <p className="text-sm text-text-secondary mb-2">
                    Henter fullstendig dokument… PDF-forhåndsvisning lastes parallelt.
                  </p>
                )}

                {/* PDF Preview */}
                <div className="card !p-0 overflow-hidden">
                  {result.pdfBase64 ? (
                    <PdfViewer
                      src={`data:application/pdf;base64,${result.pdfBase64}`}
                      title="Generert PDF"
                    />
                  ) : pdfPreviewUrl ? (
                    <PdfViewer src={pdfPreviewUrl} title="Generert PDF" />
                  ) : (
                    <div className="bg-surface-elevated p-8 text-center min-h-[400px] flex flex-col items-center justify-center gap-3">
                      <FileText size={48} className="opacity-30 text-text-muted" />
                      {pdfPreviewLoading ? (
                        <p className="text-sm text-text-muted">Laster PDF-forhåndsvisning…</p>
                      ) : pdfPreviewError ? (
                        <>
                          <p className="text-sm text-accent-red">Kunne ikke hente PDF</p>
                          <p className="text-xs text-text-muted max-w-md">{pdfPreviewError}</p>
                        </>
                      ) : (
                        <p className="text-sm text-text-muted">
                          {result.latexCompiled
                            ? "PDF ikke tilgjengelig i forhåndsvisning — bruk Eksporter PDF"
                            : "PDF kunne ikke genereres automatisk"}
                        </p>
                      )}
                      {result.latexCompiled && !pdfPreviewLoading && (
                        <button
                          type="button"
                          onClick={() => handleExport("pdf")}
                          disabled={!!exportLoading}
                          className="btn-secondary text-xs"
                        >
                          Generer PDF for forhåndsvisning
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* LaTeX source (collapsible) */}
                <div className="card">
                  <button
                    onClick={() => setShowLatex(!showLatex)}
                    className="flex items-center justify-between w-full"
                  >
                    <span className="text-sm font-medium">LaTeX-kilde</span>
                    <motion.span
                      animate={{ rotate: showLatex ? 180 : 0 }}
                      className="text-text-muted"
                    >
                      <ChevronDown size={16} />
                    </motion.span>
                  </button>
                  <AnimatePresence>
                    {showLatex && (
                      <motion.pre
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-3 bg-bg rounded-lg p-4 text-xs font-mono text-text-secondary overflow-x-auto max-h-96 overflow-y-auto"
                      >
                        {result.fullDocument}
                      </motion.pre>
                    )}
                  </AnimatePresence>
                </div>

                {/* Pipeline details */}
                <div className="card">
                  <h3 className="text-sm font-medium mb-3">Pipeline-detaljer</h3>
                  <div className="space-y-1">
                    {result.steps.map((step: any, i: number) => (
                      <div
                        key={i}
                        className="flex items-center justify-between text-sm py-2 border-b border-border last:border-0"
                      >
                        <span className="text-text-secondary">{agentLabel(step.agent)}</span>
                        <div className="flex items-center gap-3 text-xs text-text-muted">
                          {step.error && (
                            <span className="text-accent-red">{step.error}</span>
                          )}
                          <span>{step.durationSeconds?.toFixed(1)}s</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "editor" && (
              <motion.div
                key="edit"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className="card text-center py-12">
                  <Pencil size={32} className="mx-auto mb-3 text-text-muted opacity-50" />
                  <p className="text-sm text-text-secondary mb-4">
                    Åpne fullskjerm-editoren for å redigere LaTeX med live forhåndsvisning
                  </p>
                  <button
                    onClick={() => toggleLatexEditor()}
                    className="btn-primary"
                  >
                    <Pencil size={14} />
                    Åpne editor
                  </button>
                </div>
              </motion.div>
            )}

            {activeTab === "differentiation" && (
              <motion.div
                key="diff"
                role="tabpanel"
                id="panel-differentiation"
                aria-labelledby="tab-differentiation"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {diffError && (
                  <p className="text-sm text-accent-red mb-3" role="alert">
                    {diffError}
                  </p>
                )}
                {diffLoading ? (
                  <div className="card text-center py-12">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                      className="w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full mx-auto mb-3"
                    />
                    <p className="text-sm text-text-secondary">
                      Genererer tre nivåer...
                    </p>
                  </div>
                ) : diffData ? (
                  <div className="space-y-4">
                    {/* Level tabs */}
                    <div className="flex gap-2">
                      {(["basic", "standard", "advanced"] as const).map((level) => (
                        <button
                          key={level}
                          onClick={() => setActiveLevel(level)}
                          className={`btn-ghost flex-1 ${
                            activeLevel === level
                              ? "!bg-accent-blue/10 !text-accent-blue"
                              : ""
                          }`}
                        >
                          {level === "basic"
                            ? `Grunnleggende (${diffData.basic_exercise_count})`
                            : level === "standard"
                            ? `Standard (${diffData.standard_exercise_count})`
                            : `Avansert (${diffData.advanced_exercise_count})`}
                        </button>
                      ))}
                    </div>

                    {diffPdfError && (
                      <p className="text-sm text-accent-red" role="alert">
                        {diffPdfError}
                      </p>
                    )}

                    {/* Quality badges per level */}
                    {(["basic", "standard", "advanced"] as const).map((level) => {
                      const q = diffLevelQuality(level);
                      if (!q) return null;
                      return (
                        <div
                          key={level}
                          className={`text-xs px-3 py-2 rounded-lg border ${
                            q.passed
                              ? "border-accent-green/30 bg-accent-green/5 text-accent-green"
                              : "border-accent-orange/30 bg-accent-orange/5 text-accent-orange"
                          } ${activeLevel !== level ? "opacity-60" : ""}`}
                        >
                          <span className="font-medium">
                            {level === "basic"
                              ? "Grunnleggende"
                              : level === "standard"
                              ? "Standard"
                              : "Avansert"}
                            {": "}
                            {q.passed ? "OK" : "Kontroller"}
                          </span>
                          <span className="text-text-muted ml-2">
                            {q.score}/100 · {q.math_verified ? "SymPy OK" : "SymPy advarsel"}
                            {q.summary && q.summary !== "OK" ? ` · ${q.summary}` : ""}
                          </span>
                        </div>
                      );
                    })}

                    {/* PDF preview / LaTeX toggle for the active level */}
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium">
                        Forhåndsvisning ({activeLevel === "basic" ? "Grunnleggende" : activeLevel === "standard" ? "Standard" : "Avansert"})
                      </h4>
                      <button
                        onClick={() => setDiffShowLatex((v) => !v)}
                        className="btn-ghost text-xs"
                      >
                        {diffShowLatex ? "Vis PDF" : "Vis LaTeX"}
                      </button>
                    </div>

                    <div className="card !p-0 overflow-hidden">
                      {diffShowLatex ? (
                        <pre className="p-4 text-xs font-mono text-text-secondary overflow-x-auto max-h-[32rem] overflow-y-auto">
                          {diffLevelLatex(activeLevel)}
                        </pre>
                      ) : diffPdfLoading === activeLevel && !diffPdfUrls[activeLevel] ? (
                        <div className="text-center py-12">
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                            className="w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full mx-auto mb-3"
                          />
                          <p className="text-sm text-text-secondary">Lager PDF...</p>
                        </div>
                      ) : diffPdfUrls[activeLevel] ? (
                        <iframe
                          src={diffPdfUrls[activeLevel]}
                          title={`PDF ${activeLevel}`}
                          className="w-full h-[32rem] bg-white"
                        />
                      ) : (
                        <div className="text-center py-12">
                          <button
                            onClick={() => ensureDiffPdf(activeLevel)}
                            className="btn-secondary text-sm"
                          >
                            <FileText size={14} />
                            Lag PDF-forhåndsvisning
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Download per level (PDF + LaTeX) */}
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => handleDiffDownloadPdf(activeLevel)}
                        disabled={diffPdfLoading === activeLevel}
                        className="btn-primary text-xs flex-1 min-w-[10rem] disabled:opacity-60"
                      >
                        <Download size={12} />
                        {diffPdfLoading === activeLevel ? "Lager PDF..." : "Last ned PDF (dette nivået)"}
                      </button>
                      <button
                        onClick={() => {
                          const c = diffLevelLatex(activeLevel);
                          if (c) downloadText(c, `oppgaver_${activeLevel}.tex`);
                        }}
                        className="btn-secondary text-xs flex-1 min-w-[10rem]"
                      >
                        <Download size={12} />
                        Last ned LaTeX (.tex)
                      </button>
                    </div>
                  </div>
                ) : null}
              </motion.div>
            )}
          </AnimatePresence>

          {exportError && (
            <div className="card mb-6 !border-accent-red/30 bg-accent-red/5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-accent-red mb-1 flex items-center gap-2">
                    <AlertTriangle size={16} />
                    Eksport feilet
                  </h3>
                  <pre className="text-[11px] text-text-secondary whitespace-pre-wrap max-h-40 overflow-y-auto font-mono">
                    {exportError}
                  </pre>
                </div>
                <button
                  onClick={() => setExportError("")}
                  className="btn-ghost text-xs"
                  aria-label="Lukk feilmelding"
                >
                  Lukk
                </button>
              </div>
            </div>
          )}

          {/* Sticky action bar */}
          <div className="fixed bottom-0 left-0 md:left-sidebar-collapsed lg:left-sidebar right-0 z-30 bg-surface/90 backdrop-blur-md border-t border-border">
            <div className="max-w-content mx-auto px-6 py-3 flex items-center gap-2">
              {/* Download dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowDownloads(!showDownloads)}
                  className="btn-primary"
                >
                  <Download size={14} />
                  Last ned
                  <ChevronDown size={14} />
                </button>
                <AnimatePresence>
                  {showDownloads && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      className="absolute bottom-full left-0 mb-2 w-48 bg-surface border border-border rounded-xl shadow-soft-lg overflow-hidden"
                    >
                      <div className="px-3 py-2 border-b border-border">
                        <label className="text-xs text-text-secondary flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={includeSolutionsExport}
                            onChange={(e) => setIncludeSolutionsExport(e.target.checked)}
                            className="rounded border-border"
                          />
                          Inkluder løsningsforslag (lærerkopi)
                        </label>
                      </div>
                      {[
                        { id: "pdf", label: "PDF", icon: <FileText size={14} /> },
                        { id: "pdf-print", label: "PDF (print)", icon: <Printer size={14} /> },
                        { id: "docx", label: "Word", icon: <FileSpreadsheet size={14} /> },
                        { id: "pptx", label: "PowerPoint", icon: <Presentation size={14} /> },
                      ].map((item) => (
                        <button
                          key={item.id}
                          onClick={() => handleExport(item.id)}
                          disabled={exportLoading === item.id}
                          className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-text-secondary hover:bg-surface-elevated hover:text-text-primary transition-colors disabled:opacity-50"
                        >
                          {item.icon}
                          {exportLoading === item.id ? "Eksporterer..." : item.label}
                        </button>
                      ))}
                      <button
                        onClick={() => {
                          setShowDownloads(false);
                          setShowExportModal(true);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-text-secondary hover:bg-surface-elevated hover:text-text-primary border-t border-border transition-colors"
                      >
                        <Download size={14} />
                        Flere eksportvalg
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <button
                onClick={() => toggleLatexEditor()}
                className="btn-secondary"
              >
                <Pencil size={14} />
                Rediger
              </button>

              <button
                onClick={() => {
                  setApprovalChecks({
                    reviewed: false,
                    language: false,
                    classFit: false,
                    mathReviewed: false,
                  });
                  handleDifferentiate();
                }}
                disabled={diffLoading}
                className="btn-secondary"
              >
                <Layers size={14} />
                Differensiér
              </button>

              <button
                onClick={handleShare}
                className="btn-secondary"
                disabled={!canShare || shareLoading}
                title={!canShare ? "Kryss av sjekklisten først" : undefined}
              >
                <Share2 size={14} />
                {shareLoading ? "Oppretter..." : shareUrl ? "Lenke kopiert" : "Del"}
              </button>
              {shareError && (
                <p className="text-xs text-accent-red w-full mt-1" role="alert">
                  {shareError}
                </p>
              )}

              <div className="flex-1" />

              <button
                onClick={handleIngest}
                disabled={ingestStatus === "loading"}
                className="btn-ghost text-xs"
              >
                {ingestStatus && ingestStatus !== "loading"
                  ? ingestStatus
                  : "Lagre i bank"}
              </button>

              <button
                onClick={toggleFavorite}
                className="btn-ghost !p-2"
                aria-label="Merk som favoritt"
              >
                <Star
                  size={16}
                  className={
                    isFavorite
                      ? "fill-accent-orange text-accent-orange animate-star-pop"
                      : "text-text-muted"
                  }
                />
              </button>
            </div>
            <div className="max-w-content mx-auto px-6 pb-3 -mt-2">
              <div className="rounded-lg border border-border bg-surface-elevated/40 p-3">
                <p className="text-xs font-medium mb-2 flex items-center gap-1.5">
                  <CheckSquare size={14} />
                  Kvalitetssjekk før deling
                </p>
                <div className="flex flex-wrap gap-4 text-xs text-text-secondary">
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={approvalChecks.reviewed}
                      onChange={(e) => setApprovalChecks((s) => ({ ...s, reviewed: e.target.checked }))}
                    />
                    Jeg har lest gjennom innholdet
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={approvalChecks.language}
                      onChange={(e) => setApprovalChecks((s) => ({ ...s, language: e.target.checked }))}
                    />
                    Språket passer elevgruppen
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={approvalChecks.classFit}
                      onChange={(e) => setApprovalChecks((s) => ({ ...s, classFit: e.target.checked }))}
                    />
                    Oppgavene passer klassen min
                  </label>
                  {hasMathIssues && (
                    <label className="flex items-center gap-1.5 text-accent-orange">
                      <input
                        type="checkbox"
                        checked={approvalChecks.mathReviewed}
                        onChange={(e) =>
                          setApprovalChecks((s) => ({ ...s, mathReviewed: e.target.checked }))
                        }
                      />
                      Jeg har manuelt sjekket mattepåstandene markert over
                    </label>
                  )}
                </div>
              </div>
            </div>
          </div>
          <ExportModal
            isOpen={showExportModal}
            onClose={() => setShowExportModal(false)}
            latexContent={result.fullDocument}
            pdfStyle={result.generationMeta?.pdfStyle}
          />
        </>
      )}
    </div>
  );
}

/* ---- Sub-components ---- */

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    green: "text-accent-green",
    orange: "text-accent-orange",
    red: "text-accent-red",
    blue: "text-accent-blue",
    purple: "text-accent-purple",
  };

  return (
    <div className="card !p-3">
      <div className="flex items-center gap-1.5 text-text-muted mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className={`text-sm font-semibold ${colorMap[color] || ""}`}>
        {value}
      </div>
    </div>
  );
}

function downloadText(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
