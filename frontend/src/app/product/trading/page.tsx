import { TradingWorkspace } from "@/components/product/TradingWorkspace";
import { localFinancialEnabled } from "@/lib/financialLocalConfig";
import styles from "../page.module.css";

export default function ProductTradingPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Read-only financial workspace</p>
    <h1 className={styles.title}>Trading</h1>
    <p className={styles.lead}>Customer-scoped market and risk context with no order controls.</p>
    <TradingWorkspace enabled={localFinancialEnabled(process.env)} />
  </main>;
}
