export type NotificationCategory =
  | "FINANCIAL" | "TRADING_COACH" | "PORTFOLIO" | "MEDAR"
  | "SYSTEM" | "SECURITY" | "MEMORY" | "PRODUCT";
export type NotificationPriority = "INFO" | "WATCH" | "IMPORTANT" | "CRITICAL";
export type NotificationStatus =
  | "UNREAD" | "READ" | "ACKNOWLEDGED" | "SNOOZED" | "DISMISSED" | "EXPIRED";
export type NotificationAction = "read" | "acknowledge" | "snooze" | "dismiss";

export type ProductNotification = Readonly<{
  notification_id: string;
  category: NotificationCategory;
  priority: NotificationPriority;
  title: string;
  summary: string;
  source_type: string;
  source_reference: string;
  created_at: string;
  expires_at: string | null;
  status: NotificationStatus;
  channels_requested: readonly string[];
  requires_acknowledgement: boolean;
  metadata: Readonly<Record<string, unknown>>;
}>;

type Authority = Readonly<{
  external_delivery_authorized: false;
  financial_authority: false;
  execution_authorized: false;
  portfolio_mutation_authorized: false;
}>;

export type NotificationInboxReady = Authority & Readonly<{
  status: "READY";
  notifications: readonly ProductNotification[];
  source_status: "LOCAL_TEST_ONLY";
}>;

export type NotificationTransitionReady = Authority & Readonly<{
  status: "READY";
  notification: ProductNotification;
  source_status: "LOCAL_TEST_ONLY";
}>;

export type NotificationUnavailable = Authority & Readonly<{
  status: "INTEGRATION_PENDING" | "SESSION_INVALID" | "NOTIFICATION_DATA_UNAVAILABLE" | "PERMISSION_BLOCKED";
  notifications: readonly [];
}>;

export type NotificationInboxResponse = NotificationInboxReady | NotificationUnavailable;
export type NotificationTransitionResponse = NotificationTransitionReady | NotificationUnavailable;

const categories = new Set([
  "FINANCIAL", "TRADING_COACH", "PORTFOLIO", "MEDAR",
  "SYSTEM", "SECURITY", "MEMORY", "PRODUCT",
]);
const priorities = new Set(["INFO", "WATCH", "IMPORTANT", "CRITICAL"]);
const statuses = new Set([
  "UNREAD", "READ", "ACKNOWLEDGED", "SNOOZED", "DISMISSED", "EXPIRED",
]);
const degradedStatuses = new Set([
  "INTEGRATION_PENDING", "SESSION_INVALID",
  "NOTIFICATION_DATA_UNAVAILABLE", "PERMISSION_BLOCKED",
]);

export function unavailableNotifications(
  status: NotificationUnavailable["status"],
): NotificationUnavailable {
  return {
    status, notifications: [],
    external_delivery_authorized: false,
    financial_authority: false,
    execution_authorized: false,
    portfolio_mutation_authorized: false,
  };
}

function authoritiesAreFalse(item: Record<string, unknown>): boolean {
  return item.external_delivery_authorized === false
    && item.financial_authority === false
    && item.execution_authorized === false
    && item.portfolio_mutation_authorized === false;
}

function validNotification(value: unknown): value is ProductNotification {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.notification_id === "string"
    && !("user_id" in item) && !("tenant_id" in item)
    && categories.has(item.category as string)
    && priorities.has(item.priority as string)
    && statuses.has(item.status as string)
    && typeof item.title === "string" && typeof item.summary === "string"
    && typeof item.source_type === "string"
    && typeof item.source_reference === "string"
    && typeof item.created_at === "string"
    && (item.expires_at === null || typeof item.expires_at === "string")
    && Array.isArray(item.channels_requested)
    && typeof item.requires_acknowledgement === "boolean";
}

export function decodeNotificationInbox(value: unknown): NotificationInboxResponse {
  if (!value || typeof value !== "object") {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
  const item = value as Record<string, unknown>;
  if (!authoritiesAreFalse(item)) {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
  if (degradedStatuses.has(item.status as string)) {
    return unavailableNotifications(item.status as NotificationUnavailable["status"]);
  }
  if (item.status !== "READY" || item.source_status !== "LOCAL_TEST_ONLY"
      || !Array.isArray(item.notifications)
      || !item.notifications.every(validNotification)) {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
  return item as NotificationInboxReady;
}

export function decodeNotificationTransition(
  value: unknown,
): NotificationTransitionResponse {
  if (!value || typeof value !== "object") {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
  const item = value as Record<string, unknown>;
  if (!authoritiesAreFalse(item)) {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
  if (degradedStatuses.has(item.status as string)) {
    return unavailableNotifications(item.status as NotificationUnavailable["status"]);
  }
  if (item.status !== "READY" || item.source_status !== "LOCAL_TEST_ONLY"
      || !validNotification(item.notification)) {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
  return item as NotificationTransitionReady;
}

export async function requestNotificationInbox(
  fetcher: typeof fetch = fetch,
): Promise<NotificationInboxResponse> {
  try {
    const response = await fetcher("/api/product/notifications", {
      method: "GET", cache: "no-store", credentials: "same-origin",
    });
    if (!response.ok) return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
    return decodeNotificationInbox(await response.json());
  } catch {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
}

export async function transitionNotification(
  notificationId: string, action: NotificationAction,
  fetcher: typeof fetch = fetch,
): Promise<NotificationTransitionResponse> {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(notificationId)) {
    return unavailableNotifications("PERMISSION_BLOCKED");
  }
  try {
    const response = await fetcher(
      "/api/product/notifications/" + encodeURIComponent(notificationId) + "/" + action,
      { method: "POST", cache: "no-store", credentials: "same-origin" },
    );
    if (!response.ok) return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
    return decodeNotificationTransition(await response.json());
  } catch {
    return unavailableNotifications("NOTIFICATION_DATA_UNAVAILABLE");
  }
}

export function filterNotifications(
  items: readonly ProductNotification[],
  filters: Readonly<{ category: string; priority: string; readState: string }>,
): readonly ProductNotification[] {
  return items.filter((item) => {
    const readState = item.status === "UNREAD" ? "UNREAD" : "READ";
    return (filters.category === "ALL" || item.category === filters.category)
      && (filters.priority === "ALL" || item.priority === filters.priority)
      && (filters.readState === "ALL" || readState === filters.readState);
  });
}
