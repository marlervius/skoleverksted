/**
 * Client side of the shared access code that protects the pilot backend.
 *
 * The teacher signs in once with the code and gets a signed token that expires.
 * `fetch` calls to the backend get it as a bearer header automatically; links
 * and event streams that the browser opens without custom headers carry it as
 * `?access_token=` via {@link withAccessToken}.
 */
import { isPrivateSession } from "./private-storage";
import { publicBackendUrl } from "./backend-url";

export const ACCESS_STORAGE_KEY = "skoleverksted_access";
export const ACCESS_REQUIRED_EVENT = "skoleverksted:access-required";

/** Readable without a code: shared mathematics sheets and the privacy notice. */
const PUBLIC_PREFIXES = ["/shared", "/personvern"];

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/** Treat a token as expired slightly early so a request never lands on the edge. */
const EXPIRY_MARGIN_MS = 30_000;

interface StoredAccess {
  token: string;
  /** Epoch seconds, as issued by the server. */
  expiresAt: number;
}

export interface AccessStatus {
  required: boolean;
  authenticated: boolean;
  configured: boolean;
}

export class AccessLoginError extends Error {
  constructor(
    message: string,
    readonly code?: string,
    readonly retryAfter?: number,
  ) {
    super(message);
    this.name = "AccessLoginError";
  }
}

/** Only used when browser storage is blocked, so the session still works. */
let memoryAccess: StoredAccess | null = null;

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    // A private session must not leave anything behind on a shared computer.
    return isPrivateSession() ? window.sessionStorage : window.localStorage;
  } catch {
    return null;
  }
}

function parseStored(raw: string | null | undefined): StoredAccess | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<StoredAccess>;
    if (typeof value.token === "string" && typeof value.expiresAt === "number") {
      return { token: value.token, expiresAt: value.expiresAt };
    }
  } catch {
    /* corrupt value: treat as signed out */
  }
  return null;
}

function readAccess(): StoredAccess | null {
  const storage = browserStorage();
  if (!storage) return memoryAccess;
  try {
    return parseStored(storage.getItem(ACCESS_STORAGE_KEY));
  } catch {
    return memoryAccess;
  }
}

export function getAccessToken(nowMs: number = Date.now()): string | null {
  const stored = readAccess();
  if (!stored) return null;
  if (stored.expiresAt * 1000 - EXPIRY_MARGIN_MS <= nowMs) {
    clearAccessToken();
    return null;
  }
  return stored.token;
}

export function setAccessToken(token: string, expiresAt: number): void {
  const value: StoredAccess = { token, expiresAt };
  memoryAccess = value;
  const storage = browserStorage();
  if (!storage) return;
  try {
    storage.setItem(ACCESS_STORAGE_KEY, JSON.stringify(value));
    // Storage works and is now the source of truth, so clearing it signs out.
    memoryAccess = null;
  } catch {
    /* quota or blocked: the in-memory copy keeps this tab signed in */
  }
}

export function clearAccessToken(): void {
  memoryAccess = null;
  if (typeof window === "undefined") return;
  for (const read of [() => window.localStorage, () => window.sessionStorage]) {
    try {
      read().removeItem(ACCESS_STORAGE_KEY);
    } catch {
      /* storage unavailable */
    }
  }
}

/** Sign out and let the gate decide again from the server's answer. */
export function logout(): void {
  clearAccessToken();
  if (typeof window !== "undefined") window.location.reload();
}

function backendOrigins(): string[] {
  const urls = [
    publicBackendUrl(),
    process.env.NEXT_PUBLIC_VGS_API_URL,
    process.env.NEXT_PUBLIC_NORSK_API_URL,
    process.env.NEXT_PUBLIC_MATE_API_URL,
  ];
  const origins: string[] = [];
  for (const value of urls) {
    if (!value) continue;
    try {
      origins.push(new URL(value).origin);
    } catch {
      /* ignore a malformed override */
    }
  }
  return origins;
}

/**
 * True for the Skoleverksted backend and this site's own `/api/` routes (the
 * mathematics proxy). The token is never sent to any other host.
 */
export function isBackendRequest(rawUrl: string): boolean {
  if (typeof window === "undefined") return false;
  let url: URL;
  try {
    url = new URL(rawUrl, window.location.origin);
  } catch {
    return false;
  }
  if (url.origin === window.location.origin) return url.pathname.startsWith("/api/");
  return backendOrigins().includes(url.origin);
}

/** Append the token to a URL the browser opens itself (downloads, event streams). */
export function withAccessToken(url: string): string {
  const token = getAccessToken();
  if (!token || !isBackendRequest(url) || /[?&]access_token=/.test(url)) return url;
  return `${url}${url.includes("?") ? "&" : "?"}access_token=${encodeURIComponent(token)}`;
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

async function announceIfAccessRequired(response: Response): Promise<void> {
  try {
    const body = (await response.clone().json()) as { code?: string } | null;
    if (body?.code === "access_required") {
      clearAccessToken();
      window.dispatchEvent(new CustomEvent(ACCESS_REQUIRED_EVENT));
    }
  } catch {
    /* not a JSON error body */
  }
}

let interceptorInstalled = false;

/**
 * Wrap `window.fetch` once so every call to the backend carries the token and a
 * rejected token sends the teacher back to the sign-in screen. Callers that set
 * their own Authorization header keep it.
 */
export function installAccessInterceptor(): void {
  if (interceptorInstalled || typeof window === "undefined") return;
  interceptorInstalled = true;
  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    if (!isBackendRequest(requestUrl(input))) return originalFetch(input, init);

    let nextInit = init;
    const token = getAccessToken();
    if (token) {
      const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
      if (!headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
      nextInit = { ...init, headers };
    }

    const response = await originalFetch(input, nextInit);
    if (response.status === 401) void announceIfAccessRequired(response);
    return response;
  };
}

const accessBase = () => `${publicBackendUrl()}/api/platform/access`;

export async function fetchAccessStatus(): Promise<AccessStatus> {
  const token = getAccessToken();
  const response = await fetch(`${accessBase()}/status`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw new Error(`Access status failed: HTTP ${response.status}`);
  const data = (await response.json()) as Partial<AccessStatus>;
  return {
    required: data.required !== false,
    authenticated: data.authenticated === true,
    configured: data.configured !== false,
  };
}

/** Trade the shared code for a token and remember it. Throws {@link AccessLoginError}. */
export async function loginWithCode(code: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${accessBase()}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
  } catch {
    throw new AccessLoginError("Fikk ikke kontakt med serveren. Prøv igjen om litt.", "network");
  }
  const data = (await response.json().catch(() => ({}))) as {
    detail?: unknown;
    code?: string;
    retry_after?: number;
    token?: unknown;
    expires_at?: unknown;
  };
  if (!response.ok) {
    throw new AccessLoginError(
      typeof data.detail === "string" ? data.detail : "Kunne ikke logge inn.",
      data.code,
      typeof data.retry_after === "number" ? data.retry_after : undefined,
    );
  }
  if (typeof data.token === "string" && typeof data.expires_at === "number") {
    setAccessToken(data.token, data.expires_at);
  }
}
