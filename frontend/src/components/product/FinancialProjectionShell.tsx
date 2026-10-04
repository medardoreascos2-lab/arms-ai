"use client";

import { useEffect, useState, type ReactNode } from "react";
import { EmptyState, LoadingState, SourceBadge, Status } from "./ProductPrimitives";
import {
  isFinancialProjection, requestProductFinancial,
  type ProductFinancialProjection, type ProductFinancialResponse,
} from "@/lib/productFinancial";
import type { FinancialSurface } from "@/lib/financialLocalConfig";
import styles from "./FinancialProjectionShell.module.css";
import { FinancialDisclosureStrip } from "./ProductTrustNotices";

export function FinancialProjectionShell({ enabled, surface, children }: {
  enabled: boolean;
  surface: FinancialSurface;
  children: (projection: ProductFinancialProjection) => ReactNode;
}) {
  const [response, setResponse] = useState<ProductFinancialResponse | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    void requestProductFinancial(surface).then((value) => {
      if (active) setResponse(value);
    });
    return () => { active = false; };
  }, [enabled, surface]);

  if (!enabled) return <EmptyState title="Integration pending"
    detail="Local synthetic financial testing is disabled." />;
  if (response === null) return <LoadingState label={"Loading " + surface + " projection"} />;
  if (!isFinancialProjection(response)) return <EmptyState
    title={response.status.replaceAll("_", " ")}
    detail="The trusted read-only projection is unavailable." />;

  return <div className={styles.shell}>
    <FinancialDisclosureStrip />
    <div className={styles.statusRow}>
      <Status priority="information" label={response.source_status} />
      <Status priority="watch" label="READ ONLY" />
      <Status priority="watch" label="NOT REAL ACCOUNT DATA" />
    </div>
    {children(response)}
    {response.warnings.length > 0 && <section aria-label="Warnings">
      <h2>Warnings</h2><ul>{response.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
    </section>}
    <SourceBadge source={response.provenance.source_label} asOf={response.provenance.observed_at} />
  </div>;
}
