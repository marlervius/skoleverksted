import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";
import { forwardedAuthorization } from "./access-forward";

const ORIGIN = "https://skoleverksted.example";
const BACKEND = "https://api.skoleverksted.example";
const FUTURE = Math.floor(Date.now() / 1000) + 3600;

class MemoryStorage {
  private values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
  removeItem(key: string) {
    this.values.delete(key);
  }
}

type Access = typeof import("./access");

let access: Access;
let local: MemoryStorage;
let session: MemoryStorage;
let upstreamFetch: ReturnType<typeof vi.fn>;
let dispatched: Event[];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(async () => {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_API_URL", BACKEND);
  vi.stubEnv("NODE_ENV", "production");
  local = new MemoryStorage();
  session = new MemoryStorage();
  dispatched = [];
  upstreamFetch = vi.fn(async () => json({ ok: true }));
  vi.stubGlobal("window", {
    location: { origin: ORIGIN, reload: vi.fn() },
    localStorage: local,
    sessionStorage: session,
    fetch: upstreamFetch,
    dispatchEvent: (event: Event) => {
      dispatched.push(event);
      return true;
    },
  });
  // In a browser these bare globals are the very same objects as on `window`.
  vi.stubGlobal("fetch", upstreamFetch);
  vi.stubGlobal("localStorage", local);
  vi.stubGlobal("sessionStorage", session);
  access = await import("./access");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("access token storage", () => {
  it("remembers a token until shortly before it expires", () => {
    access.setAccessToken("sv1_token", FUTURE);
    expect(access.getAccessToken()).toBe("sv1_token");
    expect(local.getItem(access.ACCESS_STORAGE_KEY)).not.toBeNull();
    expect(access.getAccessToken((FUTURE - 20) * 1000)).toBeNull();
    expect(local.getItem(access.ACCESS_STORAGE_KEY)).toBeNull();
  });

  it("forgets the token on sign-out and ignores corrupt storage", () => {
    access.setAccessToken("sv1_token", FUTURE);
    access.clearAccessToken();
    expect(access.getAccessToken()).toBeNull();

    local.setItem(access.ACCESS_STORAGE_KEY, "{not json");
    expect(access.getAccessToken()).toBeNull();
    local.setItem(access.ACCESS_STORAGE_KEY, JSON.stringify({ token: 7 }));
    expect(access.getAccessToken()).toBeNull();
  });

  it("clearing browser data signs the teacher out", () => {
    access.setAccessToken("sv1_token", FUTURE);
    local.removeItem(access.ACCESS_STORAGE_KEY);
    expect(access.getAccessToken()).toBeNull();
  });

  it("keeps the token out of persistent storage in a private session", async () => {
    session.setItem("skoleverksted_private_session", "1");
    access.setAccessToken("sv1_token", FUTURE);
    expect(local.getItem(access.ACCESS_STORAGE_KEY)).toBeNull();
    expect(session.getItem(access.ACCESS_STORAGE_KEY)).not.toBeNull();
    expect(access.getAccessToken()).toBe("sv1_token");
  });

  it("falls back to memory when storage is blocked", () => {
    vi.stubGlobal("sessionStorage", undefined);
    vi.stubGlobal("window", {
      location: { origin: ORIGIN, reload: vi.fn() },
      get localStorage(): Storage {
        throw new Error("blocked");
      },
      get sessionStorage(): Storage {
        throw new Error("blocked");
      },
      fetch: upstreamFetch,
      dispatchEvent: () => true,
    });
    access.setAccessToken("sv1_memory", FUTURE);
    expect(access.getAccessToken()).toBe("sv1_memory");
    access.clearAccessToken();
    expect(access.getAccessToken()).toBeNull();
  });
});

describe("which requests carry the token", () => {
  it("covers the backend and this site's own API routes only", () => {
    expect(access.isBackendRequest(`${BACKEND}/api/platform/jobs`)).toBe(true);
    expect(access.isBackendRequest("/api/backend/estimate")).toBe(true);
    expect(access.isBackendRequest(`${ORIGIN}/api/generate/abc/stream`)).toBe(true);
    expect(access.isBackendRequest("/fag")).toBe(false);
    expect(access.isBackendRequest("https://commons.wikimedia.org/api/rest_v1/page")).toBe(false);
    expect(access.isBackendRequest("https://evil.example/api/platform/jobs")).toBe(false);
    expect(access.isBackendRequest("http://[bad")).toBe(false);
  });

  it("also covers separately deployed module URLs", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_NORSK_API_URL", "https://norsk.example/api/norsk");
    const reloaded = await import("./access");
    expect(reloaded.isBackendRequest("https://norsk.example/api/norsk/health")).toBe(true);
  });

  it("treats the public pages as readable without a code", () => {
    for (const path of ["/shared", "/shared/abc123", "/personvern"]) expect(access.isPublicPath(path)).toBe(true);
    for (const path of ["/", "/fag", "/sharedx", "/personvern-fake", "/projects/shared"]) {
      expect(access.isPublicPath(path)).toBe(false);
    }
  });

  it("adds the token to URLs the browser opens itself", () => {
    expect(access.withAccessToken(`${BACKEND}/api/platform/x`)).toBe(`${BACKEND}/api/platform/x`);

    access.setAccessToken("sv1_abc", FUTURE);
    expect(access.withAccessToken(`${BACKEND}/api/platform/x`)).toBe(`${BACKEND}/api/platform/x?access_token=sv1_abc`);
    expect(access.withAccessToken(`${BACKEND}/api/fag/d?preview=true`)).toBe(
      `${BACKEND}/api/fag/d?preview=true&access_token=sv1_abc`,
    );
    expect(access.withAccessToken(`${BACKEND}/api/x?access_token=old`)).toBe(`${BACKEND}/api/x?access_token=old`);
    expect(access.withAccessToken("https://other.example/file.pdf")).toBe("https://other.example/file.pdf");
  });
});

describe("fetch interceptor", () => {
  async function installAndGetFetch() {
    access.installAccessInterceptor();
    return (globalThis as unknown as { window: { fetch: typeof fetch } }).window.fetch;
  }

  it("sends the bearer token to the backend and nowhere else", async () => {
    access.setAccessToken("sv1_abc", FUTURE);
    const guarded = await installAndGetFetch();

    await guarded(`${BACKEND}/api/platform/jobs`);
    await guarded("https://commons.wikimedia.org/w/api.php");

    const [, backendInit] = upstreamFetch.mock.calls[0];
    expect(new Headers(backendInit.headers).get("Authorization")).toBe("Bearer sv1_abc");
    const [, otherInit] = upstreamFetch.mock.calls[1];
    expect(otherInit).toBeUndefined();
  });

  it("keeps headers a caller set itself", async () => {
    access.setAccessToken("sv1_abc", FUTURE);
    const guarded = await installAndGetFetch();

    await guarded(`${BACKEND}/api/norsk/x`, { headers: { Authorization: "Bearer own", "X-Skoleverksted-Project": "p1" } });

    const headers = new Headers(upstreamFetch.mock.calls[0][1].headers);
    expect(headers.get("Authorization")).toBe("Bearer own");
    expect(headers.get("X-Skoleverksted-Project")).toBe("p1");
  });

  it("installs only once", async () => {
    access.installAccessInterceptor();
    const first = (globalThis as unknown as { window: { fetch: typeof fetch } }).window.fetch;
    access.installAccessInterceptor();
    expect((globalThis as unknown as { window: { fetch: typeof fetch } }).window.fetch).toBe(first);
  });

  it("sends the teacher back to sign-in when the server says access is required", async () => {
    vi.stubGlobal("CustomEvent", class extends Event {
      constructor(type: string) {
        super(type);
      }
    });
    access.setAccessToken("sv1_abc", FUTURE);
    upstreamFetch.mockResolvedValueOnce(json({ code: "access_required", detail: "Tilgangskode kreves." }, 401));
    const guarded = await installAndGetFetch();

    const response = await guarded(`${BACKEND}/api/platform/jobs`);
    expect(response.status).toBe(401);
    await vi.waitFor(() => expect(dispatched.map((event) => event.type)).toContain(access.ACCESS_REQUIRED_EVENT));
    expect(access.getAccessToken()).toBeNull();
    // The caller can still read the body that the interceptor peeked at.
    expect((await response.json()).code).toBe("access_required");
  });

  it("does not sign out for unrelated 401s such as a wrong module password", async () => {
    access.setAccessToken("sv1_abc", FUTURE);
    upstreamFetch.mockResolvedValueOnce(json({ detail: "Feil passord." }, 401));
    const guarded = await installAndGetFetch();

    await guarded(`${BACKEND}/api/norsk/auth/verify`);
    await Promise.resolve();
    expect(dispatched).toHaveLength(0);
    expect(access.getAccessToken()).toBe("sv1_abc");
  });
});

describe("signing in", () => {
  it("stores the token returned for a correct code", async () => {
    upstreamFetch.mockResolvedValueOnce(json({ required: true, token: "sv1_new", expires_at: FUTURE }));

    await access.loginWithCode("riktig");

    const [url, init] = upstreamFetch.mock.calls[0];
    expect(url).toBe(`${BACKEND}/api/platform/access/login`);
    expect(JSON.parse(init.body)).toEqual({ code: "riktig" });
    expect(access.getAccessToken()).toBe("sv1_new");
  });

  it("reports a wrong code and a throttled client with the server's wording", async () => {
    upstreamFetch.mockResolvedValueOnce(json({ detail: "Feil tilgangskode.", code: "invalid_access_code" }, 401));
    await expect(access.loginWithCode("feil")).rejects.toMatchObject({
      name: "AccessLoginError",
      message: "Feil tilgangskode.",
      code: "invalid_access_code",
    });

    upstreamFetch.mockResolvedValueOnce(
      json({ detail: "For mange forsøk.", code: "too_many_attempts", retry_after: 42 }, 429),
    );
    await expect(access.loginWithCode("feil")).rejects.toMatchObject({ code: "too_many_attempts", retryAfter: 42 });
    expect(access.getAccessToken()).toBeNull();
  });

  it("explains a network failure instead of throwing a raw error", async () => {
    upstreamFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(access.loginWithCode("x")).rejects.toMatchObject({ code: "network" });
  });

  it("asks the server whether this browser is already signed in", async () => {
    access.setAccessToken("sv1_abc", FUTURE);
    upstreamFetch.mockResolvedValueOnce(json({ required: true, authenticated: true, configured: true }));

    await expect(access.fetchAccessStatus()).resolves.toEqual({ required: true, authenticated: true, configured: true });
    const [url, init] = upstreamFetch.mock.calls[0];
    expect(url).toBe(`${BACKEND}/api/platform/access/status`);
    expect(init.headers.Authorization).toBe("Bearer sv1_abc");
  });

  it("fails closed when the status answer is malformed or the server errors", async () => {
    upstreamFetch.mockResolvedValueOnce(json({}));
    await expect(access.fetchAccessStatus()).resolves.toEqual({ required: true, authenticated: false, configured: true });

    upstreamFetch.mockResolvedValueOnce(json({ detail: "boom" }, 500));
    await expect(access.fetchAccessStatus()).rejects.toThrow("HTTP 500");
  });
});

describe("forwarding credentials through this site's routes", () => {
  const request = (headers: Record<string, string>, query = "") =>
    ({ headers: new Headers(headers), nextUrl: new URL(`${ORIGIN}/api/generate/abc/stream${query}`) }) as unknown as NextRequest;

  it("prefers the header and falls back to the URL token for event streams", () => {
    expect(forwardedAuthorization(request({ authorization: "Bearer h" }, "?access_token=q"))).toBe("Bearer h");
    expect(forwardedAuthorization(request({}, "?access_token=q"))).toBe("Bearer q");
    expect(forwardedAuthorization(request({}))).toBeUndefined();
  });
});
