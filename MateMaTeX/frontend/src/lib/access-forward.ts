import type { NextRequest } from "next/server";

/**
 * Credentials the browser presented to this site, in the form the backend's
 * access gate expects. Event streams and downloads opened by the browser cannot
 * set headers, so they carry the token as `?access_token=` instead.
 */
export function forwardedAuthorization(req: NextRequest): string | undefined {
  const header = req.headers.get("authorization");
  if (header) return header;
  const token = req.nextUrl.searchParams.get("access_token");
  return token ? `Bearer ${token}` : undefined;
}
