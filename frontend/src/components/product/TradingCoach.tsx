"use client";

import { Card, EmptyState } from "./ProductPrimitives";
import { FinancialProjectionShell } from "./FinancialProjectionShell";
import styles from "./TradingCoach.module.css";

export function TradingCoach({ enabled }: { enabled: boolean }) {
  return <FinancialProjectionShell enabled={enabled} surface="coach">
    {(projection) => <div className={styles.grid}>
      <Card id="coach-summary" title="Review summary" description="Observation for reflection">
        <p className={styles.summary}>{projection.summary || "UNKNOWN"}</p>
      </Card>
      <Card id="coach-strengths" title="Strengths" description="Observed positive patterns">
        <Items values={projection.strengths} empty="No verified strengths were supplied." />
      </Card>
      <Card id="coach-review" title="Review items" description="Questions for your next review">
        <Items values={projection.review_items} empty="No verified review items were supplied." />
      </Card>
    </div>}
  </FinancialProjectionShell>;
}

function Items({ values, empty }: { values: readonly string[] | undefined; empty: string }) {
  if (!values?.length) return <EmptyState title="Unavailable" detail={empty} />;
  return <ul className={styles.list}>{values.map((value) => <li key={value}>{value}</li>)}</ul>;
}
