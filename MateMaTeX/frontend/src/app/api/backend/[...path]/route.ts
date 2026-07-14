import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

function backendBase(): string {
  return (
    process.env.MATE_BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_MATE_API_URL ||
    `${process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/matematikk`
  ).replace(/\/$/, "");
}

// Only the route prefixes the app actually uses may pass through. The proxy
// attaches the server-side API key, so an open passthrough would hand any
// visitor full authenticated access to the backend.
const ALLOWED_PREFIXES = new Set([
  "generate",
  "estimate",
  "editor",
  "exercises",
  "differentiation",
  "export",
  "sharing",
  "school",
  "m1",
]);

const MAX_BODY_BYTES = 2 * 1024 * 1024; // 2MB — largest legit payload is a LaTeX doc

async function proxyRequest(req: NextRequest, pathSegments: string[]) {
  const first = pathSegments[0] ?? "";
  if (!ALLOWED_PREFIXES.has(first)) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }

  const declaredLength = Number(req.headers.get("content-length") ?? 0);
  if (declaredLength > MAX_BODY_BYTES) {
    return Response.json({ detail: "Request body too large" }, { status: 413 });
  }

  const path = pathSegments.join("/");
  const search = req.nextUrl.search;
  const url = `${backendBase()}/${path}${search}`;

  const headers = new Headers();
  const key = process.env.MATE_API_KEY?.trim();
  if (key) {
    headers.set("X-API-Key", key);
  } else if (process.env.NODE_ENV === "production") {
    // Fail closed: never forward unauthenticated requests in production.
    return Response.json(
      { detail: "Server mangler MATE_API_KEY-konfigurasjon" },
      { status: 503 }
    );
  }
  const auth = req.headers.get("authorization");
  if (auth) {
    headers.set("Authorization", auth);
  }
  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }
  const accept = req.headers.get("accept");
  if (accept) {
    headers.set("Accept", accept);
  }
  const project = req.headers.get("x-skoleverksted-project");
  if (project) {
    headers.set("X-Skoleverksted-Project", project);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    cache: "no-store",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    const body = await req.arrayBuffer();
    if (body.byteLength > MAX_BODY_BYTES) {
      return Response.json({ detail: "Request body too large" }, { status: 413 });
    }
    init.body = body;
  }

  const upstream = await fetch(url, init);
  const responseHeaders = new Headers();
  const upstreamType = upstream.headers.get("content-type");
  if (upstreamType) {
    responseHeaders.set("Content-Type", upstreamType);
  }
  const disposition = upstream.headers.get("content-disposition");
  if (disposition) {
    responseHeaders.set("Content-Disposition", disposition);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

type RouteContext = {
  params: Promise<{ path: string[] }> | { path: string[] };
};

async function resolvePath(context: RouteContext): Promise<string[]> {
  const params = await Promise.resolve(context.params);
  return params.path;
}

export async function GET(req: NextRequest, context: RouteContext) {
  return proxyRequest(req, await resolvePath(context));
}

export async function POST(req: NextRequest, context: RouteContext) {
  return proxyRequest(req, await resolvePath(context));
}

export async function PUT(req: NextRequest, context: RouteContext) {
  return proxyRequest(req, await resolvePath(context));
}

export async function PATCH(req: NextRequest, context: RouteContext) {
  return proxyRequest(req, await resolvePath(context));
}

export async function DELETE(req: NextRequest, context: RouteContext) {
  return proxyRequest(req, await resolvePath(context));
}
