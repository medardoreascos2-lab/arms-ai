"use client";

import { degradedProductState, type DegradedProductStatus } from "@/lib/productRecovery";
import styles from "./DegradedRecoveryPanel.module.css";

export function DegradedRecoveryPanel({
  status,
  detail,
  errorReference = null,
  onRetry,
  onReportIssue,
}: {
  status: DegradedProductStatus;
  detail: string;
  errorReference?: string | null;
  onRetry?: () => void;
  onReportIssue?: (errorReference: string | null) => void;
}) {
  const state = degradedProductState(status, detail, errorReference);
  return (
    <section className={styles.panel} role="alert" aria-labelledby="degraded-status-heading">
      <h2 id="degraded-status-heading">{state.status.replaceAll("_", " ")}</h2>
      <p>{state.detail}</p>
      <p className={styles.truth}>No fallback data has been substituted.</p>
      <div className={styles.actions} aria-label="Safe recovery actions">
        <button type="button" disabled={!onRetry} onClick={onRetry}>Retry</button>
        <button type="button" onClick={() => window.location.reload()}>Refresh</button>
        <details>
          <summary>Details</summary>
          <p>Error reference: {state.errorReference || "UNAVAILABLE"}</p>
        </details>
        <button type="button" disabled={!onReportIssue}
          onClick={() => onReportIssue?.(state.errorReference)}>Report issue</button>
      </div>
    </section>
  );
}