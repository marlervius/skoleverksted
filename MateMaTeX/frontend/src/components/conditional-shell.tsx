"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/app-shell";

/**
 * Wraps most pages in AppShell. Shared-link views stay full-width without shell.
 */
export function ConditionalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const isShared = pathname.startsWith("/shared");

  if (isShared) {
    return <>{children}</>;
  }

  return <AppShell>{children}</AppShell>;
}
