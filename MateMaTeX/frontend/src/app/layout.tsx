import type { Metadata } from "next";
import "./globals.css";
import { ConditionalShell } from "@/components/conditional-shell";

export const metadata: Metadata = {
  title: {
    default: "Skoleverksted",
    template: "%s",
  },
  description:
    "Samlet lærerplattform for fagmateriell, norskopplæring og verifiserte matematikkoppgaver.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="no">
      <body className="font-sans antialiased bg-bg text-text-primary">
        <ConditionalShell>{children}</ConditionalShell>
      </body>
    </html>
  );
}
