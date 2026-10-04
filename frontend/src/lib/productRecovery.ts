export const degradedProductStatuses = [
  "MODEL_UNAVAILABLE",
  "MEMORY_UNAVAILABLE",
  "FINANCIAL_DATA_UNAVAILABLE",
  "AUTH_UNAVAILABLE",
  "PAYMENT_PROVIDER_UNAVAILABLE",
  "NETWORK_UNAVAILABLE",
  "PERMISSION_BLOCKED",
] as const;

export type DegradedProductStatus = typeof degradedProductStatuses[number];
export type RecoveryAction = "RETRY" | "REFRESH" | "DETAILS" | "REPORT_ISSUE";

export type DegradedProductState = Readonly<{
  status: DegradedProductStatus;
  detail: string;
  errorReference: string | null;
  data: null;
  syntheticFallbackUsed: false;
  actions: readonly RecoveryAction[];
}>;

export function degradedProductState(
  status: DegradedProductStatus,
  detail: string,
  errorReference: string | null = null,
): DegradedProductState {
  return Object.freeze({
    status,
    detail,
    errorReference,
    data: null,
    syntheticFallbackUsed: false,
    actions: Object.freeze(["RETRY", "REFRESH", "DETAILS", "REPORT_ISSUE"] as const),
  });
}