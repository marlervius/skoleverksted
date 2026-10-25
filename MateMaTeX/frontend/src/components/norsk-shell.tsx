"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Languages, LogOut } from "lucide-react";
import { logout } from "@/lib/access";

export function NorskShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#innhold" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-4">Hopp til innhold</a>
      <header className="border-b border-stone-200 bg-white/95">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight text-accent-900" aria-label="Norskverksted – forsiden">
            <span className="rounded-xl bg-accent-700 p-2 text-white"><Languages className="h-5 w-5" aria-hidden="true" /></span>
            <span className="text-lg">Norskverksted</span>
          </Link>
          <nav aria-label="Hovedmeny" className="flex items-center gap-4 text-sm sm:gap-6">
            <Link href="/personvern" aria-current={pathname === "/personvern" ? "page" : undefined} className="text-stone-600 hover:text-accent-800">Personvern</Link>
            <Link href="/verksted" aria-current={pathname === "/verksted" ? "page" : undefined} className="inline-flex items-center gap-1.5 rounded-lg bg-accent-700 px-4 py-2.5 font-medium text-white hover:bg-accent-800">
              Lag læringsark <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            {pathname === "/verksted" && <button type="button" onClick={logout} className="inline-flex items-center gap-1.5 text-stone-600 hover:text-accent-800"><LogOut className="h-4 w-4" aria-hidden="true" /><span>Logg ut</span></button>}
          </nav>
        </div>
      </header>
      <main id="innhold" className="flex-1">{children}</main>
      <footer className="border-t border-stone-200 bg-white px-5 py-6 text-xs text-stone-500 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <span>Norskverksted · Apexlab / Lervik KI-Tech ENK</span>
          <span>Laget for lærere i norskopplæringen</span>
          <Link href="/personvern" className="underline underline-offset-4">Personvern og tilgang</Link>
        </div>
      </footer>
    </div>
  );
}
