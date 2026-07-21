import { internalBackendUrl } from "@/lib/backend-url";

export const runtime = "edge";
export const dynamic = "force-dynamic";

/**
 * Keep-alive endpoint — pings the Render backend to prevent cold starts.
 * 
 * Triggered by Vercel cron (vercel.json) every 14 minutes during
 * Norwegian working hours (Mon-Fri 07:00-17:00).
 * 
 * Alternative: Use cron-job.org or UptimeRobot (free) to ping
 * https://matematex-api.onrender.com/health directly.
 */
export async function GET() {
  const apiUrl = internalBackendUrl();

  try {
    const res = await fetch(`${apiUrl}/health`, {
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.json();
    return Response.json({ ok: true, backend: data });
  } catch {
    return Response.json(
      { ok: false, error: "Backend unreachable" },
      { status: 503 }
    );
  }
}
