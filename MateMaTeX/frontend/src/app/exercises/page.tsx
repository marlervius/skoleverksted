"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Grid3X3,
  List,
  Download,
  Sparkles,
  ChevronDown,
  X,
  Layers,
  Copy,
  Star,
  GripVertical,
  Plus,
  FileText,
} from "lucide-react";
import {
  listExercises,
  searchExercises,
  exportExercises,
  findSimilarExercises,
  generateVariant,
  generateHints,
  updateExercise,
  downloadBase64,
  publishToSchool,
  type Exercise,
} from "@/lib/api";

type ViewMode = "grid" | "list";

// Static classes — Tailwind purges dynamically built class names like `bg-${x}`.
const DIFFICULTY_CONFIG: Record<string, { label: string; dotClass: string; dots: number }> = {
  lett: { label: "Lett", dotClass: "bg-accent-green", dots: 1 },
  middels: { label: "Middels", dotClass: "bg-accent-orange", dots: 3 },
  vanskelig: { label: "Vanskelig", dotClass: "bg-accent-red", dots: 5 },
};

const TYPE_LABELS: Record<string, string> = {
  standard: "Regneoppgave",
  flervalg: "Flervalg",
  sant_usant: "Sant/usant",
  utfylling: "Utfylling",
  tekstoppgave: "Tekstoppgave",
  grafisk: "Grafisk",
  bevis: "Bevis",
};

const TOPIC_COLORS: Record<string, string> = {
  algebra: "bg-accent-blue/10 text-accent-blue",
  geometri: "bg-accent-green/10 text-accent-green",
  funksjoner: "bg-accent-purple/10 text-accent-purple",
  statistikk: "bg-accent-teal/10 text-accent-teal",
  sannsynlighet: "bg-accent-orange/10 text-accent-orange",
};

function getTopicColor(topic: string): string {
  const lower = topic.toLowerCase();
  for (const [key, cls] of Object.entries(TOPIC_COLORS)) {
    if (lower.includes(key)) return cls;
  }
  return "bg-surface-elevated text-text-secondary";
}

export default function ExerciseBankPage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [buildMode, setBuildMode] = useState(false);
  const [examExercises, setExamExercises] = useState<Exercise[]>([]);

  // Filters
  const [filterDifficulty, setFilterDifficulty] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterGrade, setFilterGrade] = useState("");
  const [filterTopic, setFilterTopic] = useState("");

  const GRADES = ["8. trinn", "9. trinn", "10. trinn", "VG1 1T", "VG2 R1"];

  const applyClientFilters = useCallback(
    (items: Exercise[]) =>
      items.filter((ex) => {
        if (filterDifficulty && ex.difficulty !== filterDifficulty) return false;
        if (filterType && ex.exercise_type !== filterType) return false;
        if (
          filterGrade &&
          !ex.grade_level.toLowerCase().includes(filterGrade.toLowerCase())
        ) {
          return false;
        }
        if (filterTopic && !ex.topic.toLowerCase().includes(filterTopic.toLowerCase())) {
          return false;
        }
        return true;
      }),
    [filterDifficulty, filterType, filterGrade, filterTopic]
  );

  // Hint / similar state (for the expanded card)
  const [hints, setHints] = useState<any>(null);
  const [similar, setSimilar] = useState<Exercise[] | null>(null);
  const [actionLoading, setActionLoading] = useState("");
  const [actionError, setActionError] = useState("");
  const [fetchError, setFetchError] = useState("");

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const searchRef = useRef<HTMLInputElement>(null);

  // Cmd+E to focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "e") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchQuery(searchInput);
      setPage(1);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchInput]);

  const fetchExercises = useCallback(async () => {
    setLoading(true);
    setFetchError("");
    try {
      if (searchQuery.trim()) {
        const res = await searchExercises(searchQuery);
        const filtered = applyClientFilters(res.exercises);
        setExercises(filtered);
        setTotal(filtered.length);
      } else {
        const res = await listExercises({
          difficulty: filterDifficulty || undefined,
          exercise_type: filterType || undefined,
          grade_level: filterGrade || undefined,
          topic: filterTopic || undefined,
          page,
          page_size: 21,
        });
        setExercises(res.exercises);
        setTotal(res.total);
      }
    } catch (e: unknown) {
      setExercises([]);
      setFetchError(e instanceof Error ? e.message : "Kunne ikke laste oppgaver");
    } finally {
      setLoading(false);
    }
  }, [searchQuery, filterDifficulty, filterType, filterGrade, filterTopic, page, applyClientFilters]);

  useEffect(() => {
    fetchExercises();
  }, [fetchExercises]);

  const handleSearch = (value: string) => {
    setSearchInput(value);
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleBulkExport = async (format: "pdf" | "docx") => {
    if (selected.size === 0) return;
    setActionLoading("export");
    setActionError("");
    try {
      const res = await exportExercises(Array.from(selected), format);
      if (res.success) {
        downloadBase64(res.content_base64, res.filename, "application/octet-stream");
      } else {
        setActionError("Eksport feilet");
      }
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Eksport feilet");
    } finally {
      setActionLoading("");
    }
  };

  const handleExamExport = async () => {
    if (examExercises.length === 0) return;
    setActionLoading("exam");
    setActionError("");
    try {
      const res = await exportExercises(
        examExercises.map((e) => e.id),
        "pdf",
        true,
        "Eksamen"
      );
      if (res.success) {
        downloadBase64(res.content_base64, res.filename, "application/pdf");
      } else {
        setActionError("Eksamenseksport feilet");
      }
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Eksamenseksport feilet");
    } finally {
      setActionLoading("");
    }
  };

  const handleFindSimilar = async (ex: Exercise) => {
    setActionLoading("similar");
    setActionError("");
    try {
      const res = await findSimilarExercises(ex.id);
      setSimilar(res);
      setHints(null);
      setExpandedId(ex.id);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Fant ikke lignende oppgaver");
    } finally {
      setActionLoading("");
    }
  };

  const handleGenerateVariant = async (id: string) => {
    setActionLoading("variant");
    setActionError("");
    try {
      await generateVariant(id);
      fetchExercises();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Variant feilet");
    } finally {
      setActionLoading("");
    }
  };

  const handlePublishToSchool = async (id: string) => {
    setActionLoading("publish");
    setActionError("");
    try {
      await publishToSchool(id);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Publisering feilet");
    } finally {
      setActionLoading("");
    }
  };

  const handleGenerateHints = async (ex: Exercise) => {
    setActionLoading("hints");
    try {
      const res = await generateHints(ex.id, ex.latex_content, ex.solution);
      if (res.success) {
        setHints(res.hints);
        setSimilar(null);
        setExpandedId(ex.id);
      }
    } finally {
      setActionLoading("");
    }
  };

  const handleSaveExercise = async (id: string, latexContent: string) => {
    setActionLoading("save");
    setActionError("");
    try {
      const updated = await updateExercise(id, { latex_content: latexContent });
      setExercises((prev) => prev.map((e) => (e.id === id ? updated : e)));
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Kunne ikke lagre oppgave");
    } finally {
      setActionLoading("");
    }
  };

  const removeFilter = (filter: string) => {
    if (filter.startsWith("diff:")) setFilterDifficulty("");
    if (filter.startsWith("type:")) setFilterType("");
  };

  // Collect active filters for display
  const filterChips: string[] = [];
  if (filterDifficulty) filterChips.push(`diff:${filterDifficulty}`);
  if (filterType) filterChips.push(`type:${filterType}`);

  /* ---- Empty / error state ---- */
  if (fetchError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <h2 className="font-display text-2xl mb-2">Kunne ikke laste oppgaver</h2>
        <p className="text-text-secondary text-sm mb-6 max-w-sm">{fetchError}</p>
        <button type="button" onClick={() => fetchExercises()} className="btn-primary">
          Prøv igjen
        </button>
      </div>
    );
  }

  if (!loading && exercises.length === 0 && !searchQuery && !filterDifficulty && !filterType) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <div className="text-5xl mb-4 opacity-30">📐</div>
        <h2 className="font-display text-2xl mb-2">Ingen oppgaver ennå</h2>
        <p className="text-text-secondary text-sm mb-6 max-w-sm">
          Oppgaver du genererer lagres automatisk her. Generer ditt første arbeidsark for å komme i gang.
        </p>
        <a href="/matematikk" className="btn-primary">
          <Sparkles size={14} />
          Generer nå
        </a>
      </div>
    );
  }

  return (
    <div className="flex gap-6">
      {/* Main content */}
      <div className={`flex-1 min-w-0 ${buildMode ? "w-3/5" : ""}`}>
        {/* Search */}
        <div className="relative mb-4">
          <Search
            size={18}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            ref={searchRef}
            type="text"
            value={searchInput}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Søk i oppgaver... (f.eks. 'andregradsligning med diskriminant')"
            className="input !pl-11 !pr-4 !py-3.5 text-center"
          />
          <kbd className="absolute right-4 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] text-text-muted bg-surface-elevated rounded font-mono hidden md:inline">
            ⌘E
          </kbd>
        </div>

        {actionError && (
          <p className="text-sm text-accent-red mb-3" role="alert">
            {actionError}
          </p>
        )}

        {/* Filters + view mode */}
        <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
          <select
            value={filterDifficulty}
            onChange={(e) => { setFilterDifficulty(e.target.value); setPage(1); }}
            className="input !w-auto !py-1.5 !text-xs"
          >
            <option value="">Vanskelighetsgrad</option>
            <option value="lett">Lett</option>
            <option value="middels">Middels</option>
            <option value="vanskelig">Vanskelig</option>
          </select>

          <select
            value={filterType}
            onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
            className="input !w-auto !py-1.5 !text-xs"
          >
            <option value="">Type</option>
            {Object.entries(TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>

          <select
            value={filterGrade}
            onChange={(e) => { setFilterGrade(e.target.value); setPage(1); }}
            className="input !w-auto !py-1.5 !text-xs"
          >
            <option value="">Trinn</option>
            {GRADES.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>

          <input
            value={filterTopic}
            onChange={(e) => { setFilterTopic(e.target.value); setPage(1); }}
            placeholder="Emne"
            className="input !w-auto !py-1.5 !text-xs min-w-[7rem]"
          />

          <div className="flex-1" />

          <button
            onClick={() => setBuildMode(!buildMode)}
            className={`btn-ghost text-xs ${buildMode ? "!bg-accent-purple/10 !text-accent-purple" : ""}`}
          >
            <Layers size={14} />
            Bygg eksamen
          </button>

          <div className="flex border border-border rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 ${viewMode === "grid" ? "bg-surface-elevated text-text-primary" : "text-text-muted"}`}
              aria-label="Rutenettvisning"
            >
              <Grid3X3 size={14} />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-1.5 ${viewMode === "list" ? "bg-surface-elevated text-text-primary" : "text-text-muted"}`}
              aria-label="Listevisning"
            >
              <List size={14} />
            </button>
          </div>
        </div>

        {/* Active filters */}
        {filterChips.length > 0 && (
          <div className="flex gap-1.5 mb-4">
            {filterChips.map((f) => (
              <button
                key={f}
                onClick={() => removeFilter(f)}
                className="badge bg-accent-blue/10 text-accent-blue gap-1 cursor-pointer hover:bg-accent-blue/20 transition-colors"
              >
                {f.replace("diff:", "").replace("type:", "")}
                <X size={10} />
              </button>
            ))}
          </div>
        )}

        {/* Bulk action bar */}
        <AnimatePresence>
          {selected.size > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="card !py-2.5 !px-4 flex items-center gap-3 mb-4"
            >
              <span className="text-sm text-text-secondary">
                {selected.size} valgt
              </span>
              <button onClick={() => handleBulkExport("pdf")} className="btn-primary !py-1.5 !px-3 text-xs">
                <Download size={12} /> PDF
              </button>
              <button onClick={() => handleBulkExport("docx")} className="btn-secondary !py-1.5 !px-3 text-xs">
                <Download size={12} /> Word
              </button>
              <div className="flex-1" />
              <button onClick={() => setSelected(new Set())} className="btn-ghost !py-1 text-xs">
                Fjern valg
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loading */}
        {loading ? (
          <div className={`grid gap-4 ${viewMode === "grid" ? "grid-cols-1 md:grid-cols-2 lg:grid-cols-3" : ""}`}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="card animate-pulse">
                <div className="skeleton h-4 w-24 mb-3" />
                <div className="skeleton h-3 w-full mb-2" />
                <div className="skeleton h-3 w-3/4" />
              </div>
            ))}
          </div>
        ) : viewMode === "grid" ? (
          /* Grid view */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {exercises.map((ex, i) => (
              <motion.div
                key={ex.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <ExerciseCard
                  exercise={ex}
                  isSelected={selected.has(ex.id)}
                  isExpanded={expandedId === ex.id}
                  onSelect={() => toggleSelect(ex.id)}
                  onExpand={() => setExpandedId(expandedId === ex.id ? null : ex.id)}
                  onVariant={() => handleGenerateVariant(ex.id)}
                  onPublish={() => handlePublishToSchool(ex.id)}
                  onHints={() => handleGenerateHints(ex)}
                  onSimilar={() => handleFindSimilar(ex)}
                  onSaveLatex={(latex) => handleSaveExercise(ex.id, latex)}
                  onAddToExam={() => {
                    if (!examExercises.find((e) => e.id === ex.id)) {
                      setExamExercises([...examExercises, ex]);
                    }
                  }}
                  hints={expandedId === ex.id ? hints : null}
                  similar={expandedId === ex.id ? similar : null}
                  actionLoading={actionLoading}
                  buildMode={buildMode}
                />
              </motion.div>
            ))}
          </div>
        ) : (
          /* List view */
          <div className="space-y-1">
            {exercises.map((ex) => (
              <ExerciseRow
                key={ex.id}
                exercise={ex}
                isSelected={selected.has(ex.id)}
                onSelect={() => toggleSelect(ex.id)}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {total > 21 && (
          <div className="flex justify-center gap-2 mt-8">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="btn-secondary disabled:opacity-30">
              Forrige
            </button>
            <span className="btn-ghost cursor-default">
              Side {page} av {Math.ceil(total / 21)}
            </span>
            <button onClick={() => setPage(page + 1)} disabled={page >= Math.ceil(total / 21)} className="btn-secondary disabled:opacity-30">
              Neste
            </button>
          </div>
        )}
      </div>

      {/* Exam builder sidebar */}
      <AnimatePresence>
        {buildMode && (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: "40%" }}
            exit={{ opacity: 0, width: 0 }}
            className="sticky top-20 h-[calc(100vh-6rem)] overflow-y-auto"
          >
            <div className="card h-full flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-sm">Eksamensbygger</h3>
                <span className="badge bg-accent-purple/10 text-accent-purple">
                  {examExercises.length} oppgaver
                </span>
              </div>

              {examExercises.length === 0 ? (
                <div className="flex-1 flex items-center justify-center text-center text-text-muted">
                  <div>
                    <Plus size={24} className="mx-auto mb-2 opacity-30" />
                    <p className="text-xs">
                      Klikk &ldquo;+ Eksamen&rdquo; på oppgavekort for å legge til
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex-1 space-y-2 overflow-y-auto mb-4">
                    {examExercises.map((ex, i) => (
                      <div key={ex.id} className="flex items-center gap-2 p-2 bg-surface-elevated rounded-lg text-xs">
                        <GripVertical size={12} className="text-text-muted cursor-grab" />
                        <span className="font-mono text-text-muted w-5">{i + 1}.</span>
                        <span className="flex-1 truncate">{ex.title}</span>
                        <button
                          onClick={() => setExamExercises(examExercises.filter((e) => e.id !== ex.id))}
                          className="text-text-muted hover:text-accent-red transition-colors"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={handleExamExport}
                    disabled={actionLoading === "exam"}
                    className="btn-primary w-full disabled:opacity-50"
                  >
                    <FileText size={14} />
                    {actionLoading === "exam" ? "Genererer…" : "Generer eksamen"}
                  </button>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* -----------------------------------------------------------------------
   Exercise card (grid)
   ----------------------------------------------------------------------- */
function ExerciseCard({
  exercise,
  isSelected,
  isExpanded,
  onSelect,
  onExpand,
  onVariant,
  onPublish,
  onHints,
  onSimilar,
  onSaveLatex,
  onAddToExam,
  hints,
  similar,
  actionLoading,
  buildMode,
}: {
  exercise: Exercise;
  isSelected: boolean;
  isExpanded: boolean;
  onSelect: () => void;
  onExpand: () => void;
  onVariant: () => void;
  onPublish: () => void;
  onHints: () => void;
  onSimilar: () => void;
  onSaveLatex: (latex: string) => void;
  onAddToExam: () => void;
  hints: any;
  similar: Exercise[] | null;
  actionLoading: string;
  buildMode: boolean;
}) {
  const diff = DIFFICULTY_CONFIG[exercise.difficulty] || DIFFICULTY_CONFIG.middels;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(exercise.latex_content);

  useEffect(() => {
    setDraft(exercise.latex_content);
  }, [exercise.latex_content]);

  return (
    <div
      className={`card-interactive relative ${
        isSelected ? "!border-accent-blue bg-accent-blue/5" : ""
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onSelect}
            className="rounded border-border mt-0.5"
          />
          {exercise.topic && (
            <span className={`badge ${getTopicColor(exercise.topic)}`}>
              {exercise.topic}
            </span>
          )}
        </div>
        {/* Difficulty dots */}
        <div className="flex gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className={`w-1.5 h-1.5 rounded-full ${
                i < diff.dots ? diff.dotClass : "bg-border"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Content preview */}
      <div onClick={onExpand} className="cursor-pointer mb-3">
        <p className="text-sm text-text-primary line-clamp-2 leading-relaxed">
          {exercise.latex_content
            .replace(/\\[a-zA-Z]+\{([^}]*)\}/g, "$1")
            .replace(/[\\{}$]/g, "")
            .substring(0, 150)}
        </p>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-2 text-[10px] text-text-muted mb-3">
        {exercise.grade_level && <span>{exercise.grade_level}</span>}
        <span>·</span>
        <span>{TYPE_LABELS[exercise.exercise_type] || exercise.exercise_type}</span>
      </div>

      {/* Actions */}
      <div className="flex gap-1.5">
        <SmallBtn label="Lignende" onClick={onSimilar} loading={actionLoading === "similar"} />
        <SmallBtn label="Variant" onClick={onVariant} loading={actionLoading === "variant"} />
        <SmallBtn label="Skole" onClick={onPublish} loading={actionLoading === "publish"} />
        <SmallBtn label="Hint" onClick={onHints} loading={actionLoading === "hints"} />
        <SmallBtn
          label={editing ? "Avbryt" : "Rediger"}
          onClick={() => setEditing((v) => !v)}
        />
        {buildMode && (
          <SmallBtn label="+ Eksamen" onClick={onAddToExam} accent />
        )}
      </div>

      {/* Expanded: edit / similar */}
      <AnimatePresence>
        {isExpanded && editing && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 pt-3 border-t border-border space-y-2"
          >
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="input font-mono text-xs min-h-[120px] w-full"
            />
            <button
              type="button"
              className="btn-primary text-xs"
              disabled={actionLoading === "save"}
              onClick={() => {
                onSaveLatex(draft);
                setEditing(false);
              }}
            >
              {actionLoading === "save" ? "Lagrer…" : "Lagre (SymPy-sjekk)"}
            </button>
          </motion.div>
        )}
        {isExpanded && similar && !editing && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 pt-3 border-t border-border space-y-2"
          >
            <p className="text-[10px] font-medium text-text-muted uppercase tracking-wide">
              Lignende oppgaver
            </p>
            {similar.length === 0 ? (
              <p className="text-xs text-text-secondary">Ingen lignende oppgaver funnet.</p>
            ) : (
              similar.map((s) => (
                <div key={s.id} className="text-xs p-2 bg-surface-elevated rounded-lg">
                  <span className="font-medium text-text-primary">{s.title}</span>
                  <p className="text-text-secondary line-clamp-2 mt-0.5">
                    {s.latex_content.replace(/[\\{}$]/g, "").substring(0, 100)}
                  </p>
                </div>
              ))
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Expanded: hints */}
      <AnimatePresence>
        {isExpanded && hints && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 pt-3 border-t border-border space-y-2"
          >
            {hints.nudge && (
              <div className="text-xs">
                <span className="text-accent-orange font-medium">Dytt: </span>
                <span className="text-text-secondary">{hints.nudge}</span>
              </div>
            )}
            {hints.step && (
              <div className="text-xs">
                <span className="text-accent-blue font-medium">Steg: </span>
                <span className="text-text-secondary">{hints.step}</span>
              </div>
            )}
            {hints.near_solution && (
              <div className="text-xs">
                <span className="text-accent-green font-medium">Nesten: </span>
                <span className="text-text-secondary">{hints.near_solution}</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* -----------------------------------------------------------------------
   Exercise row (list)
   ----------------------------------------------------------------------- */
function ExerciseRow({
  exercise,
  isSelected,
  onSelect,
}: {
  exercise: Exercise;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const diff = DIFFICULTY_CONFIG[exercise.difficulty] || DIFFICULTY_CONFIG.middels;

  return (
    <div
      className={`card !py-2.5 !px-4 flex items-center gap-3 ${
        isSelected ? "!border-accent-blue bg-accent-blue/5" : ""
      }`}
    >
      <input type="checkbox" checked={isSelected} onChange={onSelect} className="rounded border-border" />
      <span className="text-sm font-medium w-28 truncate text-text-primary">{exercise.title}</span>
      {exercise.topic && (
        <span className={`badge ${getTopicColor(exercise.topic)}`}>{exercise.topic}</span>
      )}
      <span className="text-xs text-text-muted flex-1 truncate font-mono">
        {exercise.latex_content.replace(/[\\{}$]/g, "").substring(0, 80)}
      </span>
      <div className="flex gap-0.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className={`w-1.5 h-1.5 rounded-full ${i < diff.dots ? diff.dotClass : "bg-border"}`} />
        ))}
      </div>
      <span className="badge bg-surface-elevated text-text-muted">
        {TYPE_LABELS[exercise.exercise_type] || exercise.exercise_type}
      </span>
    </div>
  );
}

/* -----------------------------------------------------------------------
   Small action button
   ----------------------------------------------------------------------- */
function SmallBtn({
  label,
  onClick,
  loading,
  accent,
}: {
  label: string;
  onClick: () => void;
  loading?: boolean;
  accent?: boolean;
}) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      disabled={loading}
      className={`px-2 py-1 text-[10px] rounded-md border transition-colors disabled:opacity-50 ${
        accent
          ? "border-accent-purple/40 text-accent-purple hover:bg-accent-purple/10"
          : "border-border hover:border-text-muted text-text-muted hover:text-text-secondary"
      }`}
    >
      {loading ? "..." : label}
    </button>
  );
}
