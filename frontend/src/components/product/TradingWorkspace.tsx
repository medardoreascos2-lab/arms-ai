"use client";

import { Card } from "./ProductPrimitives";
import { FinancialProjectionShell } from "./FinancialProjectionShell";
import styles from "./TradingWorkspace.module.css";

export function TradingWorkspace({ enabled }: { enabled: boolean }) {
  return <FinancialProjectionShell enabled={enabled} surface="trading">
    {(projection) => <div className={styles.grid}>
      <Card id="trading-market" title="Market state" description="Observed context only">
        <Value label="Instrument" value={projection.instrument} />
        <Value label="Market state" value={projection.market_state} />
        <Value label="Session state" value={projection.session_state} />
      </Card>
      <Card id="trading-risk" title="Risk state" description="Read-only risk projection">
        <Value label="Risk" value={projection.risk_state} />
        <Value label="Freshness" value={projection.data_freshness} />
      </Card>
      <Card id="trading-authority" title="Authority" description="Execution remains unavailable">
        <Value label="Execution" value="DISABLED" />
        <Value label="PAPER" value="DISABLED" />
        <Value label="LIVE" value="DISABLED" />
      </Card>
    </div>}
  </FinancialProjectionShell>;
}

function Value({ label, value }: { label: string; value: string | undefined }) {
  return <p className={styles.value}><span>{label}</span><strong>{value || "UNKNOWN"}</strong></p>;
}
