import {
  localNotificationEndpoint,
  localNotificationsEnabled,
} from "@/lib/notificationLocalConfig";
import {
  decodeNotificationTransition,
  unavailableNotifications,
  type NotificationAction,
} from "@/lib/productNotifications";

const actions = new Set<NotificationAction>(["read", "acknowledge", "snooze", "dismiss"]);
const headers = { "Cache-Control": "no-store" };

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ notificationId: string; action: string }> },
): Promise<Response> {
  const { notificationId, action: rawAction } = await params;
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(notificationId)
      || !actions.has(rawAction as NotificationAction)) {
    return Response.json(unavailableNotifications("PERMISSION_BLOCKED"), {
      status: 404, headers,
    });
  }
  if (!localNotificationsEnabled(process.env)) {
    return Response.json(unavailableNotifications("INTEGRATION_PENDING"), { headers });
  }
  const endpoint = localNotificationEndpoint(
    process.env.PRODUCT_NOTIFICATIONS_LOCAL_TEST_URL,
    "notifications/" + notificationId + "/" + rawAction,
  );
  const sessionId = process.env.PRODUCT_NOTIFICATIONS_LOCAL_TEST_SESSION_ID;
  if (!endpoint || !sessionId || !/^synthetic-[A-Za-z0-9_.:-]+$/.test(sessionId)) {
    return Response.json(unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE"), { headers });
  }
  try {
    const upstream = await fetch(endpoint, {
      method: "POST",
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
    return Response.json(decodeNotificationTransition(JSON.parse(raw)), { headers });
  } catch {
    return Response.json(unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE"), { headers });
  }
}
