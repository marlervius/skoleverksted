export const PRODUCTION_BACKEND_URL = "https://skoleverksted-api.onrender.com";
export const DEVELOPMENT_BACKEND_URL = "http://localhost:8000";

function withoutTrailingSlash(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function isLocalUrl(value: string): boolean {
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  } catch {
    return false;
  }
}

function configuredUrl(value: string | undefined): string | undefined {
  const configured = value?.trim();
  if (!configured) return undefined;
  if (process.env.NODE_ENV === "production" && isLocalUrl(configured)) return undefined;
  return withoutTrailingSlash(configured);
}

/**
 * Resolve the shared backend without ever shipping a localhost fallback in a
 * production bundle. Environment variables may still override the default.
 */
export function publicBackendUrl(): string {
  const configured = configuredUrl(process.env.NEXT_PUBLIC_API_URL);
  const isProduction = process.env.NODE_ENV === "production";
  if (configured) return configured;

  return isProduction
    ? PRODUCTION_BACKEND_URL
    : DEVELOPMENT_BACKEND_URL;
}

export function serviceBackendUrl(
  configuredServiceUrl: string | undefined,
  servicePath: string,
): string {
  const configured = configuredUrl(configuredServiceUrl);
  if (configured) return configured;

  return `${publicBackendUrl()}/${servicePath.replace(/^\/+|\/+$/g, "")}`;
}

export function internalBackendUrl(): string {
  return configuredUrl(process.env.BACKEND_INTERNAL_URL) || publicBackendUrl();
}

export function internalServiceBackendUrl(
  configuredServiceUrl: string | undefined,
  servicePath: string,
): string {
  const configured = configuredUrl(configuredServiceUrl);
  if (configured) return configured;

  return `${internalBackendUrl()}/${servicePath.replace(/^\/+|\/+$/g, "")}`;
}
