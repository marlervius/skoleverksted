"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenText, Calculator, Languages } from "lucide-react";

const tools = [
  {
    href: "/fag",
    label: "Fag & læring",
    shortLabel: "Fag",
    description: "Læringsark, prøver og undervisningsløp",
    icon: BookOpenText,
    color: "text-accent-teal",
  },
  {
    href: "/norsk",
    label: "Norsklæring",
    shortLabel: "Norsk",
    description: "Språktilpassede ark etter CEFR",
    icon: Languages,
    color: "text-accent-purple",
  },
  {
    href: "/matematikk",
    label: "Matematikk",
    shortLabel: "Matte",
    description: "Verifiserte oppgaver og prøver",
    icon: Calculator,
    color: "text-accent-blue",
  },
] as const;

export function PlatformSwitcher({ compact = false }: { compact?: boolean }) {
  const pathname = usePathname();

  return (
    <nav
      className="inline-grid grid-cols-3 gap-1 rounded-xl border border-border bg-surface-elevated/80 p-1 shadow-soft-sm"
      aria-label="Velg arbeidsverktøy"
    >
      {tools.map((tool) => {
        const active = pathname === tool.href || pathname.startsWith(`${tool.href}/`);
        const Icon = tool.icon;
        return (
          <Link
            key={tool.href}
            href={tool.href}
            aria-current={active ? "page" : undefined}
            title={compact ? tool.description : undefined}
            className={`group flex items-center justify-center gap-2 rounded-lg font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/60 ${
              compact ? "px-2.5 py-1.5 text-xs sm:px-4" : "px-4 py-3 text-sm sm:px-6"
            } ${
              active
                ? "bg-surface text-text-primary shadow-soft-sm ring-1 ring-border"
                : "text-text-secondary hover:bg-surface/70 hover:text-text-primary"
            }`}
          >
            <Icon className={`h-4 w-4 shrink-0 ${tool.color}`} aria-hidden="true" />
            <span className="hidden sm:inline">{tool.label}</span>
            <span className="sm:hidden">{tool.shortLabel}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export { tools as platformTools };
