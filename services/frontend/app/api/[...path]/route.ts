import { auth } from "@/lib/auth";
import { createInternalAuthHeader, INTERNAL_AUTH_HEADER } from "@/lib/internal-auth";
import { logError, logEvent } from "@/lib/structured_logging";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const orchestratorUrl = process.env.ORCHESTRATOR_URL || "http://orchestrator:8000";
const allowedPaths = new Set(["analyze", "songs", "jobs", "usage"]);

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function proxyToOrchestrator(request: NextRequest, context: RouteContext) {
  const startedAt = Date.now();
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) {
    logEvent("frontend.proxy.rejected", {
      method: request.method,
      path: request.nextUrl.pathname,
      status: 401,
      reason: "unauthenticated",
    });
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const { path } = await context.params;
  const firstPath = path[0];
  if (!firstPath || !allowedPaths.has(firstPath)) {
    logEvent("frontend.proxy.rejected", {
      method: request.method,
      path: request.nextUrl.pathname,
      status: 404,
      reason: "unsupported_api_path",
    });
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const upstreamUrl = new URL(`/api/${path.map(encodeURIComponent).join("/")}`, orchestratorUrl);
  upstreamUrl.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  headers.delete("cookie");
  headers.delete("host");
  headers.delete("content-length");
  headers.set(INTERNAL_AUTH_HEADER, createInternalAuthHeader(session.user));

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    redirect: "manual",
    duplex: "half",
  };

  try {
    const response = await fetch(upstreamUrl, init);
    const responseHeaders = new Headers(response.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");
    logEvent("frontend.proxy.completed", {
      method: request.method,
      path: request.nextUrl.pathname,
      status: response.status,
      duration_ms: Date.now() - startedAt,
    });
    return new Response(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    logError("frontend.proxy.failed", error, {
      method: request.method,
      path: request.nextUrl.pathname,
      duration_ms: Date.now() - startedAt,
    });
    return NextResponse.json({ error: "Orchestrator unavailable" }, { status: 503 });
  }
}

export const GET = proxyToOrchestrator;
export const POST = proxyToOrchestrator;
export const PUT = proxyToOrchestrator;
export const PATCH = proxyToOrchestrator;
export const DELETE = proxyToOrchestrator;
