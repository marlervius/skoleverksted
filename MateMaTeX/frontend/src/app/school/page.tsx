"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { School, Search, BookOpen, AlertTriangle } from "lucide-react";
import { listSchoolExercises, type SchoolExercise } from "@/lib/api";

export default function SchoolBankPage() {
  const [exercises, setExercises] = useState<SchoolExercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listSchoolExercises({
        topic: searchQuery.trim() || undefined,
      });
      setExercises(res.exercises);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Kunne ikke laste skolebank");
      setExercises([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    const t = setTimeout(load, searchQuery ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, searchQuery]);

  const filtered = searchQuery.trim()
    ? exercises.filter(
        (ex) =>
          ex.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          ex.topic.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : exercises;

  return (
    <div className="max-w-content mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl mb-1">Skolens oppgavebank</h1>
          <p className="text-text-secondary text-sm">
            Oppgaver delt av lærere på din skole
          </p>
        </div>
      </div>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          placeholder="Søk i skolens oppgaver..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input pl-10 w-full"
        />
      </div>

      {error && (
        <div className="card mb-6 border-accent-red/30 bg-accent-red/5 flex items-center gap-2 text-sm">
          <AlertTriangle size={16} className="text-accent-red shrink-0" />
          {error}
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center justify-center min-h-[50vh] text-center"
        >
          <School size={48} className="text-text-muted opacity-20 mb-4" />
          <h2 className="font-display text-2xl mb-2">Ingen oppgaver ennå</h2>
          <p className="text-text-secondary text-sm mb-6 max-w-sm">
            Når du eller kollegaer publiserer oppgaver til skolens bank, dukker de
            opp her. Gå til oppgavebanken og klikk «Publiser til skolen».
          </p>
          <a href="/exercises" className="btn-primary inline-flex items-center gap-2">
            <BookOpen size={14} />
            Gå til min oppgavebank
          </a>
        </motion.div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((ex) => (
            <div key={ex.id} className="card-interactive p-4">
              <h3 className="font-medium text-sm mb-1">{ex.title}</h3>
              <p className="text-xs text-text-muted mb-2">
                {ex.topic} · {ex.grade_level} · {ex.difficulty}
              </p>
              <p className="text-[10px] text-text-muted">
                Publisert {new Date(ex.published_at).toLocaleDateString("nb-NO")}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
