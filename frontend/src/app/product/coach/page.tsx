import { TradingCoach } from "@/components/product/TradingCoach";
import { localFinancialEnabled } from "@/lib/financialLocalConfig";
import styles from "../page.module.css";

export default function ProductCoachPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Read-only review</p>
    <h1 className={styles.title}>Trading Coach</h1>
    <p className={styles.lead}>Evidence-backed reflection with no investment advice or execution authority.</p>
    <TradingCoach enabled={localFinancialEnabled(process.env)} />
  </main>;
}
