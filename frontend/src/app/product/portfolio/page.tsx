import { PortfolioGuardian } from "@/components/product/PortfolioGuardian";
import { localFinancialEnabled } from "@/lib/financialLocalConfig";
import styles from "../page.module.css";

export default function ProductPortfolioPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Read-only portfolio guardian</p>
    <h1 className={styles.title}>Portfolio</h1>
    <p className={styles.lead}>Customer-scoped value, allocation, risk, and alerts with no mutation controls.</p>
    <PortfolioGuardian enabled={localFinancialEnabled(process.env)} />
  </main>;
}
