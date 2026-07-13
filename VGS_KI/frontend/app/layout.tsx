import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import "./globals.css";

export const metadata: Metadata = {
  title: "VGS Lærerassistent",
  description:
    "Generer profesjonelle læringsark og arbeidsark tilpasset videregående skole (VGS)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="no" className={GeistSans.className}>
      <body className="antialiased bg-stone-100 text-stone-900">{children}</body>
    </html>
  );
}
