import { localFinancialEnabled, localFinancialEndpoint, type FinancialSurface } from "@/lib/financialLocalConfig";
import { decodeFinancialResponse, degradedFinancialResponse } from "@/lib/productFinancial";

const allowed = new Set<FinancialSurface>(["overview", "trading", "portfolio", "coach", "shadow"]);
const headers = { "Cache-Control": "no-store" };

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ surface: string }> },
): Promise<Response> {
  const { surface: rawSurface } = await params;
  if (!allowed.has(rawSurface as FinancialSurface)) {
    return Response.json(degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE"), {
      status: 404, headers,
    });
  }
  if (!localFinancialEnabled(process.env)) {
    return Response.json(degradedFinancialResponse("INTEGRATION_PENDING"), { headers });
  }
  const surface = rawSurface as FinancialSurface;
  const endpoint = localFinancialEndpoint(process.env.PRODUCT_FINANCIAL_LOCAL_TEST_URL, surface);
  const sessionId = process.env.PRODUCT_FINANCIAL_LOCAL_TEST_SESSION_ID;
  if (!endpoint || !sessionId || !/^synthetic-[A-Za-z0-9_.:-]+$/.test(sessionId)) {
    return Response.json(degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE"), { headers });
  }
  try {
    const upstream = await fetch(endpoint, {
      method: "GET",
      headers: { Accept: "application/json", "X-ARMS-Local-Test-Session": sessionId },
      cache: "no-store", credentials: "omit", redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    if (!upstream.ok) {
      return Response.json(degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE"), { headers });
    }
    const raw = await upstream.text();
    if (raw.length > 100000) {
      return Response.json(degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE"), { headers });
    }
    return Response.json(decodeFinancialResponse(JSON.parse(raw)), { headers });
  } catch {
    return Response.json(degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE"), { headers });
  }
}
