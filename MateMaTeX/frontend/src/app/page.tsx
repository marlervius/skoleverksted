"use client";

import Link from "next/link";
import { ArrowRight, BookOpenText, Calculator, Languages, ShieldCheck, Sparkles } from "lucide-react";
import { PlatformSwitcher, platformTools } from "@/components/platform-switcher";

const cardStyles = [
  { surface: "from-accent-teal/15 to-accent-teal/5", icon: "bg-accent-teal/15 text-accent-teal" },
  { surface: "from-accent-purple/15 to-accent-purple/5", icon: "bg-accent-purple/15 text-accent-purple" },
  { surface: "from-accent-blue/15 to-accent-blue/5", icon: "bg-accent-blue/15 text-accent-blue" },
];

const icons = [BookOpenText, Languages, Calculator];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl py-6 sm:py-12">
      <section className="text-center">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-text-secondary shadow-soft-sm">
          <Sparkles className="h-3.5 w-3.5 text-accent-orange" />
          Ett verksted for hele skolen
        </div>
        <h1 className="font-display text-4xl tracking-tight text-text-primary sm:text-5xl">
          Hva vil du lage i dag?
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-text-secondary sm:text-lg">
          Velg arbeidsflate. Du kan bytte når som helst uten å forlate appen.
        </p>
        <div className="mt-8 flex justify-center">
          <PlatformSwitcher />
        </div>
      </section>

      <section className="mt-12 grid gap-4 md:grid-cols-3" aria-label="Arbeidsverktøy">
        {platformTools.map((tool, index) => {
          const Icon = icons[index];
          const style = cardStyles[index];
          return (
            <Link
              key={tool.href}
              href={tool.href}
              className={`group relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br ${style.surface} p-6 transition-all hover:-translate-y-1 hover:border-text-muted/40 hover:shadow-soft-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/60`}
            >
              <div className={`mb-6 flex h-11 w-11 items-center justify-center rounded-xl ${style.icon}`}>
                <Icon className="h-5 w-5" />
              </div>
              <h2 className="text-lg font-semibold text-text-primary">{tool.label}</h2>
              <p className="mt-2 min-h-12 text-sm leading-relaxed text-text-secondary">{tool.description}</p>
              <span className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-text-primary">
                Åpne verkstedet
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </span>
            </Link>
          );
        })}
      </section>

      <div className="mt-8 flex items-center justify-center gap-2 text-xs text-text-muted">
        <ShieldCheck className="h-4 w-4 text-accent-green" />
        Felles inngang, ingen elevdata og fagspesialisert kvalitetssikring
      </div>
    </div>
  );
}
