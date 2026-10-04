"use client";

import { Card, ConfidenceBadge, EmptyState, Status } from "./ProductPrimitives";
import { FinancialProjectionShell } from "./FinancialProjectionShell";
import styles from "./ShadowMedar.module.css";

export function ShadowMedar({ enabled }: { enabled: boolean }) {
  return <FinancialProjectionShell enabled={enabled} surface="shadow">
    {(projection) => <div className={styles.grid}>
      <Card id="shadow-summary" title="Shadow analysis" description="Parallel observation only">
        <div className={styles.badges}>
          <ConfidenceBadge value={projection.confidence} />
          <Status priority="watch" label="NO ACTION AUTHORITY" />
        </div>
        <p className={styles.summary}>{projection.summary || "UNKNOWN"}</p>
      </Card>
      <Card id="shadow-evidence" title="Evidence" description="Inputs supplied with this projection">
        {projection.evidence?.length
          ? <ul className={styles.evidence}>{projection.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
          : <EmptyState title="Unavailable" detail="No verified evidence was supplied." />}
      </Card>
    </div>}
  </FinancialProjectionShell>;
}
