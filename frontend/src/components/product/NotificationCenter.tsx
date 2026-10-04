"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyState, LoadingState, SourceBadge, Status } from "./ProductPrimitives";
import {
  filterNotifications,
  requestNotificationInbox,
  transitionNotification,
  type NotificationAction,
  type NotificationInboxResponse,
  type ProductNotification,
} from "@/lib/productNotifications";
import styles from "./NotificationCenter.module.css";

const categories = [
  "ALL", "FINANCIAL", "TRADING_COACH", "PORTFOLIO", "MEDAR",
  "SYSTEM", "SECURITY", "MEMORY", "PRODUCT",
];
const priorities = ["ALL", "INFO", "WATCH", "IMPORTANT", "CRITICAL"];

export function NotificationCenter({ enabled }: { enabled: boolean }) {
  const [response, setResponse] = useState<NotificationInboxResponse | null>(null);
  const [category, setCategory] = useState("ALL");
  const [priority, setPriority] = useState("ALL");
  const [readState, setReadState] = useState("ALL");
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    void requestNotificationInbox().then((value) => {
      if (active) setResponse(value);
    });
    return () => { active = false; };
  }, [enabled]);

  const visible = useMemo(() => filterNotifications(
    response?.status === "READY" ? response.notifications : [],
    { category, priority, readState },
  ), [response, category, priority, readState]);

  async function apply(item: ProductNotification, action: NotificationAction) {
    setBusy(item.notification_id + ":" + action);
    setActionError(null);
    const result = await transitionNotification(item.notification_id, action);
    if (result.status === "READY" && response?.status === "READY") {
      setResponse({
        ...response,
        notifications: response.notifications.map((current) =>
          current.notification_id === item.notification_id
            ? result.notification : current),
      });
    } else {
      setActionError(result.status.replaceAll("_", " "));
    }
    setBusy(null);
  }

  if (!enabled) return <EmptyState title="Integration pending"
    detail="Local notification testing is disabled." />;
  if (response === null) return <LoadingState label="Loading notification inbox" />;
  if (response.status !== "READY") return <EmptyState
    title={response.status.replaceAll("_", " ")}
    detail="The trusted notification inbox is unavailable." />;

  return <div className={styles.center}>
    <div className={styles.badges}>
      <Status priority="information" label={response.source_status} />
      <Status priority="watch" label="IN APP ONLY" />
      <Status priority="watch" label="NO EXTERNAL DELIVERY" />
    </div>
    <section className={styles.filters} aria-label="Notification filters">
      <label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}>
        {categories.map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <label>Priority<select value={priority} onChange={(event) => setPriority(event.target.value)}>
        {priorities.map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <label>Read state<select value={readState} onChange={(event) => setReadState(event.target.value)}>
        {["ALL", "UNREAD", "READ"].map((value) => <option key={value}>{value}</option>)}
      </select></label>
    </section>
    {actionError && <p role="alert" className={styles.error}>{actionError}</p>}
    <section aria-label="Notification inbox" className={styles.list}>
      {visible.length === 0
        ? <EmptyState title="No notifications" detail="No records match the current filters." />
        : visible.map((item) => <article key={item.notification_id}
            className={item.priority === "CRITICAL" ? styles.critical : styles.item}>
          <div className={styles.heading}>
            <div><Status priority={priorityStyle(item.priority)} label={item.priority} />
              <Status priority="unknown" label={item.status} /></div>
            <h2>{item.title}</h2>
          </div>
          <p>{item.summary}</p>
          <p className={styles.meta}>{item.category} · {item.source_type}</p>
          <SourceBadge source={item.source_reference} asOf={item.created_at} />
          <div className={styles.actions} aria-label={"Actions for " + item.title}>
            {item.status === "UNREAD" && <Action label="Mark read" action="read" item={item} busy={busy} apply={apply} />}
            {item.requires_acknowledgement && item.status !== "ACKNOWLEDGED"
              && item.status !== "DISMISSED"
              && <Action label="Acknowledge" action="acknowledge" item={item} busy={busy} apply={apply} />}
            {item.status !== "DISMISSED" && item.status !== "EXPIRED"
              && <Action label="Snooze" action="snooze" item={item} busy={busy} apply={apply} />}
            {item.status !== "DISMISSED" && (!item.requires_acknowledgement || item.status === "ACKNOWLEDGED")
              && <Action label="Dismiss" action="dismiss" item={item} busy={busy} apply={apply} />}
          </div>
        </article>)}
    </section>
  </div>;
}

function Action({ label, action, item, busy, apply }: {
  label: string;
  action: NotificationAction;
  item: ProductNotification;
  busy: string | null;
  apply: (item: ProductNotification, action: NotificationAction) => Promise<void>;
}) {
  const key = item.notification_id + ":" + action;
  return <button type="button" disabled={busy !== null}
    onClick={() => void apply(item, action)}>
    {busy === key ? "Updating…" : label}
  </button>;
}

function priorityStyle(priority: string): "information" | "watch" | "important" | "critical" {
  if (priority === "CRITICAL") return "critical";
  if (priority === "IMPORTANT") return "important";
  if (priority === "WATCH") return "watch";
  return "information";
}
