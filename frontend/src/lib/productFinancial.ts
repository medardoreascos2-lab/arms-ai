import type { FinancialSurface } from "./financialLocalConfig.ts";

export type FinancialDegradedStatus =
  | "FINANCIAL_DATA_UNAVAILABLE" | "INTEGRATION_PENDING"
  | "ACCOUNT_SCOPE_UNAVAILABLE" | "PORTFOLIO_UNAVAILABLE" | "STALE_DATA"
  | "ENTITLEMENT_REQUIRED" | "SESSION_INVALID";

export type FinancialProvenance = Readonly<{
  source_id: string; source_label: string;
  classification: "SYNTHETIC" | "LOCAL_TEST_ONLY" | "NOT_REAL_ACCOUNT_DATA" | "UNKNOWN";
  observed_at: string | null; freshness_seconds: number | null;
  source_status: "AVAILABLE" | "SYNTHETIC" | "UNKNOWN";
}>;

export type ProductFinancialProjection = Readonly<{
  status: "READY" | "UNKNOWN"; provenance: FinancialProvenance;
  warnings: readonly string[]; investment_advice: false;
  execution_authorized: false; portfolio_mutation_authorized: false;
  source_status: "AVAILABLE" | "SYNTHETIC" | "UNKNOWN";
  headline?: string | null; instrument?: "NQ" | "MNQ" | "UNKNOWN";
  strengths?: readonly string[]; review_items?: readonly string[];
  evidence?: readonly string[];
  market_state?: string; risk_state?: string; session_state?: string; data_freshness?: string;
  total_value?: string | number | null; cash?: string | number | null;
  currency?: string; allocation?: readonly Readonly<{ label: string; percentage: string | number | null }>[];
  concentration?: string; risk?: string; drawdown?: string | number | null;
  summary?: string | null; confidence?: number | null;
  alerts?: readonly Readonly<{ alert_id: string; title: string; detail: string; severity: string }>[];
  trading?: ProductFinancialProjection | null; portfolio?: ProductFinancialProjection | null;
  coach?: ProductFinancialProjection | null; shadow_medar?: ProductFinancialProjection | null;
}>;

export type ProductFinancialDegraded = Readonly<{
  status: FinancialDegradedStatus; data: null; broker_authorized: false;
  portfolio_mutation_authorized: false; paper_authorized: false; live_authorized: false;
}>;

export type ProductFinancialResponse = ProductFinancialProjection | ProductFinancialDegraded;

const degraded = new Set<FinancialDegradedStatus>([
  "FINANCIAL_DATA_UNAVAILABLE", "INTEGRATION_PENDING", "ACCOUNT_SCOPE_UNAVAILABLE",
  "PORTFOLIO_UNAVAILABLE", "STALE_DATA", "ENTITLEMENT_REQUIRED", "SESSION_INVALID",
]);

export function degradedFinancialResponse(status: FinancialDegradedStatus): ProductFinancialDegraded {
  return { status, data: null, broker_authorized: false,
    portfolio_mutation_authorized: false, paper_authorized: false, live_authorized: false };
}

function validProvenance(value: unknown): value is FinancialProvenance {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.source_id === "string" && typeof item.source_label === "string"
    && ["SYNTHETIC", "LOCAL_TEST_ONLY", "NOT_REAL_ACCOUNT_DATA", "UNKNOWN"].includes(item.classification as string)
    && ["AVAILABLE", "SYNTHETIC", "UNKNOWN"].includes(item.source_status as string)
    && (item.observed_at === null || typeof item.observed_at === "string")
    && (item.freshness_seconds === null
      || (typeof item.freshness_seconds === "number" && Number.isInteger(item.freshness_seconds)
        && item.freshness_seconds >= 0));
}

export function decodeFinancialResponse(value: unknown): ProductFinancialResponse {
  if (!value || typeof value !== "object") return degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE");
  const item = value as Record<string, unknown>;
  if (degraded.has(item.status as FinancialDegradedStatus)) {
    if (item.data !== null || item.broker_authorized !== false
        || item.portfolio_mutation_authorized !== false
        || item.paper_authorized !== false || item.live_authorized !== false) {
      return degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE");
    }
    return degradedFinancialResponse(item.status as FinancialDegradedStatus);
  }
  if ((item.status !== "READY" && item.status !== "UNKNOWN")
      || !validProvenance(item.provenance)
      || !["AVAILABLE", "SYNTHETIC", "UNKNOWN"].includes(item.source_status as string)
      || item.investment_advice !== false || item.execution_authorized !== false
      || item.portfolio_mutation_authorized !== false) {
    return degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE");
  }
  return item as ProductFinancialProjection;
}

export async function requestProductFinancial(
  surface: FinancialSurface, fetcher: typeof fetch = fetch,
): Promise<ProductFinancialResponse> {
  try {
    const response = await fetcher("/api/product/financial/" + surface, {
      method: "GET", cache: "no-store", credentials: "same-origin",
    });
    if (!response.ok) return degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE");
    return decodeFinancialResponse(await response.json());
  } catch {
    return degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE");
  }
}

export function isFinancialProjection(
  response: ProductFinancialResponse,
): response is ProductFinancialProjection {
  return response.status === "READY" || response.status === "UNKNOWN";
}
