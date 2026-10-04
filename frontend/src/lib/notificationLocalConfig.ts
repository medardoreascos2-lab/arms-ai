/** Server-only local notification API configuration. */

export function localNotificationsEnabled(
  environment: Readonly<Record<string, string | undefined>>,
): boolean {
  return environment.NODE_ENV !== "production"
    && environment.PRODUCT_NOTIFICATIONS_LOCAL_TEST_ENABLED === "true";
}

export function localNotificationEndpoint(
  raw: string | undefined, relativePath: string,
): string | null {
  if (!raw || !/^notifications(?:\/[A-Za-z0-9_.:-]+\/(?:read|acknowledge|snooze|dismiss))?$/.test(relativePath)) {
    return null;
  }
  try {
    const url = new URL(raw);
    if (url.protocol !== "http:"
        || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
        || url.username || url.password || url.search || url.hash
        || url.pathname !== "/") {
      return null;
    }
    return new URL("/product/" + relativePath, url).toString();
  } catch {
    return null;
  }
}
