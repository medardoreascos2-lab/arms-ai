import { DailyIntelligencePanel } from "@/components/product/DailyIntelligencePanel";
import { localFinancialEnabled } from "@/lib/financialLocalConfig";
import styles from "../page.module.css";

export default function DailyIntelligencePage() {
  return (
    <main className={styles.main}>
      <p className={styles.eyebrow}>Read-only financial intelligence</p>
      <h1 className={styles.title}>Daily Intelligence</h1>
      <p className={styles.lead}>
        A daily view of what matters. Verified sources and observation times are required
        before any brief, market view, or account insight can appear.
      </p>
      <DailyIntelligencePanel localTestEnabled={localFinancialEnabled(process.env)} />
    </main>
  );
}
