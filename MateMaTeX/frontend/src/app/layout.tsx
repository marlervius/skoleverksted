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
    <html
      lang="no"
      className="dark"
      suppressHydrationWarning
    >
      <body className="font-sans antialiased bg-bg text-text-primary">
        {/* Theme init script — avoids flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('theme');
                  if (stored === 'light') {
                    document.documentElement.classList.remove('dark');
                  } else if (!stored && window.matchMedia('(prefers-color-scheme: light)').matches) {
                    document.documentElement.classList.remove('dark');
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
        <ConditionalShell>{children}</ConditionalShell>
      </body>
    </html>
  );
}
