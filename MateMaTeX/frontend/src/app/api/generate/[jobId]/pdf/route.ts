import type { NextRequest } from "next/server";
import { internalServiceBackendUrl } from "@/lib/backend-url";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

/**
 * Proxies job PDF download so the browser never needs MATE_API_KEY.
 */
export async function GET(
  req: NextRequest,
  context: { params: Promise<{ jobId: string }> | { jobId: string } },
) {
  const { jobId } = await Promise.resolve(context.params);
  const backend = internalServiceBackendUrl(
    process.env.MATE_BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_MATE_API_URL,
    "api/matematikk",
  );

  const headers: Record<string, string> = {};
  const key = process.env.MATE_API_KEY?.trim();
  if (key) {
    headers["X-API-Key"] = key;
  }

  const preview = req.nextUrl.searchParams.get("preview") === "true";
  const url = `${backend}/generate/${encodeURIComponent(jobId)}/pdf${preview ? "?preview=true" : ""}`;
  const upstream = await fetch(url, { headers, cache: "no-store" });

  if (!upstream.ok) {
    const text = await upstream.text().catch(() => "");
    return new Response(text || `Upstream ${upstream.status}`, {
      status: upstream.status,
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/pdf",
      "Cache-Control": "private, max-age=0, must-revalidate",
    },
  });
}

/** Records the teacher's explicit approval of the exact verified revision. */
export async function POST(
  _req: NextRequest,
  context: { params: Promise<{ jobId: string }> | { jobId: string } },
) {
  const { jobId } = await Promise.resolve(context.params);
  const backend = internalServiceBackendUrl(
    process.env.MATE_BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_MATE_API_URL,
    "api/matematikk",
  );
  const headers: Record<string, string> = {};
  const key = process.env.MATE_API_KEY?.trim();
  if (key) headers["X-API-Key"] = key;

  const upstream = await fetch(
    `${backend}/generate/${encodeURIComponent(jobId)}/approve`,
    { method: "POST", headers, cache: "no-store" },
  );
  const body = await upstream.text().catch(() => "");
  return new Response(body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") || "application/json" },
  });
}
