"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  FileText,
  Loader2,
  Sparkles,
  CheckCircle2,
  Settings2,
  ChevronDown,
  ChevronUp,
  Upload,
  Eye,
  EyeOff,
  ListOrdered,
  Accessibility,
  BookOpen,
  Languages,
} from "lucide-react";

import { GenerationStatus } from "../components/GenerationStatus";
import { HistoryPanel } from "../components/HistoryPanel";
import { LoginForm } from "../components/LoginForm";
import { OptionToggle } from "../components/OptionToggle";
import { PreviewModal } from "../components/PreviewModal";
import { ImageModePicker, type ImageMode } from "@/components/image-mode-picker";
import {
  APP_PASSWORD_STORAGE_KEY,
  DEFAULT_ACCESSIBILITY,
  DEFAULT_OPTIONS,
  HISTORY_KEY,
  LEVELS,
  MAX_HISTORY,
  sortLevelsByCefr,
  SUBJECTS,
} from "../lib/fovConstants";
import type {
  AccessibilityState,
  HistoryItem,
  LessonResponse,
  OptionsState,
  SeriesState,
  Status,
} from "../lib/fovTypes";
import { nextPollDelayMs } from "../lib/polling";

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function HomeContent() {
  const apiUrl =
    process.env.NEXT_PUBLIC_NORSK_API_URL ||
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/norsk`;

  // --- Core form state ---
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState("");
  const [topic, setTopic] = useState("");
  const [difficultyModifier, setDifficultyModifier] = useState<number | null>(null);
  const [options, setOptions] = useState<OptionsState>(DEFAULT_OPTIONS);

  // --- #9 Special instructions ---
  const [specialInstructions, setSpecialInstructions] = useState("");
  const [showInstructions, setShowInstructions] = useState(false);
  const [sourceText, setSourceText] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [showSource, setShowSource] = useState(false);
  const DRAFT_KEY = "skoleverksted_norsk_draft_v1";

  // --- #11 Series ---
  const [seriesEnabled, setSeriesEnabled] = useState(false);
  const [series, setSeries] = useState<SeriesState>({
    lesson_number: 1,
    total_lessons: 4,
    series_theme: "",
  });

  // --- #12 Accessibility ---
  const [accessibility, setAccessibility] = useState<AccessibilityState>(DEFAULT_ACCESSIBILITY);
  const [showAccessibility, setShowAccessibility] = useState(false);

  // --- #3 Dual version ---
  const [dualVersion, setDualVersion] = useState(false);

  // --- Multi-level (2–3 PDFs, same topic, ZIP) ---
  const [multiLevelMode, setMultiLevelMode] = useState(false);
  const [selectedMultiLevels, setSelectedMultiLevels] = useState<string[]>([]);

  // --- #5 Custom image ---
  const [customImage, setCustomImage] = useState<File | null>(null);
  const [imageMode, setImageMode] = useState<ImageMode>("none");
  const [imageError, setImageError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- #7 History ---
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // --- Generation state ---
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [progress, setProgress] = useState<{ step: number; totalSteps: number; message: string } | null>(null);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [isDual, setIsDual] = useState(false);
  const [previewData, setPreviewData] = useState<LessonResponse | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const pollingRef = useRef<boolean>(false);

  // --- Simple password gate (when backend has APP_PASSWORD set) ---
  const [authConfigLoaded, setAuthConfigLoaded] = useState(false);
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [appPassword, setAppPassword] = useState<string | null>(null);
  const [loginPasswordInput, setLoginPasswordInput] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginSubmitting, setLoginSubmitting] = useState(false);

  const clearStoredPassword = useCallback(() => {
    try {
      sessionStorage.removeItem(APP_PASSWORD_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setAppPassword(null);
  }, []);

  const authFetch = useCallback(
    (input: string, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      const project = new URLSearchParams(window.location.search).get("project");
      if (project) headers.set("X-Skoleverksted-Project", project);
      if (passwordRequired && appPassword) {
        headers.set("Authorization", `Bearer ${appPassword}`);
      }
      return fetch(input, { ...init, headers });
    },
    [passwordRequired, appPassword]
  );

  // --- Load history from localStorage on mount ---
  useEffect(() => {
    try {
      const stored = localStorage.getItem(HISTORY_KEY);
      if (stored) {
        setHistory(JSON.parse(stored));
      }
    } catch {
      // ignore corrupt storage
    }
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw) as Record<string, unknown>;
      if (typeof draft.subject === "string") setSubject(draft.subject);
      if (typeof draft.level === "string") setLevel(draft.level);
      if (typeof draft.topic === "string") setTopic(draft.topic);
      if (typeof draft.specialInstructions === "string") setSpecialInstructions(draft.specialInstructions);
      if (typeof draft.sourceText === "string") setSourceText(draft.sourceText);
      if (typeof draft.sourceName === "string") setSourceName(draft.sourceName);
      if (draft.imageMode === "none" || draft.imageMode === "commons" || draft.imageMode === "ai") {
        setImageMode(draft.imageMode);
      }
    } catch { /* ignore corrupt local draft */ }
  }, []);

  // Prefill when opened from a Skoleverksted project or theme pack.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const querySubject = params.get("subject");
    const queryLevel = params.get("languageLevel") || params.get("level");
    const queryTopic = params.get("topic");
    if (querySubject) setSubject(querySubject);
    if (queryLevel) setLevel(queryLevel);
    if (queryTopic) setTopic(queryTopic);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ subject, level, topic, specialInstructions, sourceText, sourceName, imageMode, savedAt: Date.now() }));
    } catch { /* localStorage may be unavailable */ }
  }, [subject, level, topic, specialInstructions, sourceText, sourceName, imageMode]);

  // --- Auth config + restore password from session ---
  useEffect(() => {
    let cancelled = false;
    fetch(`${apiUrl}/auth/config`)
      .then((r) => r.json())
      .then((data: { password_required?: boolean }) => {
        if (cancelled) return;
        const req = !!data.password_required;
        setPasswordRequired(req);
        if (req && typeof window !== "undefined") {
          try {
            const saved = sessionStorage.getItem(APP_PASSWORD_STORAGE_KEY);
            if (saved) setAppPassword(saved);
          } catch {
            /* ignore */
          }
        }
      })
      .catch(() => {
        if (!cancelled) setPasswordRequired(false);
      })
      .finally(() => {
        if (!cancelled) setAuthConfigLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  // --- Cleanup polling on unmount ---
  useEffect(() => {
    return () => {
      pollingRef.current = false;
    };
  }, []);

  // --- Derived validity ---
  const authBlocked = passwordRequired && !appPassword;
  const multiLevelsOk =
    selectedMultiLevels.length >= 2 && selectedMultiLevels.length <= 3;
  const levelOk = multiLevelMode ? multiLevelsOk : !!level;
  const isFormValid = !!(subject && levelOk && topic.trim().length > 0 && !authBlocked);
  const formDisabled = status === "loading" || authBlocked;

  function toggleMultiLevelCheckbox(lv: string) {
    setSelectedMultiLevels((prev) => {
      if (prev.includes(lv)) return prev.filter((x) => x !== lv);
      if (prev.length >= 3) return prev;
      return [...prev, lv];
    });
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginError(null);
    setLoginSubmitting(true);
    try {
      const res = await fetch(`${apiUrl}/auth/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: loginPasswordInput }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setLoginError(
          typeof data.detail === "string" ? data.detail : "Feil passord."
        );
        return;
      }
      try {
        sessionStorage.setItem(APP_PASSWORD_STORAGE_KEY, loginPasswordInput);
      } catch {
        /* ignore */
      }
      setAppPassword(loginPasswordInput);
      setLoginPasswordInput("");
    } finally {
      setLoginSubmitting(false);
    }
  }

  // ---------------------------------------------------------------------------
  // History helpers
  // ---------------------------------------------------------------------------

  function saveToHistory() {
    const sortedMulti =
      multiLevelMode && selectedMultiLevels.length >= 2
        ? sortLevelsByCefr(selectedMultiLevels)
        : null;
    const item: HistoryItem = {
      id: crypto.randomUUID(),
      topic: topic.trim(),
      subject,
      level: sortedMulti?.length ? sortedMulti[0] : level,
      multiLevels: sortedMulti,
      timestamp: Date.now(),
      options,
      difficultyModifier,
      specialInstructions,
      series: seriesEnabled ? series : null,
      accessibility,
    };
    setHistory((prev) => {
      const updated = [item, ...prev].slice(0, MAX_HISTORY);
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
      } catch {
        // Storage full — silently ignore
      }
      return updated;
    });
  }

  function loadFromHistory(item: HistoryItem) {
    setSubject(item.subject);
    if (item.multiLevels && item.multiLevels.length >= 2) {
      setMultiLevelMode(true);
      setSelectedMultiLevels([...item.multiLevels]);
      setDualVersion(false);
      setLevel(item.multiLevels[0] || "");
    } else {
      setMultiLevelMode(false);
      setSelectedMultiLevels([]);
      setLevel(item.level);
    }
    setTopic(item.topic);
    setOptions(item.options);
    setDifficultyModifier(item.difficultyModifier);
    setSpecialInstructions(item.specialInstructions || "");
    if (item.series) {
      setSeriesEnabled(true);
      setSeries(item.series);
    } else {
      setSeriesEnabled(false);
    }
    setAccessibility(item.accessibility || DEFAULT_ACCESSIBILITY);
    setShowHistory(false);
  }

  function clearHistory() {
    setHistory([]);
    try {
      localStorage.removeItem(HISTORY_KEY);
    } catch {
      // ignore
    }
  }

  // ---------------------------------------------------------------------------
  // Image upload handler
  // ---------------------------------------------------------------------------

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    setImageError(null);
    const file = e.target.files?.[0] || null;
    if (!file) {
      setCustomImage(null);
      return;
    }
    const allowed = ["image/jpeg", "image/png", "image/webp"];
    if (!allowed.includes(file.type)) {
      setImageError("Kun JPEG, PNG og WebP er støttet.");
      setCustomImage(null);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setImageError("Bildet er for stort. Maks 5 MB.");
      setCustomImage(null);
      return;
    }
    setCustomImage(file);
  }

  // ---------------------------------------------------------------------------
  // Core fetch helpers
  // ---------------------------------------------------------------------------

  async function startGeneration(): Promise<{
    generation_id: string;
    dual?: boolean;
    zip_download?: boolean;
  }> {
    const baseUrl = `${apiUrl}/generate-lesson`;

    // Multi-level ZIP (2–3 levels)
    if (multiLevelMode && multiLevelsOk && !customImage) {
      const res = await authFetch(`${apiUrl}/generate-multi-lesson`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(),
          subject,
          levels: sortLevelsByCefr(selectedMultiLevels),
          options,
          difficulty_modifier: difficultyModifier,
          special_instructions: specialInstructions || null,
          source_text: sourceText || null,
          source_name: sourceText ? sourceName || "lærerens kildemateriale" : null,
          series: seriesEnabled ? series : null,
          accessibility,
          image_mode: imageMode,
        }),
      });
      if (!res.ok) await throwFromResponse(res);
      return res.json();
    }

    // Dual version (adjacent sub-levels)
    if (dualVersion && !customImage && !multiLevelMode) {
      const res = await authFetch(`${apiUrl}/generate-dual-lesson`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(),
          subject,
          level,
          options,
          difficulty_modifier: difficultyModifier,
          special_instructions: specialInstructions || null,
          source_text: sourceText || null,
          source_name: sourceText ? sourceName || "lærerens kildemateriale" : null,
          series: seriesEnabled ? series : null,
          accessibility,
          image_mode: imageMode,
        }),
      });
      if (!res.ok) await throwFromResponse(res);
      return res.json();
    }

    // Custom image upload
    if (customImage) {
      const fd = new FormData();
      fd.append("topic", topic.trim());
      fd.append("subject", subject);
      fd.append("level", level);
      fd.append("options", JSON.stringify(options));
      if (difficultyModifier !== null) fd.append("difficulty_modifier", String(difficultyModifier));
      if (specialInstructions) fd.append("special_instructions", specialInstructions);
      if (sourceText) fd.append("source_text", sourceText);
      if (sourceText) fd.append("source_name", sourceName || "lærerens kildemateriale");
      if (seriesEnabled) fd.append("series", JSON.stringify(series));
      fd.append("accessibility", JSON.stringify(accessibility));
      fd.append("image", customImage);

      const res = await authFetch(`${apiUrl}/generate-lesson-with-image`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) await throwFromResponse(res);
      return res.json();
    }

    // Standard generation
    const res = await authFetch(baseUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: topic.trim(),
        subject,
        level,
        options,
        difficulty_modifier: difficultyModifier,
        special_instructions: specialInstructions || null,
        source_text: sourceText || null,
        source_name: sourceText ? sourceName || "lærerens kildemateriale" : null,
        series: seriesEnabled ? series : null,
        accessibility,
        image_mode: imageMode,
      }),
    });
    if (!res.ok) await throwFromResponse(res);
    return res.json();
  }

  async function throwFromResponse(res: Response): Promise<never> {
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      clearStoredPassword();
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Ikke innlogget eller feil passord. Prøv igjen."
      );
    }
    const statusMessages: Record<number, string> = {
      413: "Bildet er for stort. Maks 5 MB.",
      415: "Ugyldig bildeformat. Bruk JPEG, PNG eller WebP.",
      422: "Ugyldig forespørsel. Sjekk alle feltene og prøv igjen.",
      500: "En serverfeil oppstod. Prøv igjen om litt.",
      503: "Tjenesten er midlertidig utilgjengelig. Prøv igjen om litt.",
      429: "For mange forespørsler. Vent litt og prøv igjen.",
    };
    throw new Error(
      data.detail || statusMessages[res.status] || `Feil: ${res.status}`
    );
  }

  // ---------------------------------------------------------------------------
  // Submit handler
  // ---------------------------------------------------------------------------

  async function startPreview(): Promise<{ generation_id: string }> {
    const res = await authFetch(`${apiUrl}/generate-lesson-json`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: topic.trim(),
        subject,
        level,
        options,
        difficulty_modifier: difficultyModifier,
        special_instructions: specialInstructions || null,
        source_text: sourceText || null,
        source_name: sourceText ? sourceName || "lærerens kildemateriale" : null,
        series: seriesEnabled ? series : null,
        accessibility,
        image_mode: imageMode,
      }),
    });
    if (!res.ok) await throwFromResponse(res);
    return res.json();
  }

  const handlePreview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid) return;

    setStatus("loading");
    setErrorMessage("");
    setProgress({ step: 0, totalSteps: 2, message: "Starter forhåndsvisning..." });
    setGenerationId(null);
    pollingRef.current = true;

    try {
      const data = await startPreview();
      const gId = data.generation_id;
      setGenerationId(gId);

      saveToHistory();
      pollPreviewProgress(gId);
    } catch (error) {
      console.error("Error starting preview:", error);
      setStatus("error");
      setProgress(null);
      pollingRef.current = false;
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Kunne ikke starte forhåndsvisning. Prøv igjen."
      );
    }
  };

  const generatePdfFromPreview = async () => {
    if (!previewData) return;

    setStatus("loading");
    setErrorMessage("");
    setProgress({ step: 0, totalSteps: 3, message: "Starter PDF-generering..." });
    setGenerationId(null);
    pollingRef.current = true;
    setIsPreviewing(false);

    try {
      const res = await authFetch(`${apiUrl}/generate-pdf-from-json`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: previewData.topic,
          subject: previewData.subject,
          level: previewData.level,
          text: previewData.text,
          worksheet: previewData.worksheet,
          image_url: previewData.image_url,
          image_mode: previewData.image_mode || imageMode,
          image_caption: previewData.image_caption || "",
          image_credit: previewData.image_credit || "",
          image_source_page: previewData.image_source_page || null,
          language_exercises: previewData.language_exercises,
          options,
          accessibility,
        }),
      });

      if (!res.ok) await throwFromResponse(res);
      const data = await res.json();
      const gId = data.generation_id;
      setGenerationId(gId);

      // Re-use standard pollProgress since the final step downloads PDF
      // Note: We pass dual=false
      const pollFromPreview = async (id: string, attempt = 0) => {
        if (!pollingRef.current) return;
        try {
          const statusRes = await authFetch(`${apiUrl}/generation-status/${id}`);
          if (!statusRes.ok) throw new Error("Kunne ikke hente status");

          const progressData = await statusRes.json();
          setProgress({
            step: progressData.step,
            totalSteps: progressData.total_steps,
            message: progressData.message,
          });

          if (progressData.step === 3) {
            pollingRef.current = false;
            await downloadPDF(id);
          } else if (progressData.step === -1) {
            pollingRef.current = false;
            throw new Error(progressData.message);
          } else if (pollingRef.current) {
            setTimeout(
              () => pollFromPreview(id, attempt + 1),
              nextPollDelayMs(attempt)
            );
          }
        } catch (error) {
          if (pollingRef.current) {
            console.error("Error polling progress:", error);
            setStatus("error");
            setProgress(null);
            pollingRef.current = false;
            setErrorMessage(
              error instanceof Error ? error.message : "Feil under generering. Prøv igjen."
            );
          }
        }
      };

      pollFromPreview(gId);
    } catch (error) {
      console.error("Error generating from preview:", error);
      setStatus("error");
      setProgress(null);
      pollingRef.current = false;
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Kunne ikke generere PDF. Prøv igjen."
      );
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid) return;

    setStatus("loading");
    setErrorMessage("");
    setProgress({ step: 0, totalSteps: 4, message: "Starter generering..." });
    setGenerationId(null);
    pollingRef.current = true;

    try {
      const data = await startGeneration();
      const gId = data.generation_id;
      setGenerationId(gId);
      setIsDual(!!data.dual || !!data.zip_download);

      saveToHistory();
      pollProgress(gId, !!data.dual);
    } catch (error) {
      console.error("Error starting generation:", error);
      setStatus("error");
      setProgress(null);
      pollingRef.current = false;
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Kunne ikke starte generering. Prøv igjen."
      );
    }
  };

  // ---------------------------------------------------------------------------
  // Polling
  // ---------------------------------------------------------------------------

  const pollPreviewProgress = async (gId: string, attempt = 0) => {
    if (!pollingRef.current) return;

    try {
      const res = await authFetch(`${apiUrl}/generation-status/${gId}`);
      if (!res.ok) throw new Error("Kunne ikke hente status");

      const progressData = await res.json();
      setProgress({
        step: progressData.step,
        totalSteps: progressData.total_steps,
        message: progressData.message,
      });

      if (progressData.step === 2) {
        pollingRef.current = false;
        await downloadPreviewJson(gId);
      } else if (progressData.step === -1) {
        pollingRef.current = false;
        throw new Error(progressData.message);
      } else if (pollingRef.current) {
        setTimeout(
          () => pollPreviewProgress(gId, attempt + 1),
          nextPollDelayMs(attempt)
        );
      }
    } catch (error) {
      if (pollingRef.current) {
        console.error("Error polling preview progress:", error);
        setStatus("error");
        setProgress(null);
        pollingRef.current = false;
        setErrorMessage(
          error instanceof Error ? error.message : "Feil under generering. Prøv igjen."
        );
      }
    }
  };

  const pollProgress = async (gId: string, dual: boolean, attempt = 0) => {
    if (!pollingRef.current) return;

    try {
      const res = await authFetch(`${apiUrl}/generation-status/${gId}`);
      if (!res.ok) throw new Error("Kunne ikke hente status");

      const progressData = await res.json();
      setProgress({
        step: progressData.step,
        totalSteps: progressData.total_steps,
        message: progressData.message,
      });

      if (progressData.step === 4) {
        pollingRef.current = false;
        if (dual) {
          await downloadZip(gId);
        } else {
          await downloadPDF(gId);
        }
      } else if (progressData.step === -1) {
        pollingRef.current = false;
        throw new Error(progressData.message);
      } else if (pollingRef.current) {
        setTimeout(
          () => pollProgress(gId, dual, attempt + 1),
          nextPollDelayMs(attempt)
        );
      }
    } catch (error) {
      if (pollingRef.current) {
        console.error("Error polling progress:", error);
        setStatus("error");
        setProgress(null);
        pollingRef.current = false;
        setErrorMessage(
          error instanceof Error ? error.message : "Feil under generering. Prøv igjen."
        );
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Download helpers
  // ---------------------------------------------------------------------------

  async function downloadPreviewJson(gId: string) {
    try {
      const res = await authFetch(`${apiUrl}/download-json/${gId}`);
      if (!res.ok) throw new Error("Kunne ikke hente forhåndsvisning");

      const data = await res.json();
      setPreviewData(data);
      setIsPreviewing(true);
      setStatus("idle");
      setProgress(null);
    } catch (error) {
      console.error("Error fetching preview:", error);
      setStatus("error");
      setProgress(null);
      setErrorMessage(error instanceof Error ? error.message : "Kunne ikke laste forhåndsvisning.");
    }
  }

  async function downloadFile(url: string, defaultName: string) {
    const res = await authFetch(url);
    if (!res.ok) throw new Error(`Kunne ikke laste ned fil (${res.status})`);
    const blob = await res.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;

    const contentDisposition = res.headers.get("Content-Disposition");
    let filename = defaultName;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/);
      if (match) filename = decodeURIComponent(match[1]);
    }
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(objectUrl);
  }

  const downloadPDF = async (gId: string) => {
    try {
      await downloadFile(`${apiUrl}/download-pdf/${gId}`, "leksjon.pdf");
      setStatus("success");
      setProgress(null);
      pollingRef.current = false;
      setTimeout(() => setStatus("idle"), 3000);
    } catch (error) {
      console.error("Error downloading PDF:", error);
      setStatus("error");
      setProgress(null);
      pollingRef.current = false;
      setErrorMessage(
        error instanceof Error ? error.message : "Kunne ikke laste ned PDF. Prøv igjen."
      );
    }
  };

  const downloadZip = async (gId: string) => {
    try {
      await downloadFile(`${apiUrl}/download-zip/${gId}`, "leksjoner_dual.zip");
      setStatus("success");
      setProgress(null);
      pollingRef.current = false;
      setTimeout(() => setStatus("idle"), 3000);
    } catch (error) {
      console.error("Error downloading ZIP:", error);
      setStatus("error");
      setProgress(null);
      pollingRef.current = false;
      setErrorMessage(
        error instanceof Error ? error.message : "Kunne ikke laste ned ZIP. Prøv igjen."
      );
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!authConfigLoaded) {
    return (
      <main className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-accent-600" aria-label="Laster" />
      </main>
    );
  }

  if (passwordRequired && !appPassword) {
    return (
      <LoginForm
        loginPasswordInput={loginPasswordInput}
        setLoginPasswordInput={setLoginPasswordInput}
        loginError={loginError}
        loginSubmitting={loginSubmitting}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <main className="min-h-screen bg-bg">
      <div className="mx-auto max-w-2xl px-4 py-8 sm:py-10">
        {/* Page intro */}
        <div className="mb-6 relative">
          {passwordRequired && appPassword && (
            <button
              type="button"
              onClick={() => {
                clearStoredPassword();
                setLoginPasswordInput("");
              }}
              className="absolute right-0 top-0 text-xs text-stone-400 hover:text-stone-600 underline"
            >
              Logg ut
            </button>
          )}
          <h1 className="text-xl font-semibold text-stone-900 tracking-tight">
            Norsklæring
          </h1>
          <p className="text-stone-500 text-sm mt-1">
            Tydelige PDF-læringsark tilpasset fag og språknivå — for voksne som lærer norsk.
          </p>
        </div>

        <div className="w-full">
          <HistoryPanel
            history={history}
            showHistory={showHistory}
            setShowHistory={setShowHistory}
            onSelect={loadFromHistory}
            onClear={clearHistory}
          />

          <form onSubmit={handleSubmit}>
            <div className="surface-card p-6 sm:p-7">

              {/* Subject */}
              <div className="mb-5">
                <label className="field-label">
                  <BookOpen className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  Fag
                </label>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="input-field appearance-none cursor-pointer"
                  disabled={formDisabled}
                >
                  <option value="">Velg fag...</option>
                  {SUBJECTS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.icon} {s.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Level */}
              <div className="mb-5">
                <label className="field-label">
                  <Languages className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  Språknivå (CEFR)
                </label>
                {!multiLevelMode && (
                  <select
                    value={level}
                    onChange={(e) => setLevel(e.target.value)}
                    className="input-field appearance-none cursor-pointer"
                    disabled={formDisabled}
                  >
                    <option value="">Velg nivå...</option>
                    {LEVELS.map((l) => (
                      <option key={l.value} value={l.value}>
                        {l.label}
                      </option>
                    ))}
                  </select>
                )}

                <div className={`${multiLevelMode ? "mt-0" : "mt-4"}`}>
                  <OptionToggle
                    label="Flere nivåer samtidig (2–3 PDF-er)"
                    checked={multiLevelMode}
                    onChange={(v) => {
                      setMultiLevelMode(v);
                      if (v) {
                        setDualVersion(false);
                        setSelectedMultiLevels((prev) =>
                          prev.length > 0 ? prev : level ? [level] : []
                        );
                      } else {
                        setSelectedMultiLevels([]);
                      }
                    }}
                    disabled={formDisabled || !!customImage || dualVersion}
                    description="Samme tema og innstillinger — én PDF per nivå, pakket i én ZIP"
                  />
                </div>

                {multiLevelMode && (
                  <div className="mt-3 p-4 bg-accent-50 border border-accent-200 rounded-lg space-y-2">
                    <p className="text-xs text-stone-600">
                      Kryss av 2 eller 3 nivåer (f.eks. A1.1, B1.1 og B2.1 for differensiering).
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {LEVELS.map((l) => {
                        const checked = selectedMultiLevels.includes(l.value);
                        const maxed = !checked && selectedMultiLevels.length >= 3;
                        return (
                          <label
                            key={l.value}
                            className={`flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer transition-colors text-sm ${
                              checked
                                ? "border-accent-300 bg-white text-accent-800"
                                : maxed
                                  ? "border-stone-200 bg-stone-50 text-stone-400 cursor-not-allowed"
                                  : "border-stone-200 bg-white text-stone-600 hover:border-stone-300"
                            }`}
                          >
                            <input
                              type="checkbox"
                              className="rounded border-stone-300 text-accent-600 focus:ring-accent-600/30"
                              checked={checked}
                              disabled={formDisabled || maxed}
                              onChange={() => toggleMultiLevelCheckbox(l.value)}
                            />
                            <span className="truncate">{l.label}</span>
                          </label>
                        );
                      })}
                    </div>
                    <p
                      className={`text-xs ${
                        multiLevelsOk ? "text-accent-700" : "text-amber-600"
                      }`}
                    >
                      Valgt: {selectedMultiLevels.length} av 3
                      {!multiLevelsOk &&
                        selectedMultiLevels.length > 0 &&
                        " — trenger minst 2 nivåer"}
                    </p>
                  </div>
                )}
              </div>

              {/* Difficulty Modifier */}
              {(level || (multiLevelMode && selectedMultiLevels.length > 0)) && (
                <div className="mb-5">
                  <label className="field-label mb-3">
                    <Settings2 className="w-4 h-4 text-accent-600" aria-hidden="true" />
                    Vanskelighetsgrad (valgfritt)
                  </label>
                  <div className="px-4 py-3 bg-white border border-stone-200 rounded-lg">
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-stone-500 whitespace-nowrap">Enklere</span>
                      <input
                        type="range"
                        min="-2"
                        max="2"
                        value={difficultyModifier ?? 0}
                        onChange={(e) => setDifficultyModifier(parseInt(e.target.value) || null)}
                        className="flex-1 h-2 cursor-pointer accent-accent-600"
                        disabled={formDisabled}
                      />
                      <span className="text-xs text-stone-500 whitespace-nowrap">Vanskeligere</span>
                    </div>
                    <div className="flex justify-between text-xs text-stone-400 mt-2">
                      <span>-2</span><span>-1</span>
                      <span className="text-stone-700 font-medium">Standard</span>
                      <span>+1</span><span>+2</span>
                    </div>
                    {difficultyModifier !== null && difficultyModifier !== 0 && (
                      <div className="flex items-center justify-between mt-2">
                        <p className="text-xs text-accent-700">
                          Justering: {difficultyModifier > 0 ? "+" : ""}{difficultyModifier}
                          {difficultyModifier === -2 && " (Svært enkelt)"}
                          {difficultyModifier === -1 && " (Litt enklere)"}
                          {difficultyModifier === 1 && " (Litt vanskeligere)"}
                          {difficultyModifier === 2 && " (Svært vanskelig)"}
                        </p>
                        <button
                          type="button"
                          onClick={() => setDifficultyModifier(null)}
                          className="text-xs text-stone-400 hover:text-stone-600 underline"
                          disabled={formDisabled}
                        >
                          Tilbakestill
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Topic / Profession */}
              <div className="mb-5">
                <label className="field-label">
                  <FileText className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  {subject === "Utdanningsvalg" ? "Hvilket yrke vil du utforske?" : "Tema"}
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder={subject === "Utdanningsvalg" ? "F.eks. Sykepleier, Elektriker, Ingeniør..." : "F.eks. Det Norske Storting, Fotosyntese..."}
                  className="input-field"
                  disabled={formDisabled}
                />
              </div>

              {/* ---------------------------------------------------------------- */}
              {/* #9 Special instructions                                          */}
              {/* ---------------------------------------------------------------- */}
              <div className="mb-5">
                <button
                  type="button"
                  onClick={() => setShowInstructions((v) => !v)}
                  className="flex items-center gap-2 text-sm text-stone-500 hover:text-stone-700 transition-colors"
                  disabled={formDisabled}
                >
                  {showInstructions ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  <span>Spesielle instrukser til AI (valgfritt)</span>
                  {showInstructions ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
                {showInstructions && (
                  <div className="mt-2">
                    <textarea
                      value={specialInstructions}
                      onChange={(e) => setSpecialInstructions(e.target.value.slice(0, 500))}
                      placeholder="F.eks. Fokuser på norrøn mytologi, unngå bruk av presens perfektum, inkluder minst to eksempler fra dagliglivet..."
                      rows={3}
                      className="input-field text-sm resize-none"
                      disabled={formDisabled}
                    />
                    <p className={`text-xs mt-1 text-right ${specialInstructions.length >= 480 ? "text-amber-600" : "text-stone-400"}`}>
                      {specialInstructions.length}/500 tegn
                    </p>
                  </div>
                )}
              </div>

              <div className="mb-5">
                <button
                  type="button"
                  onClick={() => setShowSource((value) => !value)}
                  className="flex items-center gap-2 text-sm text-stone-500 transition-colors hover:text-stone-700"
                  disabled={formDisabled}
                >
                  <BookOpen className="h-4 w-4 text-accent-600" />
                  <span>Kildegrunnlag fra lærer (anbefalt)</span>
                  {showSource ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
                {showSource && (
                  <div className="mt-3 space-y-2 rounded-lg border border-stone-200 bg-stone-50/60 p-4">
                    <input
                      value={sourceName}
                      onChange={(e) => setSourceName(e.target.value.slice(0, 160))}
                      placeholder="Kildenavn, for eksempel NDLA-artikkel eller lærerens notat"
                      className="input-field text-sm"
                      disabled={formDisabled}
                    />
                    <textarea
                      value={sourceText}
                      onChange={(e) => setSourceText(e.target.value.slice(0, 5000))}
                      placeholder="Lim inn et autoritativt utdrag. Kildebaserte faktapåstander merkes med [K] i resultatet."
                      rows={5}
                      className="input-field resize-y text-sm"
                      disabled={formDisabled}
                    />
                    <p className="text-right text-xs text-stone-400">{sourceText.length}/5000 tegn</p>
                  </div>
                )}
              </div>

              {/* Modular Options */}
              <div className="mb-5 panel">
                <label className="flex items-center gap-2 text-sm font-semibold text-stone-800 mb-3">
                  <Settings2 className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  Tilpass innhold
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  <OptionToggle label="Mye fakta (Fordypning)" checked={options.deep_dive}
                    onChange={(val) => setOptions({ ...options, deep_dive: val })}
                    disabled={formDisabled} description="Ca. 800 ord tekst" />
                  <OptionToggle label="Faktaoppgaver" checked={options.comprehension_tasks}
                    onChange={(val) => setOptions({ ...options, comprehension_tasks: val })}
                    disabled={formDisabled} />
                  <OptionToggle label="Grammatikk" checked={options.grammar_tasks}
                    onChange={(val) => setOptions({ ...options, grammar_tasks: val })}
                    disabled={formDisabled} />
                  <OptionToggle label="Ordoppgaver" checked={options.vocabulary_tasks}
                    onChange={(val) => setOptions({ ...options, vocabulary_tasks: val })}
                    disabled={formDisabled} />
                  <OptionToggle label="Diskusjon" checked={options.discussion_tasks}
                    onChange={(val) => setOptions({ ...options, discussion_tasks: val })}
                    disabled={formDisabled} />
                  <OptionToggle label="Inkluder Fasit" checked={options.teacher_key}
                    onChange={(val) => setOptions({ ...options, teacher_key: val })}
                    disabled={formDisabled} highlight />
                </div>
              </div>

              {/* Advanced Modules */}
              <div className="mb-5 panel">
                <label className="flex items-center gap-2 text-sm font-semibold text-stone-800 mb-3">
                  <Sparkles className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  Avanserte moduler
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  <OptionToggle label="Rollespill" checked={options.role_play}
                    onChange={(val) => setOptions({ ...options, role_play: val })}
                    disabled={formDisabled} description="Dialog mellom Person A og B" advanced />
                  <OptionToggle label="Bildebeskrivelse" checked={options.image_description}
                    onChange={(val) => setOptions({ ...options, image_description: val })}
                    disabled={formDisabled} description="Norskprøve-oppgaver om bildet" advanced />
                  <OptionToggle label="Skriveramme" checked={options.writing_frame}
                    onChange={(val) => setOptions({ ...options, writing_frame: val })}
                    disabled={formDisabled} description="Setningsstartere og modelltekst" advanced />
                  <OptionToggle label="Kulturblikk" checked={options.cultural_comparison}
                    onChange={(val) => setOptions({ ...options, cultural_comparison: val })}
                    disabled={formDisabled} description="Sammenlign Norge og hjemlandet" advanced />
                  <OptionToggle label="Virkelig case" checked={options.real_case}
                    onChange={(val) => setOptions({ ...options, real_case: val })}
                    disabled={formDisabled} description="E-post, SMS eller offisielt brev" advanced />
                </div>
              </div>

              {/* ---------------------------------------------------------------- */}
              {/* #11 Series                                                        */}
              {/* ---------------------------------------------------------------- */}
              <div className="mb-5">
                <button
                  type="button"
                  onClick={() => setSeriesEnabled((v) => !v)}
                  className="flex items-center gap-2 w-full text-left"
                  disabled={formDisabled}
                >
                  <div className={`p-1.5 rounded-md ${seriesEnabled ? "bg-accent-100" : "bg-stone-100"}`}>
                    <ListOrdered className={`w-4 h-4 ${seriesEnabled ? "text-accent-700" : "text-stone-400"}`} />
                  </div>
                  <span className={`text-sm font-medium ${seriesEnabled ? "text-accent-800" : "text-stone-500"}`}>
                    Del av en serie (valgfritt)
                  </span>
                  {seriesEnabled ? <ChevronUp className="w-3 h-3 text-stone-400 ml-auto" /> : <ChevronDown className="w-3 h-3 text-stone-400 ml-auto" />}
                </button>

                {seriesEnabled && (
                  <div className="mt-3 p-4 bg-accent-50 border border-accent-200 rounded-lg space-y-3">
                    <div>
                      <label className="text-xs text-stone-600 mb-1 block">Serietema</label>
                      <input
                        type="text"
                        value={series.series_theme}
                        onChange={(e) => setSeries({ ...series, series_theme: e.target.value.slice(0, 100) })}
                        placeholder="F.eks. Norsk arbeidsliv og samfunn"
                        className="input-field text-sm"
                        disabled={formDisabled}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-stone-600 mb-1 block">Leksjon nr.</label>
                        <input
                          type="number"
                          min={1}
                          max={20}
                          value={series.lesson_number}
                          onChange={(e) => setSeries({ ...series, lesson_number: Math.max(1, Math.min(20, parseInt(e.target.value) || 1)) })}
                          className="input-field text-sm"
                          disabled={formDisabled}
                        />
                      </div>
                      <div>
                        <label className="text-xs text-stone-600 mb-1 block">Totalt antall</label>
                        <input
                          type="number"
                          min={2}
                          max={20}
                          value={series.total_lessons}
                          onChange={(e) => setSeries({ ...series, total_lessons: Math.max(2, Math.min(20, parseInt(e.target.value) || 2)) })}
                          className="input-field text-sm"
                          disabled={formDisabled}
                        />
                      </div>
                    </div>
                    <p className="text-xs text-stone-500">
                      Leksjon {series.lesson_number} av {series.total_lessons} i &quot;{series.series_theme || "..."}&quot;
                    </p>
                  </div>
                )}
              </div>

              {/* ---------------------------------------------------------------- */}
              {/* #12 Accessibility                                                 */}
              {/* ---------------------------------------------------------------- */}
              <div className="mb-5">
                <button
                  type="button"
                  onClick={() => setShowAccessibility((v) => !v)}
                  className="flex items-center gap-2 w-full text-left"
                  disabled={formDisabled}
                >
                  <div className={`p-1.5 rounded-md ${showAccessibility ? "bg-accent-100" : "bg-stone-100"}`}>
                    <Accessibility className={`w-4 h-4 ${showAccessibility ? "text-accent-700" : "text-stone-400"}`} />
                  </div>
                  <span className={`text-sm font-medium ${showAccessibility ? "text-accent-800" : "text-stone-500"}`}>
                    Tilgjengelighetsalternativer
                  </span>
                  {showAccessibility ? <ChevronUp className="w-3 h-3 text-stone-400 ml-auto" /> : <ChevronDown className="w-3 h-3 text-stone-400 ml-auto" />}
                </button>

                {showAccessibility && (
                  <div className="mt-3 p-4 bg-accent-50 border border-accent-200 rounded-lg">
                    <div className="grid grid-cols-1 gap-2">
                      <OptionToggle
                        label="Dysleksi-vennlig font"
                        checked={accessibility.dyslexia_font}
                        onChange={(val) => setAccessibility({ ...accessibility, dyslexia_font: val })}
                        disabled={formDisabled}
                        description="Bruker OpenDyslexic i PDF"
                      />
                      <OptionToggle
                        label="Høy kontrast"
                        checked={accessibility.high_contrast}
                        onChange={(val) => setAccessibility({ ...accessibility, high_contrast: val })}
                        disabled={formDisabled}
                        description="Svart/hvitt uten bakgrunnsfarger"
                      />
                      <OptionToggle
                        label="Stor skrift"
                        checked={accessibility.large_print}
                        onChange={(val) => setAccessibility({ ...accessibility, large_print: val })}
                        disabled={formDisabled}
                        description="13pt i stedet for 11pt"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* ---------------------------------------------------------------- */}
              {/* Pedagogical image mode                                             */}
              {/* ---------------------------------------------------------------- */}
              <div className="mb-5">
                <ImageModePicker
                  value={imageMode}
                  onChange={setImageMode}
                  disabled={formDisabled || !!customImage}
                  compact
                />
              </div>

              {/* ---------------------------------------------------------------- */}
              {/* #5 Custom image upload                                            */}
              {/* ---------------------------------------------------------------- */}
              <div className="mb-5">
                <label className="field-label">
                  <Upload className="w-4 h-4 text-accent-600" aria-hidden="true" />
                  Eget bilde (valgfritt)
                </label>
                <div
                  className={`relative border-2 border-dashed rounded-lg px-4 py-5 text-center transition-colors
                    ${customImage ? "border-accent-300 bg-accent-50" : "border-stone-300 bg-white hover:border-stone-400"}`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleImageChange}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={formDisabled || multiLevelMode}
                  />
                  {customImage ? (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <CheckCircle2 className="w-4 h-4 text-accent-700 shrink-0" />
                        <span className="text-accent-800 text-sm truncate">{customImage.name}</span>
                        <span className="text-stone-400 text-xs shrink-0">({(customImage.size / 1024).toFixed(0)} KB)</span>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setCustomImage(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
                        className="text-xs text-stone-400 hover:text-red-600 ml-2 shrink-0 transition-colors"
                        disabled={formDisabled}
                      >
                        Fjern
                      </button>
                    </div>
                  ) : (
                    <div>
                      <Upload className="w-6 h-6 text-stone-400 mx-auto mb-1" />
                      <p className="text-sm text-stone-500">
                        Klikk eller dra et bilde hit
                      </p>
                      <p className="text-xs text-stone-400 mt-0.5">JPEG, PNG, WebP · maks 5 MB</p>
                    </div>
                  )}
                </div>
                {imageError && (
                  <p className="text-xs text-red-600 mt-1">{imageError}</p>
                )}
                {multiLevelMode && (
                  <p className="text-xs text-stone-500 mt-2">
                    Flernivå støttes ikke sammen med eget bilde — skru av «Flere nivåer» for å laste opp bilde.
                  </p>
                )}
                {customImage && (
                  <p className="text-xs text-stone-500 mt-1">
                    Bildemodusen hoppes over – bildet ditt brukes i PDF-en.
                  </p>
                )}
              </div>

              {/* ---------------------------------------------------------------- */}
              {/* #3 Dual version toggle                                            */}
              {/* ---------------------------------------------------------------- */}
              {!customImage && (
                <div className="mb-8">
                  <OptionToggle
                    label="Generer to versjoner (nabonivåer)"
                    checked={dualVersion}
                    onChange={(v) => {
                      setDualVersion(v);
                      if (v) {
                        setMultiLevelMode(false);
                        setSelectedMultiLevels([]);
                      }
                    }}
                    disabled={formDisabled || multiLevelMode}
                    description={
                      multiLevelMode
                        ? "Skru av flernivå for å bruke nabonivåer"
                        : level
                          ? `Lager PDF for begge ${level.slice(0, 2)}-undernivåene i én ZIP`
                          : "Velg nivå først"
                    }
                  />
                  {dualVersion && (
                    <p className="text-xs text-stone-500 mt-2 px-1">
                      Du laster ned en ZIP med én PDF per undernivå.
                    </p>
                  )}
                </div>
              )}

              {/* Submit / Preview */}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handlePreview}
                  disabled={
                    !isFormValid ||
                    status === "loading" ||
                    multiLevelMode ||
                    dualVersion ||
                    !!customImage
                  }
                  className={`
                    flex-1 py-3.5 px-6 rounded-lg font-medium text-base
                    flex items-center justify-center gap-2 border
                    transition-colors focus:outline-none focus:ring-2 focus:ring-stone-300
                    ${
                      status === "loading"
                        ? "bg-stone-100 text-stone-400 border-stone-200 cursor-wait"
                        : isFormValid && !multiLevelMode && !dualVersion && !customImage
                        ? "bg-white text-stone-700 border-stone-300 hover:border-stone-400 hover:bg-stone-50"
                        : "bg-stone-100 text-stone-400 border-stone-200 cursor-not-allowed"
                    }
                  `}
                >
                  <FileText className="w-5 h-5" />
                  <span>Forhåndsvis først</span>
                </button>
                <button
                  type="submit"
                  disabled={!isFormValid || status === "loading"}
                  className={`
                    flex-1 py-3.5 px-6 rounded-lg font-semibold text-base
                    flex items-center justify-center gap-2
                    transition-colors focus:outline-none focus:ring-2 focus:ring-accent-600/30
                    ${
                      status === "loading"
                        ? "bg-stone-200 text-stone-500 cursor-wait"
                        : status === "success"
                        ? "bg-accent-700 text-white"
                        : isFormValid
                        ? "bg-accent-700 hover:bg-accent-800 text-white"
                        : "bg-stone-200 text-stone-400 cursor-not-allowed"
                    }
                  `}
                >
                  {status === "loading" ? (
                    <><Loader2 className="w-5 h-5 animate-spin" /><span>Genererer...</span></>
                  ) : status === "success" ? (
                    <><CheckCircle2 className="w-5 h-5" /><span>{isDual ? "ZIP lastet ned!" : "PDF lastet ned!"}</span></>
                  ) : (
                    <><Sparkles className="w-5 h-5" /><span>{dualVersion ? "Lag ZIP" : customImage ? "Lag PDF med bilde" : "Generer PDF"}</span></>
                  )}
                </button>
              </div>

              <GenerationStatus
                status={status}
                progress={progress}
                errorMessage={errorMessage}
                isDual={isDual}
                onDismissError={() => setStatus("idle")}
              />
            </div>
          </form>

          {/* Info Cards */}
          <div className="grid grid-cols-2 gap-3 mt-5">
            <div className="rounded-lg border border-stone-200 bg-white px-4 py-3">
              <h3 className="text-stone-800 font-medium text-sm">Tilpasset innhold</h3>
              <p className="text-stone-400 text-xs mt-0.5">AI-generert tekst tilpasset språknivå</p>
            </div>
            <div className="rounded-lg border border-stone-200 bg-white px-4 py-3">
              <h3 className="text-stone-800 font-medium text-sm">Ferdig PDF</h3>
              <p className="text-stone-400 text-xs mt-0.5">Klar til print med oppgaver</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-10 text-center text-stone-400 text-xs">
          <p>Norsklæring · Læringsark for voksenopplæring</p>
        </footer>
      </div>

      {isPreviewing && previewData && (
        <PreviewModal
          previewData={previewData}
          formDisabled={formDisabled}
          isGenerating={status === "loading"}
          onClose={() => setIsPreviewing(false)}
          onGeneratePdf={generatePdfFromPreview}
        />
      )}
    </main>
  );
}
