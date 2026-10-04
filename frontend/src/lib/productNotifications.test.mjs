import test from "node:test";
import assert from "node:assert/strict";
import {
  decodeNotificationInbox,
  filterNotifications,
  requestNotificationInbox,
  transitionNotification,
} from "./productNotifications.ts";
import {
  localNotificationEndpoint,
  localNotificationsEnabled,
} from "./notificationLocalConfig.ts";

const notification = {
  notification_id: "synthetic-notification-1",
  category: "SECURITY",
  priority: "CRITICAL",
  title: "Synthetic security review",
  summary: "Local fixture only.",
  source_type: "PRODUCT",
  source_reference: "synthetic-source-1",
  created_at: "2026-10-04T12:00:00Z",
  expires_at: null,
  status: "UNREAD",
  channels_requested: ["IN_APP"],
  requires_acknowledgement: true,
  metadata: {},
};

const ready = {
  status: "READY",
  notifications: [notification],
  source_status: "LOCAL_TEST_ONLY",
  external_delivery_authorized: false,
  financial_authority: false,
  execution_authorized: false,
  portfolio_mutation_authorized: false,
};

test("notification decoder requires all authority fields to remain false", () => {
  assert.equal(decodeNotificationInbox(ready).status, "READY");
  assert.equal(decodeNotificationInbox({
    ...ready, execution_authorized: true,
  }).status, "NOTIFICATION_DATA_UNAVAILABLE");
});

test("notification filters preserve critical and read state", () => {
  assert.deepEqual(filterNotifications(ready.notifications, {
    category: "SECURITY", priority: "CRITICAL", readState: "UNREAD",
  }), [notification]);
  assert.deepEqual(filterNotifications(ready.notifications, {
    category: "MEDAR", priority: "ALL", readState: "ALL",
  }), []);
});

test("notification client uses same-origin GET and explicit status POST", async () => {
  const calls = [];
  const fetcher = async (url, init) => {
    calls.push([url, init]);
    return { ok: true, json: async () => ready };
  };
  assert.equal((await requestNotificationInbox(fetcher)).status, "READY");

  const transitionFetcher = async (url, init) => {
    calls.push([url, init]);
    return { ok: true, json: async () => ({
      ...ready, notifications: undefined, notification: { ...notification, status: "READ" },
    }) };
  };
  assert.equal((await transitionNotification(
    notification.notification_id, "read", transitionFetcher,
  )).status, "READY");
  assert.deepEqual(calls.map(([url]) => url), [
    "/api/product/notifications",
    "/api/product/notifications/synthetic-notification-1/read",
  ]);
  assert.equal(calls[0][1].method, "GET");
  assert.equal(calls[1][1].method, "POST");
});

test("local notification config is nonproduction and loopback only", () => {
  assert.equal(localNotificationsEnabled({
    NODE_ENV: "development",
    PRODUCT_NOTIFICATIONS_LOCAL_TEST_ENABLED: "true",
  }), true);
  assert.equal(localNotificationsEnabled({
    NODE_ENV: "production",
    PRODUCT_NOTIFICATIONS_LOCAL_TEST_ENABLED: "true",
  }), false);
  assert.equal(localNotificationEndpoint(
    "http://127.0.0.1:8000/", "notifications",
  ), "http://127.0.0.1:8000/product/notifications");
  assert.equal(localNotificationEndpoint(
    "https://example.com/", "notifications",
  ), null);
  assert.equal(localNotificationEndpoint(
    "http://127.0.0.1:8000/", "notifications/id/send",
  ), null);
});

test("notification decoder rejects browser payloads containing scope identifiers", () => {
  assert.equal(decodeNotificationInbox({
    ...ready,
    notifications: [{ ...notification, tenant_id: "leaked-tenant" }],
  }).status, "NOTIFICATION_DATA_UNAVAILABLE");
  assert.equal(decodeNotificationInbox({
    ...ready,
    notifications: [{ ...notification, user_id: "leaked-user" }],
  }).status, "NOTIFICATION_DATA_UNAVAILABLE");
});