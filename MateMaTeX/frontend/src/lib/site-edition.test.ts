import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { isPublicPath } from "./access";
import { isLanguageSite, siteName } from "./site-edition";
import { middleware } from "../middleware";

afterEach(() => vi.unstubAllEnvs());

describe("independent language frontend", () => {
  it("keeps the whole platform and its access gate by default", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_EDITION", "");
    expect(isLanguageSite()).toBe(false);
    expect(siteName()).toBe("Skoleverksted");
    expect(isPublicPath("/")).toBe(false);
    for (const path of ["/fag", "/norsk", "/matematikk", "/projects", "/api/backend/estimate"]) {
      expect(middleware(new NextRequest(`https://skoleverksted.example${path}`)).headers.get("x-middleware-next")).toBe("1");
    }
  });

  it("opens only the language landing page and privacy notice without a code", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_EDITION", "norsk");
    expect(siteName()).toBe("Norskverksted");
    expect(isPublicPath("/")).toBe(true);
    expect(isPublicPath("/personvern")).toBe(true);
    for (const path of ["/verksted", "/norsk", "/fag", "/matematikk", "/api/norsk/generate"]) {
      expect(isPublicPath(path)).toBe(false);
    }
    for (const path of ["/", "/verksted", "/personvern"]) {
      expect(middleware(new NextRequest(`https://norskverksted.example${path}`)).headers.get("x-middleware-next")).toBe("1");
    }
  });

  it("does not expose other modules, shared history or mathematics proxies on the language site", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_EDITION", "norsk");
    for (const path of ["/fag", "/matematikk", "/history", "/projects", "/shared/abc", "/api/backend/estimate", "/api/generate/abc/stream"]) {
      expect(middleware(new NextRequest(`https://norskverksted.example${path}`)).status).toBe(404);
    }
  });

  it("preserves a language lesson's prefill when redirecting old module links", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_EDITION", "norsk");
    const response = middleware(new NextRequest("https://norskverksted.example/norsk?level=A2.1&topic=Biblioteket"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://norskverksted.example/verksted?level=A2.1&topic=Biblioteket");
  });

  it("does not select the restricted edition for an unknown flag", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_EDITION", "unknown");
    expect(isLanguageSite()).toBe(false);
    expect(isPublicPath("/")).toBe(false);
  });
});
