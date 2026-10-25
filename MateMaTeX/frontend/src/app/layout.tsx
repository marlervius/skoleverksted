import type { Metadata } from "next";
import "./globals.css";
import { AccessGate } from "@/components/access-gate";
import { ConditionalShell } from "@/components/conditional-shell";
import { isLanguageSite, LANGUAGE_SITE_URL, siteName } from "@/lib/site-edition";

export const metadata: Metadata = {
  title: {
    default: siteName(),
    template: "%s",
  },
  description:
    isLanguageSite()
      ? "Læringsark, oppgaver og begrepstrening for voksne som lærer norsk. Tilpass undervisningen til fag, tema og språknivå fra A1 til B2."
      : "Samlet lærerplattform for fagmateriell, norskopplæring og verifiserte matematikkoppgaver.",
  ...(isLanguageSite() ? { metadataBase: new URL(LANGUAGE_SITE_URL), openGraph: { siteName: "Norskverksted", locale: "nb_NO", type: "website" as const } } : {}),
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="no">
      <body className="font-sans antialiased bg-bg text-text-primary">
        <AccessGate>
          <ConditionalShell>{children}</ConditionalShell>
        </AccessGate>
      </body>
    </html>
  );
}
