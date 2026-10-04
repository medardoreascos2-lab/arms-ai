import { ShadowMedar } from "@/components/product/ShadowMedar";
import { localFinancialEnabled } from "@/lib/financialLocalConfig";
import styles from "../page.module.css";

export default function ProductShadowMedarPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Read-only parallel analysis</p>
    <h1 className={styles.title}>Shadow MEDAR</h1>
    <p className={styles.lead}>An explainable comparison view with no advice, tool, memory-write, or trading authority.</p>
    <ShadowMedar enabled={localFinancialEnabled(process.env)} />
  </main>;
}
