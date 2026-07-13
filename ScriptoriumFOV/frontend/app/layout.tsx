import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import "./globals.css";

export const metadata: Metadata = {
  title: "Scriptorium",
  description:
    "Generer PDF-læringsark for voksne innvandrere – tilpasset fag og språknivå",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="no" className={GeistSans.className}>
      <body className="antialiased">
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
