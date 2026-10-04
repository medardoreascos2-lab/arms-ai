/** Server-side local test configuration. Never accepts a non-loopback backend. */

export function localMedarEnabled(environment: Readonly<Record<string, string | undefined>>): boolean {
  return environment.NODE_ENV !== "production"
    && environment.PRODUCT_MEDAR_LOCAL_TEST_ENABLED === "true";
}

export function localMedarEndpoint(raw: string | undefined): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
        || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
      return null;
    }
    return new URL("/product/medar/conversations", url).toString();
  } catch {
    return null;
  }
}
