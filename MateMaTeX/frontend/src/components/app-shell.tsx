"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Sidebar } from "@/components/sidebar";
import { CommandPalette } from "@/components/command-palette";
import { PlatformSwitcher } from "@/components/platform-switcher";

const PAGE_TITLES: Record<string, string> = {
  "/": "Oversikt",
  "/fag": "Fag & læring",
  "/norsk": "Norsklæring",
  "/matematikk": "Matematikk",
  "/theme-pack": "Temapakke",
  "/projects": "Prosjekter",
  "/exercises": "Oppgavebank",
  "/templates": "Maler",
  "/history": "Historikk",
  "/school": "Skolens bank",
  "/shared": "Delt med meg",
  "/settings": "Innstillinger",
  "/personvern": "Personvern",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [cmdOpen, setCmdOpen] = useState(false);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Cmd+K — Command palette
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen((o) => !o);
      }
      // Cmd+N — New generation
      if ((e.metaKey || e.ctrlKey) && e.key === "n") {
        e.preventDefault();
        const destination = pathname.startsWith("/fag") ? "/fag" : pathname.startsWith("/norsk") ? "/norsk" : "/matematikk";
        window.location.assign(destination);
      }
      // Escape — Close modals
      if (e.key === "Escape") {
        setCmdOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [pathname]);

  // Get breadcrumb from path
  const pageTitle = PAGE_TITLES[pathname] || (pathname.startsWith("/projects/") ? "Prosjekt" : "");
  const isImmersiveWorkspace = pathname === "/fag" || pathname === "/norsk";

  return (
    <div className="min-h-screen flex">
      {/* Sidebar (desktop) */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile bottom bar */}
      <MobileBottomBar pathname={pathname} />

      {/* Main content area */}
      <div className="flex-1 md:ml-sidebar-collapsed lg:ml-sidebar min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-bg/90 backdrop-blur-md border-b border-border">
            <div className="relative mx-auto flex h-16 max-w-[1600px] items-center justify-between px-4 sm:px-6">
              <div className="flex items-center gap-3">
                <h1 className="hidden text-sm font-medium text-text-primary xl:block">
                  {pageTitle}
                </h1>
              </div>
              <div className="absolute left-1/2 hidden -translate-x-1/2 md:block">
                <PlatformSwitcher compact />
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCmdOpen(true)}
                  className="hidden md:flex items-center gap-2 px-3 py-1.5 text-xs text-text-muted border border-border rounded-lg hover:border-text-muted transition-colors"
                >
                  <span>Kommandoer</span>
                  <kbd className="px-1.5 py-0.5 text-[10px] bg-surface-elevated rounded font-mono">
                    ⌘K
                  </kbd>
                </button>
              </div>
            </div>
          </header>

        {/* Page content */}
        <main className={`${isImmersiveWorkspace ? "max-w-none" : "max-w-content mx-auto px-4 py-8 sm:px-6"} pb-24 md:pb-8`}>
          {children}
        </main>
      </div>

      {/* Command palette overlay */}
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </div>
  );
}

/* -----------------------------------------------------------------------
   Mobile bottom tab bar (< 768px)
   ----------------------------------------------------------------------- */
function MobileBottomBar({ pathname }: { pathname: string }) {
  const tabs = [
    { href: "/", label: "Oversikt", icon: "✦" },
    { href: "/fag", label: "Fag", icon: "▤" },
    { href: "/norsk", label: "Norsk", icon: "A" },
    { href: "/matematikk", label: "Matte", icon: "∑" },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-surface border-t border-border safe-area-inset-bottom">
      <div className="flex">
        {tabs.map((tab) => {
          const active = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] transition-colors ${
                active ? "text-accent-blue" : "text-text-muted"
              }`}
            >
              <span className="text-lg">{tab.icon}</span>
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
