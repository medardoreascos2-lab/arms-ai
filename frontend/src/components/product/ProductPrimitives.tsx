import type { ReactNode } from "react";
import { formatConfidence } from "@/lib/productPresentation";
import styles from "./ProductPrimitives.module.css";

export type ProductPriority = "information" | "watch" | "important" | "critical" | "unknown";
export type RiskLevel = "low" | "watch" | "high" | "unknown";

export function Card({ id, title, description, children }: {
  id: string; title: string; description?: string; children: ReactNode;
}) {
  return <section aria-labelledby={id} className={styles.card}>
    <h2 id={id} className={styles.cardTitle}>{title}</h2>
    {description && <p className={styles.description}>{description}</p>}
    {children}
  </section>;
}

export function Metric({ label, value, kind, source, asOf }: {
  label: string; value: string; kind: "actual" | "paper" | "hypothetical";
  source: string | null; asOf: string | null;
}) {
  return <div className={styles.metric}>
    <span className={styles.description}>{label}</span>
    <strong className={styles.metricValue}>{value}</strong>
    <span className={styles.meta}>{kind.toUpperCase()}</span>
    <SourceBadge source={source} asOf={asOf} />
  </div>;
}

export function Status({ priority, label }: { priority: ProductPriority; label: string }) {
  return <span className={`${styles.badge} ${styles[priority]}`}>{label}</span>;
}

export function Alert({ priority, title, message }: {
  priority: ProductPriority; title: string; message: string;
}) {
  return <div className={styles.alert}>
    <Status priority={priority} label={priority.toUpperCase()} />
    <strong>{title}</strong>
    <p>{message}</p>
  </div>;
}

export function ConfidenceBadge({ value }: { value: number | null | undefined }) {
  const formatted = formatConfidence(value);
  return <span className={`${styles.badge} ${formatted === "Unknown" ? styles.unknown : styles.information}`}>
    Confidence: {formatted}
  </span>;
}

export function SourceBadge({ source, asOf }: { source: string | null; asOf: string | null }) {
  return <span className={styles.meta}>
    Source: {source || "Unknown"} · As of: {asOf || "Unknown"}
  </span>;
}

export function ReasoningSummary({ summary, factors }: {
  summary: string; factors?: readonly string[];
}) {
  return <div className={styles.reasoning}>
    <strong>Why this view</strong>
    <p>{summary}</p>
    {factors && factors.length > 0 && <ul>{factors.map((factor, index) => <li key={`${index}-${factor}`}>{factor}</li>)}</ul>}
  </div>;
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  const priority = level === "high" ? "important" : level === "low" ? "information" : level;
  return <Status priority={priority} label={`Risk: ${level.toUpperCase()}`} />;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className={styles.state}>
    <strong>{title}</strong>
    <p>{detail}</p>
  </div>;
}

export function LoadingState({ label = "Loading verified data" }: { label?: string }) {
  return <div className={styles.state} role="status" aria-busy="true">{label}</div>;
}

export function ErrorState({ title = "Data unavailable", detail }: {
  title?: string; detail: string;
}) {
  return <div className={styles.state} role="alert">
    <strong>{title}</strong>
    <p>{detail}</p>
  </div>;
}

export function PermissionState({ detail }: { detail: string }) {
  return <div className={styles.state}>
    <strong>Access unavailable</strong>
    <p>{detail}</p>
  </div>;
}
