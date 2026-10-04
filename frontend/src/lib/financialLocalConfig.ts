/** Server-side local financial test configuration. Never accepts a non-loopback backend. */

export type FinancialSurface = "overview" | "trading" | "portfolio" | "coach" | "shadow";

export function localFinancialEnabled(environment: Readonly<Record<string, string | undefined>>): boolean {
  return environment.NODE_ENV !== "production"
    && environment.PRODUCT_FINANCIAL_LOCAL_TEST_ENABLED === "true";
}

export function localFinancialEndpoint(
  raw: string | undefined, surface: FinancialSurface,
): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
        || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
      return null;
    }
    return new URL("/product/financial/" + surface, url).toString();
  } catch {
    return null;
  }
}
