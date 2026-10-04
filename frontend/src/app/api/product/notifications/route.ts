import {
  localNotificationEndpoint,
  localNotificationsEnabled,
} from "@/lib/notificationLocalConfig";
import {
  decodeNotificationInbox,
  unavailableNotifications,
} from "@/lib/productNotifications";

const headers = { "Cache-Control": "no-store" };

export async function GET(): Promise<Response> {
  if (!localNotificationsEnabled(process.env)) {
    return Response.json(unavailableNotifications("INTEGRATION_PENDING"), { headers });
  }
  const endpoint = localNotificationEndpoint(
    process.env.PRODUCT_NOTIFICATIONS_LOCAL_TEST_URL, "notifications",
  );
  const sessionId = process.env.PRODUCT_NOTIFICATIONS_LOCAL_TEST_SESSION_ID;
  if (!endpoint || !sessionId || !/^synthetic-[A-Za-z0-9_.:-]+$/.test(sessionId)) {
    return Response.json(unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE"), { headers });
  }
  try {
    const upstream = await fetch(endpoint, {
      method: "GET",
      headers: { Accept: "application/json", "X-ARMS-Local-Test-Session": sessionId },
      cache: "no-store", credentials: "omit", redirect: "error",
      signal: AbortSignal.timeout(10000),
    });
    if (!upstream.ok) {
      return Response.json(unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE"), { headers });
    }
    const raw = await upstream.text();
    if (raw.length > 100000) {
      return Response.json(unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE"), { headers });
    }
    return Response.json(decodeNotificationInbox(JSON.parse(raw)), { headers });
  } catch {
    return Response.json(unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE"), { headers });
  }
}
