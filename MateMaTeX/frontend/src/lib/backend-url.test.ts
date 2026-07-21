import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEVELOPMENT_BACKEND_URL,
  PRODUCTION_BACKEND_URL,
  publicBackendUrl,
  serviceBackendUrl,
} from "./backend-url";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("backend URL resolution", () => {
  it("uses Render when a production environment variable is missing", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    expect(publicBackendUrl()).toBe(PRODUCTION_BACKEND_URL);
  });

  it("rejects a localhost environment variable in production", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    expect(publicBackendUrl()).toBe(PRODUCTION_BACKEND_URL);
    expect(serviceBackendUrl("http://127.0.0.1:8000/api/fag", "api/fag")).toBe(
      `${PRODUCTION_BACKEND_URL}/api/fag`,
    );
  });

  it("keeps localhost as the development fallback", () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    expect(publicBackendUrl()).toBe(DEVELOPMENT_BACKEND_URL);
  });

  it("prefers and normalizes explicit service URLs", () => {
    expect(serviceBackendUrl(" https://api.example.no/fag/ ", "api/fag")).toBe(
      "https://api.example.no/fag",
    );
  });
});
