import { localMedarEnabled, localMedarEndpoint } from "@/lib/medarLocalConfig";
import { decodeMedarResponse, degradedResponse } from "@/lib/medarProduct";

const headers = { "Cache-Control": "no-store" };
const idPattern = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;
const allowedFields = new Set([
  "request_id", "conversation_id", "message", "locale",
  "response_profile", "client_context",
]);

export async function POST(request: Request): Promise<Response> {
  let requestId = "invalid-request";
  let body: Record<string, unknown>;
  try {
    const raw = await request.text();
    if (raw.length > 16384) throw new Error("oversized request");
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("invalid request");
    }
    body = parsed as Record<string, unknown>;
    if (typeof body.request_id === "string" && idPattern.test(body.request_id)) {
      requestId = body.request_id;
    }
    if (
      !idPattern.test(String(body.request_id ?? ""))
      || !idPattern.test(String(body.conversation_id ?? ""))
      || typeof body.message !== "string"
      || body.message.trim().length < 1
      || body.message.length > 8192
      || Object.keys(body).some((key) => !allowedFields.has(key))
    ) {
      throw new Error("invalid request");
    }
  } catch {
    return Response.json(degradedResponse(requestId, "INVALID_REQUEST"), { headers });
  }

  if (!localMedarEnabled(process.env)) {
    return Response.json(degradedResponse(requestId, "LOCAL_TEST_DISABLED"), { headers });
  }
  const endpoint = localMedarEndpoint(process.env.PRODUCT_MEDAR_LOCAL_TEST_URL);
  const sessionId = process.env.PRODUCT_MEDAR_LOCAL_TEST_SESSION_ID;
  if (!endpoint || !sessionId || !/^synthetic-[A-Za-z0-9_.:-]+$/.test(sessionId)) {
    return Response.json(degradedResponse(requestId, "MEDAR_UNAVAILABLE"), { headers });
  }

  try {
    const upstream = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-ARMS-Local-Test-Session": sessionId,
      },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!upstream.ok) {
      return Response.json(degradedResponse(requestId, "MEDAR_UNAVAILABLE"), { headers });
    }
    const raw = await upstream.text();
    if (raw.length > 20000) {
      return Response.json(degradedResponse(requestId, "MEDAR_UNAVAILABLE"), { headers });
    }
    return Response.json(decodeMedarResponse(JSON.parse(raw), requestId), { headers });
  } catch {
    return Response.json(degradedResponse(requestId, "MEDAR_UNAVAILABLE"), { headers });
  }
}
