"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CalendarRange, Clock3, Loader2, Sparkles } from "lucide-react";
import { YEAR_PLAN_LEVELS, YEAR_PLAN_SUBJECTS } from "@/features/fag/components/constants";
import { generateYearPlan } from "@/lib/platform-api";
import { isMathematicsSubject, MATEMATEX_YEAR_PLAN_LEVELS } from "@/lib/mathematics-year-plan";

function suggestedSchoolYear(): string {
  const now = new Date();
  const year = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-${year + 1}`;
}

export default function NewYearPlanPage() {
  const router = useRouter();
  const [subject, setSubject] = useState("Historie");
  const [level, setLevel] = useState("VG2");
  const [schoolYear, setSchoolYear] = useState(suggestedSchoolYear());
  const [lessonsPerWeek, setLessonsPerWeek] = useState(2);
  const [lessonMinutes, setLessonMinutes] = useState(45);
  const [teachingWeeks, setTeachingWeeks] = useState(38);
  const [periodCount, setPeriodCount] = useState(9);
  const [goals, setGoals] = useState("");
  const [constraints, setConstraints] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const totalLessons = useMemo(() => lessonsPerWeek * teachingWeeks, [lessonsPerWeek, teachingWeeks]);
  const mathematicsSelected = isMathematicsSubject(subject);
  const availableLevels = mathematicsSelected ? MATEMATEX_YEAR_PLAN_LEVELS : YEAR_PLAN_LEVELS;

  function handleSubjectChange(nextSubject: string) {
    const nextIsMathematics = isMathematicsSubject(nextSubject);
    setSubject(nextSubject);
    if (nextIsMathematics && !MATEMATEX_YEAR_PLAN_LEVELS.some((item) => item.value === level)) {
      setLevel("VG1 1T");
    } else if (!nextIsMathematics && MATEMATEX_YEAR_PLAN_LEVELS.some((item) => item.value === level)) {
      setLevel("VG2");
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const plan = await generateYearPlan({
        subject,
        level,
        school_year: schoolYear,
        lessons_per_week: lessonsPerWeek,
        lesson_minutes: lessonMinutes,
        teaching_weeks: teachingWeeks,
        number_of_periods: periodCount,
        competency_goals: goals.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
        constraints,
        use_ai: true,
      });
      router.push(`/year-plans/${plan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke lage årsplanen.");
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link href="/year-plans" className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary">
        <ArrowLeft className="h-4 w-4" /> Årsplaner
      </Link>

      <header>
        <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-accent-purple/10 px-3 py-1 text-xs font-medium text-accent-purple">
          <Sparkles className="h-3.5 w-3.5" /> Pedagogisk planlegger
        </div>
        <h1 className="font-display text-4xl">Ny årsplan</h1>
        <p className="mt-2 max-w-2xl text-text-secondary">
          Planen blir et redigerbart forslag. Du beholder kontrollen over temaer, timetall og læreplandekning.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-5">
        <section className="card">
          <h2 className="flex items-center gap-2 font-semibold"><CalendarRange className="h-5 w-5 text-accent-blue" /> Fag og skoleår</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <label className="text-sm font-medium">Fag
              <select className="input mt-2" value={subject} onChange={(event) => handleSubjectChange(event.target.value)}>
                {YEAR_PLAN_SUBJECTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">Nivå
              <select className="input mt-2" value={level} onChange={(event) => setLevel(event.target.value)}>
                {availableLevels.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium">Skoleår
              <input className="input mt-2" value={schoolYear} onChange={(event) => setSchoolYear(event.target.value)} placeholder="2026-2027" />
            </label>
          </div>
          {mathematicsSelected && (
            <div className="mt-4 rounded-lg border border-accent-blue/20 bg-accent-blue/5 px-4 py-3 text-sm text-text-secondary">
              Læremidlene i årsplanen åpnes i <strong className="text-text-primary">MateMaTeX</strong> med matematisk verifisering, fasit og matematikktilpassede eksportvalg.
            </div>
          )}
        </section>

        <section className="card">
          <h2 className="flex items-center gap-2 font-semibold"><Clock3 className="h-5 w-5 text-accent-teal" /> Tidsramme</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-4">
            <label className="text-sm font-medium">Timer per uke
              <input className="input mt-2" type="number" min={1} max={15} value={lessonsPerWeek} onChange={(event) => setLessonsPerWeek(Number(event.target.value))} />
            </label>
            <label className="text-sm font-medium">Minutter per time
              <input className="input mt-2" type="number" min={30} max={180} step={5} value={lessonMinutes} onChange={(event) => setLessonMinutes(Number(event.target.value))} />
            </label>
            <label className="text-sm font-medium">Undervisningsuker
              <input className="input mt-2" type="number" min={20} max={45} value={teachingWeeks} onChange={(event) => setTeachingWeeks(Number(event.target.value))} />
            </label>
            <label className="text-sm font-medium">Antall perioder
              <input className="input mt-2" type="number" min={4} max={16} value={periodCount} onChange={(event) => setPeriodCount(Number(event.target.value))} />
            </label>
          </div>
          <div className="mt-4 rounded-lg bg-accent-teal/10 px-4 py-3 text-sm text-text-secondary">
            Planleggeren fordeler omtrent <strong className="text-text-primary">{totalLessons} undervisningstimer</strong> på {periodCount} perioder.
          </div>
        </section>

        <section className="card space-y-5">
          <div>
            <label className="text-sm font-medium" htmlFor="competency-goals">Kompetansemål <span className="font-normal text-text-muted">(ett per linje)</span></label>
            <textarea
              id="competency-goals"
              className="input mt-2 min-h-36 resize-y"
              value={goals}
              onChange={(event) => setGoals(event.target.value)}
              placeholder="Lim inn relevante kompetansemål. Planleggeren fordeler dem uten å omskrive dem."
            />
            <p className="mt-2 text-xs text-text-muted">Kan stå tomt i første utkast, men planen vil da ikke påstå full læreplandekning.</p>
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="constraints">Lokale hensyn</label>
            <textarea
              id="constraints"
              className="input mt-2 min-h-24 resize-y"
              value={constraints}
              onChange={(event) => setConstraints(event.target.value)}
              placeholder="For eksempel ekskursjon i oktober, praksisperiode, tentamen eller temaer skolen prioriterer."
            />
          </div>
        </section>

        {error && <div role="alert" className="card border-accent-red/30 text-sm text-accent-red">{error}</div>}

        <div className="flex flex-wrap items-center justify-end gap-3">
          <Link href="/year-plans" className="btn-secondary">Avbryt</Link>
          <button type="submit" className="btn-primary min-w-48" disabled={loading || !subject || !level || !schoolYear}>
            {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Planlegger skoleåret …</> : <><Sparkles className="h-4 w-4" /> Lag årsplanforslag</>}
          </button>
        </div>
      </form>
    </div>
  );
}
