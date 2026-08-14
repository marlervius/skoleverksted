import type { LessonOptions } from "./constants";

const API_URL =
  process.env.NEXT_PUBLIC_VGS_API_URL ||
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/fag`;

interface GenerateLessonParams {
  topic: string;
  subject: string;
  level: string;
  languageLevel: string;
  options: LessonOptions;
  imageData?: string;
  description?: string;
  sourceText?: string;
  useNdla?: boolean;
  interest?: string;
  basisText?: string;
  imageUrlOverride?: string;
  signal?: AbortSignal;
  onProgress?: (message: string) => void;
}

interface GenerateLessonResult {
  blob: Blob;
  filename: string;
  basisText?: string;
  imageUrl?: string;
  worksheetText?: string;
  faktarapportText?: string;
  languageExercises?: Record<string, unknown>;
  warnings?: string[];
  sourceGrounded?: boolean;
  sourceName?: string;
  /** Separate teacher fact-report PDF (spec 2.8), when generated. */
  rapportBlob?: Blob;
  rapportFilename?: string;
  lintIssues?: string[];
}

export interface GenerationReview {
  job_id: string;
  status: "needs_teacher_review" | "source_approved";
  quality_stop_reason: string;
  truth_passport: Record<string, unknown>;
  sources: Array<Record<string, unknown>>;
  claims_for_review: Array<Record<string, unknown>>;
  quarantine: Array<Record<string, unknown>>;
  content: Record<string, unknown>;
  variant_issues?: string[];
  pdf_ready?: boolean;
  filename?: string;
}

export interface GenerationReviewPatch {
  canonical?: Record<string, unknown> | string;
  variants?: Record<string, string>;
  worksheet?: string;
  language_exercises?: Record<string, unknown>;
}

export class ReviewRequiredError extends Error {
  review: GenerationReview;

  constructor(review: GenerationReview) {
    const firstClaim = review.claims_for_review[0];
    const location = firstClaim?.location ? ` (${String(firstClaim.location)})` : "";
    const claim = firstClaim?.claim ? ` Første punkt${location}: ${String(firstClaim.claim)}` : "";
    super(`Produksjonen trenger lærergjennomgang: ${review.quality_stop_reason}.${claim}`);
    this.name = "ReviewRequiredError";
    this.review = review;
  }
}

async function reviewRequest(path: string, body: Record<string, unknown>): Promise<GenerationReview> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Serverfeil: ${res.status}`);
  const passport = data.truth_passport || {};
  const claims = Array.isArray(passport.claims)
    ? passport.claims.filter((claim: Record<string, unknown>) => claim.status !== "verified")
    : [];
  return {
    job_id: String(data.job_id || ""),
    status: data.status === "source_approved" ? "source_approved" : "needs_teacher_review",
    quality_stop_reason: String(data.quality_stop_reason || "truth_layer_unresolved_claims"),
    truth_passport: passport,
    sources: Array.isArray(data.sources || passport.sources) ? (data.sources || passport.sources) : [],
    claims_for_review: Array.isArray(data.claims_for_review) ? data.claims_for_review : claims,
    quarantine: Array.isArray(data.quarantine) ? data.quarantine : [],
    content: data.review_payload || data.content || {},
    variant_issues: Array.isArray(data.variant_issues) ? data.variant_issues : [],
    pdf_ready: Boolean(data.pdf_ready),
    filename: data.filename ? String(data.filename) : undefined,
  };
}

export function rerunGenerationReview(jobId: string, patch: GenerationReviewPatch): Promise<GenerationReview> {
  return reviewRequest(`/generation/${encodeURIComponent(jobId)}/review/rerun`, patch as Record<string, unknown>);
}

export function removeGenerationClaim(jobId: string, claimId: string): Promise<GenerationReview> {
  return reviewRequest(`/generation/${encodeURIComponent(jobId)}/review/remove`, { claim_id: claimId });
}

export async function downloadApprovedGeneration(jobId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_URL}/generate-lesson-download/${encodeURIComponent(jobId)}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail?.message || data.detail || `Serverfeil: ${res.status}`);
  }
  const contentDisposition = res.headers.get("Content-Disposition");
  const filename = contentDisposition?.match(/filename="(.+)"/)?.[1] || "differensiert.pdf";
  return { blob: await res.blob(), filename };
}

export async function generateLesson(
  params: GenerateLessonParams
): Promise<GenerateLessonResult> {
  const { topic, subject, level, languageLevel, options, imageData, description, sourceText, useNdla, interest, basisText, imageUrlOverride, signal, onProgress } = params;

  const body = JSON.stringify({
    topic: topic.trim(),
    subject,
    level,
    language_level: languageLevel !== "none" ? languageLevel : null,
    options,
    image_data: imageData,
    description: description || null,
    source_text: sourceText || null,
    use_ndla: useNdla ?? true,
    interest: interest || null,
    basis_text: basisText || null,
    image_url_override: imageUrlOverride || null,
  });

  return runSseJob(
    `${API_URL}/generate-lesson-start`,
    (id) => `${API_URL}/generate-lesson-download/${id}`,
    (id) => `${API_URL}/generate-lesson-stream/${id}`,
    body,
    signal,
    onProgress,
    "leksjon.pdf",
    (id) => `${API_URL}/generate-lesson-download-rapport/${id}`
  );
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/** Create an object URL from a Blob for inline PDF preview. Caller must revoke it. */
export function createBlobUrl(blob: Blob): string {
  return window.URL.createObjectURL(blob);
}

// ── Shared SSE helper ──────────────────────────────────────────────────────────

async function runSseJob(
  startUrl: string,
  downloadUrl: (jobId: string) => string,
  streamUrl: (jobId: string) => string,
  body: string,
  signal?: AbortSignal,
  onProgress?: (message: string) => void,
  defaultFilename = "dokument.pdf",
  rapportUrl?: (jobId: string) => string
): Promise<GenerateLessonResult> {
  const startRes = await fetch(startUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    signal,
  });

  if (!startRes.ok) {
    const errorData = await startRes.json().catch(() => ({}));
    throw new Error(errorData.detail || `Serverfeil: ${startRes.status}`);
  }

  const { job_id } = await startRes.json();

  let capturedBasisText: string | undefined;
  let capturedImageUrl: string | undefined;
  let capturedWorksheetText: string | undefined;
  let capturedFaktarapportText: string | undefined;
  let capturedLanguageExercises: Record<string, unknown> | undefined;
  let capturedWarnings: string[] | undefined;
  let capturedSourceGrounded: boolean | undefined;
  let capturedSourceName: string | undefined;
  let capturedHasFaktarapport = false;
  let capturedLintIssues: string[] | undefined;

  await new Promise<void>((resolve, reject) => {
    const eventSource = new EventSource(streamUrl(job_id));
    const abortHandler = () => {
      eventSource.close();
      reject(new DOMException("AbortError", "AbortError"));
    };
    signal?.addEventListener("abort", abortHandler);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "progress" && onProgress) {
          onProgress(data.message);
        } else if (data.type === "needs_teacher_review") {
          signal?.removeEventListener("abort", abortHandler);
          eventSource.close();
          const claims = Array.isArray(data.truth_passport?.claims)
            ? data.truth_passport.claims.filter((claim: Record<string, unknown>) => claim.status !== "verified")
            : [];
          reject(new ReviewRequiredError({
            job_id: String(data.job_id || ""),
            status: "needs_teacher_review",
            quality_stop_reason: String(data.quality_stop_reason || "truth_layer_unresolved_claims"),
            truth_passport: data.truth_passport || {},
            sources: Array.isArray(data.truth_passport?.sources) ? data.truth_passport.sources : [],
            claims_for_review: claims,
            quarantine: Array.isArray(data.quarantine) ? data.quarantine : [],
            content: data.review_payload || {},
            variant_issues: Array.isArray(data.variant_issues) ? data.variant_issues : [],
          }));
        } else if (data.type === "done") {
          capturedBasisText = data.basis_text ?? undefined;
          capturedImageUrl = data.image_url ?? undefined;
          capturedWorksheetText = data.worksheet_text ?? undefined;
          capturedFaktarapportText = data.faktarapport_text ?? undefined;
          capturedLanguageExercises = data.language_exercises ?? undefined;
          capturedWarnings = data.warnings ?? undefined;
          capturedSourceGrounded = data.source_grounded ?? undefined;
          capturedSourceName = data.source_name ?? undefined;
          capturedHasFaktarapport = Boolean(data.has_faktarapport);
          capturedLintIssues = data.lint_issues ?? undefined;
          signal?.removeEventListener("abort", abortHandler);
          eventSource.close();
          resolve();
        } else if (data.type === "error") {
          signal?.removeEventListener("abort", abortHandler);
          eventSource.close();
          reject(new Error(data.message || "Ukjent feil under generering"));
        }
      } catch {
        // ignore malformed events
      }
    };

    eventSource.onerror = () => {
      signal?.removeEventListener("abort", abortHandler);
      eventSource.close();
      reject(new Error("Mistet tilkobling til serveren. Prøv igjen."));
    };
  });

  const dlRes = await fetch(downloadUrl(job_id), { signal });
  if (!dlRes.ok) {
    const errorData = await dlRes.json().catch(() => ({}));
    throw new Error(errorData.detail || `Serverfeil: ${dlRes.status}`);
  }

  const blob = await dlRes.blob();
  const contentDisposition = dlRes.headers.get("Content-Disposition");
  let filename = defaultFilename;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="(.+)"/);
    if (match) filename = match[1];
  }

  // Fetch the separate teacher fact-report PDF when the job produced one.
  let rapportBlob: Blob | undefined;
  let rapportFilename: string | undefined;
  if (capturedHasFaktarapport && rapportUrl) {
    try {
      const rapportRes = await fetch(rapportUrl(job_id), { signal });
      if (rapportRes.ok) {
        rapportBlob = await rapportRes.blob();
        rapportFilename = "faktarapport.pdf";
        const cd = rapportRes.headers.get("Content-Disposition");
        const match = cd?.match(/filename="(.+)"/);
        if (match) rapportFilename = match[1];
      }
    } catch {
      // Fact report is optional — never block the main result on it.
    }
  }

  return {
    blob,
    filename,
    rapportBlob,
    rapportFilename,
    lintIssues: capturedLintIssues,
    basisText: capturedBasisText,
    imageUrl: capturedImageUrl,
    worksheetText: capturedWorksheetText,
    faktarapportText: capturedFaktarapportText,
    languageExercises: capturedLanguageExercises,
    warnings: capturedWarnings,
    sourceGrounded: capturedSourceGrounded,
    sourceName: capturedSourceName,
  };
}


// ── Recompile PDF from edited text ────────────────────────────────────────────

interface RecompileLessonParams {
  text: string;
  worksheet: string;
  faktarapport?: string;
  topic: string;
  subject: string;
  level: string;
  languageLevel?: string;
  options: Record<string, boolean>;
  imageUrl?: string;
  languageExercises?: Record<string, unknown>;
  signal?: AbortSignal;
}

export async function recompileLesson(
  params: RecompileLessonParams
): Promise<GenerateLessonResult> {
  const res = await fetch(`${API_URL}/recompile-lesson`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: params.text,
      worksheet: params.worksheet,
      faktarapport: params.faktarapport || null,
      topic: params.topic,
      subject: params.subject,
      level: params.level,
      language_level: params.languageLevel && params.languageLevel !== "none" ? params.languageLevel : null,
      options: params.options,
      image_url: params.imageUrl || null,
      language_exercises: params.languageExercises || null,
    }),
    signal: params.signal,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Serverfeil: ${res.status}`);
  }

  const blob = await res.blob();
  const contentDisposition = res.headers.get("Content-Disposition");
  let filename = "rediger.pdf";
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="(.+)"/);
    if (match) filename = match[1];
  }
  return { blob, filename };
}

// ── Differensiert PDF ─────────────────────────────────────────────────────────

interface GenerateDifferentiatedParams {
  topic: string;
  subject: string;
  level: string;
  languageLevel: string;
  options: LessonOptions;
  imageData?: string;
  description?: string;
  sourceText?: string;
  useNdla?: boolean;
  interest?: string;
  signal?: AbortSignal;
  onProgress?: (message: string) => void;
}

export async function generateDifferentiated(
  params: GenerateDifferentiatedParams
): Promise<GenerateLessonResult> {
  const { topic, subject, level, languageLevel, options, imageData, description, sourceText, useNdla, interest, signal, onProgress } = params;

  const body = JSON.stringify({
    topic: topic.trim(),
    subject,
    level,
    language_level: languageLevel !== "none" ? languageLevel : null,
    options,
    image_data: imageData,
    description: description || null,
    source_text: sourceText || null,
    use_ndla: useNdla ?? true,
    interest: interest || null,
  });

  return runSseJob(
    `${API_URL}/generate-differentiated-start`,
    (id) => `${API_URL}/generate-lesson-download/${id}`,
    (id) => `${API_URL}/generate-lesson-stream/${id}`,
    body,
    signal,
    onProgress,
    "differensiert.pdf"
  );
}

// ── Prøvegenerator ────────────────────────────────────────────────────────────

interface GenerateProveParams {
  topic: string;
  subject: string;
  level: string;
  languageLevel: string;
  includeFasit: boolean;
  description?: string;
  sourceText?: string;
  useNdla?: boolean;
  signal?: AbortSignal;
  onProgress?: (message: string) => void;
}

export async function generateProve(
  params: GenerateProveParams
): Promise<GenerateLessonResult> {
  const { topic, subject, level, languageLevel, includeFasit, description, sourceText, useNdla, signal, onProgress } = params;

  const body = JSON.stringify({
    topic: topic.trim(),
    subject,
    level,
    language_level: languageLevel !== "none" ? languageLevel : null,
    include_fasit: includeFasit,
    description: description || null,
    source_text: sourceText || null,
    use_ndla: useNdla ?? true,
  });

  return runSseJob(
    `${API_URL}/generate-prove-start`,
    (id) => `${API_URL}/generate-prove-download/${id}`,
    (id) => `${API_URL}/generate-prove-stream/${id}`,
    body,
    signal,
    onProgress,
    "prove.pdf"
  );
}

// ── Sekvensplanlegger ─────────────────────────────────────────────────────────

interface GenerateSequenceParams {
  topic: string;
  subject: string;
  level: string;
  antallUker: number;
  timerPerUke: number;
  grepGoals?: string[];
  description?: string;
  signal?: AbortSignal;
  onProgress?: (message: string) => void;
}

export async function generateSequence(
  params: GenerateSequenceParams
): Promise<GenerateLessonResult> {
  const { topic, subject, level, antallUker, timerPerUke, grepGoals, description, signal, onProgress } = params;

  const body = JSON.stringify({
    topic: topic.trim(),
    subject,
    level,
    antall_uker: antallUker,
    timer_per_uke: timerPerUke,
    grep_goals: grepGoals ?? [],
    description: description || null,
  });

  return runSseJob(
    `${API_URL}/generate-sequence-start`,
    (id) => `${API_URL}/generate-sequence-download/${id}`,
    (id) => `${API_URL}/generate-sequence-stream/${id}`,
    body,
    signal,
    onProgress,
    "sekvensplan.pdf"
  );
}

// ── Image candidates for image picker UI ─────────────────────────────────────

export interface ImageCandidate {
  url: string;
  thumbUrl: string;
  title: string;
  attribution: string;
}

export async function fetchImageCandidates(
  topic: string,
  subject: string,
  limit = 5
): Promise<ImageCandidate[]> {
  const url = `${API_URL}/search-images?topic=${encodeURIComponent(topic)}&subject=${encodeURIComponent(subject)}&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();
  return (data.candidates ?? []).map((c: { url: string; thumb_url: string; title: string; attribution: string }) => ({
    url: c.url,
    thumbUrl: c.thumb_url,
    title: c.title,
    attribution: c.attribution,
  }));
}


// ── Download .docx from existing text ────────────────────────────────────────

interface DownloadDocxParams {
  text: string;
  worksheet: string;
  faktarapport?: string;
  topic: string;
  subject: string;
  level: string;
  signal?: AbortSignal;
}

export async function downloadDocx(params: DownloadDocxParams): Promise<void> {
  const res = await fetch(`${API_URL}/generate-docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: params.text,
      worksheet: params.worksheet,
      faktarapport: params.faktarapport || null,
      topic: params.topic,
      subject: params.subject,
      level: params.level,
    }),
    signal: params.signal,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Serverfeil: ${res.status}`);
  }

  const blob = await res.blob();
  const contentDisposition = res.headers.get("Content-Disposition");
  let filename = "leksjon.docx";
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="(.+)"/);
    if (match) filename = match[1];
  }
  downloadBlob(blob, filename);
}


// ── Grep competency goals ─────────────────────────────────────────────────────

export interface CompetencyGoal {
  kode: string;
  tittel: string;
  laereplan: string;
}

export async function fetchCompetencyGoals(
  subject: string,
  level: string
): Promise<CompetencyGoal[]> {
  const url = `${API_URL}/grep/goals?subject=${encodeURIComponent(subject)}&level=${encodeURIComponent(level)}`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();
  return data.goals ?? [];
}
