import type { GenerationResultApi } from "@/lib/api";
import type {
  GenerationRequest,
  GenerationResult,
  LayoutReport,
  MathClaimDetail,
} from "@/lib/store";

function mapLayoutReport(raw: unknown): LayoutReport | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const r = raw as Record<string, any>;
  const issues = Array.isArray(r.issues) ? r.issues : [];
  return {
    score: Number(r.score ?? 100),
    overfullCount: Number(r.overfull_count ?? 0),
    underfullCount: Number(r.underfull_count ?? 0),
    maxOverflowPt: Number(r.max_overflow_pt ?? 0),
    undefinedReferences: Number(r.undefined_references ?? 0),
    summary: String(r.summary ?? ""),
    issues: issues.map((i: any) => ({
      kind: String(i.kind ?? ""),
      severity: (i.severity ?? "info") as LayoutReport["issues"][number]["severity"],
      detail: String(i.detail ?? ""),
      overflowPt: Number(i.overflow_pt ?? 0),
    })),
  };
}

function mapClaims(raw: unknown[]): MathClaimDetail[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((c: any) => ({
    claimId: c.claim_id ?? c.claimId ?? "",
    latexExpression: c.latex_expression ?? c.latexExpression ?? "",
    claimType: c.claim_type ?? c.claimType ?? "",
    context: c.context ?? "",
    isCorrect: c.is_correct ?? c.isCorrect ?? null,
    errorMessage: c.error_message ?? c.errorMessage ?? "",
    expectedResult: c.expected_result ?? c.expectedResult ?? "",
    actualResult: c.actual_result ?? c.actualResult ?? "",
  }));
}

function mapContentQuality(raw: unknown): GenerationResult["contentQuality"] {
  if (!raw || typeof raw !== "object") return undefined;
  const report = raw as Record<string, any>;
  const issues = Array.isArray(report.issues) ? report.issues : [];
  return {
    passed: Boolean(report.passed),
    score: Number(report.score ?? 0),
    semanticScore: Number(report.semantic_score ?? 100),
    semanticSummary: String(report.semantic_summary ?? ""),
    missingSubtopics: Array.isArray(report.missing_subtopics)
      ? report.missing_subtopics.map(String)
      : [],
    issues: issues.map((issue: any) => ({
      code: String(issue.code ?? ""),
      severity: issue.severity === "warning" ? "warning" : "error",
      message: String(issue.message ?? ""),
    })),
  };
}

/**
 * Mapper backend GET /generate/{id}/result til frontend-modell.
 */
export function mapApiResultToGenerationResult(
  api: GenerationResultApi | Record<string, unknown>,
  generationMeta?: GenerationRequest
): GenerationResult {
  const raw = api as Record<string, unknown>;
  const mv = (raw.math_verification ?? {}) as Record<string, unknown>;
  const incorrect = mapClaims((mv.errors as unknown[]) ?? []);
  const unparseable = mapClaims((mv.unparseable_claims as unknown[]) ?? []);

  const stepsRaw = (raw.steps as unknown[]) ?? [];
  const steps = stepsRaw.map((s: any) => ({
    agent: String(s.agent ?? ""),
    startedAt: s.started_at ?? s.startedAt ?? "",
    completedAt: s.completed_at ?? s.completedAt ?? null,
    durationSeconds: Number(s.duration_seconds ?? s.durationSeconds ?? 0),
    outputSummary: s.output_summary ?? s.outputSummary ?? "",
    error: s.error ?? "",
    retries: Number(s.retries ?? 0),
  }));

  const latex = (raw.latex_compilation ?? {}) as Record<string, unknown>;

  const statusRaw = String(raw.status ?? "");
  let status: GenerationResult["status"] =
    statusRaw === "pending" ||
    statusRaw === "running" ||
    statusRaw === "completed" ||
    statusRaw === "completed_with_warnings" ||
    statusRaw === "review_required" ||
    statusRaw === "failed"
      ? statusRaw
      : "failed";

  const blockedLegacyResult =
    (status === "completed" || status === "completed_with_warnings") &&
    (raw.source_approved === false || Number(mv.claims_unparseable ?? 0) > 0 || Number(mv.claims_incorrect ?? 0) > 0);
  if (blockedLegacyResult) status = "failed";

  const verificationFailed = status === "failed" &&
    String(raw.warning_reason ?? "").split(",").includes("verification");
  const rawError = String(raw.error ?? "");
  const error = blockedLegacyResult
    ? "Dette resultatet er ikke ferdig verifisert. Generer på nytt for automatisk reparasjon og sluttkontroll."
    : verificationFailed && (!rawError || rawError === "KI-genereringen feilet midlertidig. Prøv igjen.")
      ? "Sluttkontrollen kunne ikke verifisere materialet etter automatiske reparasjonsforsøk. Eksport er stoppet. Prøv en ny generering."
      : rawError;

  return {
    jobId: String(raw.job_id ?? ""),
    status,
    fullDocument: String(raw.full_document ?? ""),
    pdfUrl: String(raw.pdf_path ?? ""),
    pdfBase64: String(raw.pdf_base64 ?? ""),
    usedLatexFallback: Boolean(raw.used_latex_fallback),
    fromCache: Boolean(raw.from_cache),
    differentiatedBasic: String(raw.differentiated_basic ?? ""),
    differentiatedAdvanced: String(raw.differentiated_advanced ?? ""),
    warningReason: String(raw.warning_reason ?? ""),
    contentQuality: mapContentQuality(raw.content_quality),
    layoutReport: mapLayoutReport(raw.layout_report),
    layoutFixAttempts: Number(raw.layout_fix_attempts ?? 0),
    truthPassport:
      raw.truth_passport && typeof raw.truth_passport === "object"
        ? (raw.truth_passport as GenerationResult["truthPassport"])
        : undefined,
    sourceApproved:
      typeof raw.source_approved === "boolean" ? raw.source_approved : undefined,
    teacherApprovedAt:
      typeof raw.teacher_approved_at === "string" ? raw.teacher_approved_at : undefined,
    qualityStopReason:
      typeof raw.quality_stop_reason === "string" ? raw.quality_stop_reason : undefined,
    steps,
    mathVerification: {
      claimsChecked: Number(mv.claims_checked ?? 0),
      claimsCorrect: Number(mv.claims_correct ?? 0),
      claimsIncorrect: Number(mv.claims_incorrect ?? 0),
      claimsUnparseable: Number(mv.claims_unparseable ?? 0),
      allCorrect: Boolean(mv.all_correct),
      summary: String(mv.summary ?? ""),
      incorrectClaims: incorrect,
      unparseableClaims: unparseable,
    },
    latexCompiled: Boolean(raw.pdf_available ?? latex.success),
    totalDuration: Number(raw.total_duration_seconds ?? 0),
    error,
    generationMeta,
    errorCategory: categorizeError(
      error,
      Boolean(latex.success),
      status === "failed"
    ),
  };
}

export type ErrorCategory = "aborted" | "latex" | "model" | "verification" | "unknown";

export function isSuccessfulStatus(status: GenerationResult["status"]): boolean {
  return status === "completed" || status === "completed_with_warnings";
}

export function categorizeError(
  errorMessage: string,
  latexCompiled: boolean,
  failed: boolean
): ErrorCategory {
  if (!failed) return "unknown";
  const m = errorMessage.toLowerCase();
  if (m.includes("avbrutt")) return "aborted";
  if (
    m.includes("sympy") ||
    m.includes("fasit") ||
    m.includes("grunnlov") ||
    m.includes("§1")
  ) {
    return "verification";
  }
  if (
    m.includes("latex") ||
    m.includes("kompiler") ||
    m.includes("pdflatex") ||
    m.includes("compile")
  ) {
    return "latex";
  }
  if (m.includes("verifiser") || m.includes("sluttkontroll")) {
    return "verification";
  }
  if (
    !latexCompiled &&
    (m.includes("pdf") || m.includes("dokument") || m.includes("figur"))
  ) {
    return "latex";
  }
  if (errorMessage) return "model";
  return "unknown";
}

/** Human-readable explanation for a completed_with_warnings result. */
export function warningReasonLabel(reason: string): string {
  const parts = (reason || "").split(",").map((r) => r.trim()).filter(Boolean);
  const hasUnparseable = parts.includes("unparseable");
  const hasIncorrect = parts.includes("incorrect");
  const hasFallback = parts.includes("fallback");
  const hasContentQuality = parts.includes("content_quality");
  const hasLegacyMath = parts.includes("math");

  if (hasIncorrect) {
    return "SymPy fant feil i fasiten. Materialet bør ikke brukes uten manuell kontroll.";
  }
  if (hasUnparseable && hasFallback) {
    return "Noen figurer ble forenklet, og deler av fasiten kunne ikke verifiseres automatisk — lærer kontroll anbefales.";
  }
  if (hasFallback) {
    return "Avanserte figurer (f.eks. TikZ) ble fjernet for å få dokumentet til å kompilere. Tekst og oppgaver er beholdt.";
  }
  if (hasContentQuality) {
    return "Materialet har mangler i pensumdekning eller didaktisk struktur. Se kvalitetsrapporten og kontroller før bruk.";
  }
  if (hasUnparseable || hasLegacyMath) {
    return "Del av fasiten kunne ikke verifiseres automatisk (f.eks. «vis at» eller modellering). Kontroller manuelt før bruk.";
  }
  return "Materialet bør gjennomgås før det deles med elever.";
}

export function errorCategoryLabel(cat: ErrorCategory): string {
  switch (cat) {
    case "aborted":
      return "Avbrutt av bruker";
    case "verification":
      return "Kvalitets- og fasitkontroll";
    case "latex":
      return "LaTeX-kompilering";
    case "model":
      return "Generering / modell";
    default:
      return "Ukjent";
  }
}
