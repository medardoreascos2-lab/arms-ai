"use client";

import { useEffect, useState } from "react";
import { Card, EmptyState, LoadingState, SourceBadge, Status } from "./ProductPrimitives";
import { isFinancialProjection, requestProductFinancial, type ProductFinancialResponse } from "@/lib/productFinancial";
import { initialDailyInsights } from "@/lib/dailyIntelligence";
import styles from "./DailyIntelligencePanel.module.css";

export function DailyIntelligencePanel({ localTestEnabled }: { localTestEnabled: boolean }) {
  const [response, setResponse] = useState<ProductFinancialResponse | null>(null);

  useEffect(() => {
    if (!localTestEnabled) return;
    let active = true;
    void requestProductFinancial("overview").then((value) => {
      if (active) setResponse(value);
    });
    return () => { active = false; };
  }, [localTestEnabled]);

  if (!localTestEnabled) {
    return <Unavailable status="INTEGRATION PENDING" reason="Local synthetic financial testing is disabled." />;
  }
  if (response === null) return <LoadingState label="Loading verified Daily Intelligence" />;
  if (!isFinancialProjection(response)) {
    return <Unavailable status={response.status.replaceAll("_", " ")}
      reason="A trusted daily financial projection is not available." />;
  }

  return (
    <div className={styles.panel}>
      <div className={styles.statusRow}>
        <Status priority="information" label={response.source_status} />
        <Status priority="watch" label="NOT REAL ACCOUNT DATA" />
      </div>
      <Card id="daily-BRIEF" title="Daily brief" description="Today''s verified overview">
        <p>{response.headline || "No headline was supplied."}</p>
      </Card>
      <Card id="daily-MARKET" title="Market context" description="Current market conditions and freshness">
        {response.trading ? <dl className={styles.facts}>
          <div><dt>Instrument</dt><dd>{response.trading.instrument || "UNKNOWN"}</dd></div>
          <div><dt>Market</dt><dd>{response.trading.market_state || "UNKNOWN"}</dd></div>
          <div><dt>Risk</dt><dd>{response.trading.risk_state || "UNKNOWN"}</dd></div>
          <div><dt>Session</dt><dd>{response.trading.session_state || "UNKNOWN"}</dd></div>
        </dl> : <EmptyState title="Unavailable" detail="No trading projection was supplied." />}
      </Card>
      <Card id="daily-PORTFOLIO" title="Portfolio context" description="Account-specific risk and exposure">
        {response.portfolio ? <dl className={styles.facts}>
          <div><dt>Total value</dt><dd>{response.portfolio.total_value ?? "UNKNOWN"}</dd></div>
          <div><dt>Cash</dt><dd>{response.portfolio.cash ?? "UNKNOWN"}</dd></div>
          <div><dt>Risk</dt><dd>{response.portfolio.risk || "UNKNOWN"}</dd></div>
        </dl> : <EmptyState title="Unavailable" detail="No portfolio projection was supplied." />}
      </Card>
      <Card id="daily-PRIORITIES" title="Review priorities" description="Items needing your attention">
        {response.alerts?.length ? <ul>{response.alerts.map((alert) =>
          <li key={alert.alert_id}>{alert.title}: {alert.detail}</li>)}</ul>
          : <EmptyState title="Unavailable" detail="No verified priorities were supplied." />}
      </Card>
      <SourceBadge source={response.provenance.source_label} asOf={response.provenance.observed_at} />
    </div>
  );
}

function Unavailable({ status, reason }: { status: string; reason: string }) {
  return <div className={styles.panel}>
    <Status priority="unknown" label={status} />
    <div className={styles.grid}>
      {initialDailyInsights.map((insight) => <Card key={insight.id}
        id={"daily-" + insight.id} title={insight.title} description={insight.purpose}>
        <EmptyState title="Unavailable" detail={reason} />
      </Card>)}
    </div>
  </div>;
}
