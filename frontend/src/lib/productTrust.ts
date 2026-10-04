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