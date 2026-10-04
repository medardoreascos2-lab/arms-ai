"use client";

import { Card, EmptyState } from "./ProductPrimitives";
import { FinancialProjectionShell } from "./FinancialProjectionShell";
import styles from "./PortfolioGuardian.module.css";

export function PortfolioGuardian({ enabled }: { enabled: boolean }) {
  return <FinancialProjectionShell enabled={enabled} surface="portfolio">
    {(projection) => <div className={styles.grid}>
      <Card id="portfolio-summary" title="Portfolio summary" description="Trusted read-only account projection">
        <Value label="Total value" value={money(projection.total_value, projection.currency)} />
        <Value label="Cash" value={money(projection.cash, projection.currency)} />
      </Card>
      <Card id="portfolio-risk" title="Risk and drawdown" description="No exposure changes can be made here">
        <Value label="Risk" value={projection.risk} />
        <Value label="Concentration" value={projection.concentration} />
        <Value label="Drawdown" value={display(projection.drawdown)} />
      </Card>
      <Card id="portfolio-allocation" title="Allocation" description="Observed allocation from the supplied projection">
        {projection.allocation?.length ? <ul className={styles.list}>
          {projection.allocation.map((item) =>
            <li key={item.label}><span>{item.label}</span><strong>{display(item.percentage)}%</strong></li>)}
        </ul> : <EmptyState title="Unavailable" detail="No verified allocation was supplied." />}
      </Card>
      <Card id="portfolio-alerts" title="Portfolio alerts" description="Items requiring review">
        {projection.alerts?.length ? <ul className={styles.alerts}>
          {projection.alerts.map((alert) =>
            <li key={alert.alert_id}><strong>{alert.title}</strong><span>{alert.detail}</span></li>)}
        </ul> : <EmptyState title="Unavailable" detail="No verified portfolio alerts were supplied." />}
      </Card>
    </div>}
  </FinancialProjectionShell>;
}

function display(value: string | number | null | undefined) {
  return value === null || value === undefined ? "UNKNOWN" : String(value);
}

function money(value: string | number | null | undefined, currency: string | undefined) {
  return value === null || value === undefined ? "UNKNOWN" : display(value) + " " + (currency || "UNKNOWN");
}

function Value({ label, value }: { label: string; value: string | undefined }) {
  return <p className={styles.value}><span>{label}</span><strong>{value || "UNKNOWN"}</strong></p>;
}
