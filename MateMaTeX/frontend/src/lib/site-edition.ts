/** One codebase, two independently deployed frontends. This flag is public. */
export function isLanguageSite(): boolean {
  return process.env.NEXT_PUBLIC_SITE_EDITION === "norsk";
}

export const LANGUAGE_SITE_URL = "https://norskverksted.vercel.app";

export function siteName(): string {
  return isLanguageSite() ? "Norskverksted" : "Skoleverksted";
}

export function languageRoute(pathname: string): "allow" | "workspace" | "missing" {
  if (["/", "/verksted", "/personvern"].includes(pathname)) return "allow";
  if (pathname === "/norsk") return "workspace";
  return "missing";
}
