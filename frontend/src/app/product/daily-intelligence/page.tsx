import { Card, EmptyState, Status } from "@/components/product/ProductPrimitives";
import { initialDailyInsights } from "@/lib/dailyIntelligence";
import styles from "../page.module.css";

export default function DailyIntelligencePage() {
  return (
    <main className={styles.main}>
      <p className={styles.eyebrow}>Product preview</p>
      <h1 className={styles.title}>Daily Intelligence</h1>
      <p className={styles.lead}>
        A daily view of what matters. Verified sources and observation times are required
        before any brief, market view, or account insight can appear.
      </p>
      <Status priority="unknown" label="INTEGRATION PENDING" />
      <div className={styles.grid}>
        {initialDailyInsights.map((insight) => (
          <Card key={insight.id} id={`daily-${insight.id}`} title={insight.title} description={insight.purpose}>
            <EmptyState title="Unavailable" detail={insight.content.reason} />
          </Card>
        ))}
      </div>
    </main>
  );
}
