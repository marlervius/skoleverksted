import Link from "next/link";
import { ArrowRight, BookOpenText, Check, FileCheck2, Languages, Layers3, MoveUpRight } from "lucide-react";

const features = [
  { icon: Languages, title: "Språket på riktig nivå", text: "Velg fra A1.1 til B2.2 og lag tekster, begrepsforklaringer og oppgaver tilpasset deltakerne dine." },
  { icon: Layers3, title: "Ett tema. Flere innganger.", text: "Lag materiell om samme tema på flere språknivåer. Velg blant annet leseoppgaver, grammatikk, samtale og skrivestøtte." },
  { icon: BookOpenText, title: "Fra begrep til forståelse", text: "La deltakerne øve videre med en nedlastbar begrepstrener. Den åpnes i nettleseren og kan brukes uten nett." },
];

export function NorskHome() {
  return (
    <div className="mx-auto max-w-6xl px-5 sm:px-8">
      <section className="grid items-center gap-12 py-16 sm:py-24 lg:grid-cols-[1.15fr_1fr] lg:gap-16" aria-labelledby="norsk-title">
        <div>
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.18em] text-accent-700">For voksne som lærer norsk</p>
          <h1 id="norsk-title" className="max-w-xl font-display text-5xl leading-[1.08] tracking-tight text-accent-900 sm:text-6xl">God undervisning begynner med et språk alle forstår.</h1>
          <p className="mt-6 max-w-lg text-lg leading-relaxed text-stone-600">Lag læringsark som møter deltakerne der de er. Du velger tema, fag og språknivå. Norskverksted hjelper deg med teksten, oppgavene og begrepene.</p>
          <Link href="/verksted" className="mt-8 inline-flex items-center gap-3 rounded-xl bg-accent-700 px-6 py-3.5 font-medium text-white transition hover:bg-accent-800">Åpne Norskverksted <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
          <p className="mt-3 text-xs text-stone-500">Åpen utprøving · Tilgangskoden er midlertidig fjernet</p>
        </div>
        <div className="relative rounded-3xl bg-accent-100 p-5 sm:p-8">
          <div className="mb-4 flex items-center justify-between text-xs font-medium text-accent-800"><span>Slik kan et læringsark se ut</span><span className="rounded-full border border-accent-300 px-2.5 py-1">A2</span></div>
          <article className="rounded-xl border border-stone-200 bg-white p-6 shadow-soft-lg sm:p-8">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-accent-600">Eksempel · Norsk i hverdagen</p>
            <h2 className="mt-4 font-display text-3xl text-stone-900">På biblioteket</h2>
            <div className="mt-5 border-y border-stone-200 py-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-accent-700">Ord vi skal lære</h3>
              <dl className="mt-3 space-y-2 text-sm text-stone-600"><div><dt className="inline font-semibold text-stone-900">å låne</dt><dd className="inline"> – å bruke noe og gi det tilbake</dd></div><div><dt className="inline font-semibold text-stone-900">Mitt språk</dt><dd className="mt-2 border-b border-dotted border-stone-300 pb-2"><span className="sr-only">Plass til egen oversettelse</span></dd></div></dl>
            </div>
            <p className="mt-5 text-sm leading-7 text-stone-700">Sara går til biblioteket. Hun vil låne en bok på norsk. Hun spør en ansatt om hjelp.</p>
            <div className="mt-5 rounded-lg bg-stone-50 p-4"><h3 className="text-sm font-semibold text-stone-900">Snakk sammen</h3><p className="mt-1 text-sm text-stone-600">Hvilken bok vil du låne?</p></div>
            <p className="mt-5 text-[11px] text-stone-500">Illustrerende eksempel, ikke et ferdig generert læringsark.</p>
          </article>
        </div>
      </section>

      <section className="border-t border-stone-200 py-12 sm:py-16" aria-labelledby="features-title">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-700">Din undervisning, ditt faglige skjønn</p>
        <h2 id="features-title" className="mt-3 font-display text-3xl text-accent-900 sm:text-4xl">Mer tid til menneskene i rommet.</h2>
        <div className="mt-9 grid gap-8 md:grid-cols-3">{features.map(({ icon: Icon, title, text }) => <div key={title}><Icon className="mb-4 h-6 w-6 text-accent-700" aria-hidden="true" /><h3 className="text-base font-semibold text-stone-900">{title}</h3><p className="mt-2 text-sm leading-6 text-stone-600">{text}</p></div>)}</div>
      </section>

      <section className="mb-16 rounded-2xl border border-accent-200 bg-white p-6 sm:p-10" aria-labelledby="workflow-title">
        <div className="flex items-center gap-3"><FileCheck2 className="h-6 w-6 text-accent-700" aria-hidden="true" /><h2 id="workflow-title" className="font-display text-3xl text-accent-900">Du har siste ord.</h2></div>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-600">KI lager et utkast. Kilder og innhold kontrolleres, og du gjennomgår og godkjenner den konkrete versjonen før endelig eksport.</p>
        <ol className="my-7 grid gap-5 text-sm md:grid-cols-3">{["Velg fag, tema og språknivå.", "Les forhåndsvisningen og gjør endringer.", "Godkjenn og last ned læringsark og øvingsmateriell."].map((step, index) => <li key={step} className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-50 text-xs font-semibold text-accent-800">{index + 1}</span><span className="pt-1 text-stone-700">{step}</span></li>)}</ol>
        <div className="flex flex-wrap items-center justify-between gap-5 border-t border-stone-200 pt-6"><p className="flex items-center gap-2 text-xs text-stone-600"><Check className="h-4 w-4 text-accent-700" aria-hidden="true" />PDF-læringsark, flernivåpakker og begrepstrener</p><Link href="/verksted" className="inline-flex items-center gap-2 text-sm font-semibold text-accent-700 hover:underline">Lag ditt første læringsark <MoveUpRight className="h-4 w-4" aria-hidden="true" /></Link></div>
      </section>
    </div>
  );
}
