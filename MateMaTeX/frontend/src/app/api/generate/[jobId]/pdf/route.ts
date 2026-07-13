import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Proxies job PDF download so the browser never needs MATE_API_KEY.
 */
export async function GET(
  _req: NextRequest,
  context: { params: Promise<{ jobId: string }> | { jobId: string } },
) {
  const { jobId } = await Promise.resolve(context.params);
  const backend = (
    process.env.MATE_BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_MATE_API_URL ||
    `${process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/matematikk`
  ).replace(/\/$/, "");

  const headers: Record<string, string> = {};
  const key = process.env.MATE_API_KEY?.trim();
  if (key) {
    headers["X-API-Key"] = key;
  }

  const url = `${backend}/generate/${encodeURIComponent(jobId)}/pdf`;
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
