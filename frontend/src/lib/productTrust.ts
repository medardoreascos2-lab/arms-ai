export const financialDisclosureKinds = [
  "ANALYSIS", "PAPER", "HYPOTHETICAL", "LIVE_UNAVAILABLE",
] as const;

export type FinancialDisclosureKind = typeof financialDisclosureKinds[number];

export const financialDisclosureCopy: Readonly<Record<FinancialDisclosureKind, string>> = {
  ANALYSIS: "Decision support only; no investment advice or execution authority.",
  PAPER: "Any paper result is simulated and remains separate from live trading.",
  HYPOTHETICAL: "Synthetic and projected outcomes are hypothetical, not actual results.",
  LIVE_UNAVAILABLE: "Live trading and real-money execution are unavailable.",
};
export type ProductProvenanceState = "CURRENT" | "UNKNOWN" | "INTEGRATION_PENDING";

export type ProductProvenance = Readonly<{
  source: string;
  asOf: string;
  freshness: string;
  state: ProductProvenanceState;
}>;

export function describeProductProvenance(input: Readonly<{
  source?: string | null;
  asOf?: string | null;
  freshnessSeconds?: number | null;
  integrationPending?: boolean;
}>): ProductProvenance {
  const source = input.source?.trim() || "UNKNOWN";
  const asOf = input.asOf?.trim() || "UNKNOWN";
  const validFreshness = typeof input.freshnessSeconds === "number"
    && Number.isInteger(input.freshnessSeconds) && input.freshnessSeconds >= 0;
  return Object.freeze({
    source,
    asOf,
    freshness: validFreshness ? `${input.freshnessSeconds}s` : "UNKNOWN",
    state: input.integrationPending ? "INTEGRATION_PENDING"
      : source === "UNKNOWN" || asOf === "UNKNOWN" ? "UNKNOWN" : "CURRENT",
  });
}