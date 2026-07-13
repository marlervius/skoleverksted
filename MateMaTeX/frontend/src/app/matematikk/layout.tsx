import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Matematikk — Skoleverksted",
  description: "LK20-oppgaver og prøver med matematisk verifisert fasit.",
};

export default function MatematikkLayout({ children }: { children: React.ReactNode }) {
  return children;
}
