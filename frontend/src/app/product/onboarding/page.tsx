import { ProductOnboarding } from "@/components/product/ProductOnboarding";
import styles from "../page.module.css";

export default function ProductOnboardingPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Resumable local preview</p>
    <h1 className={styles.title}>Product onboarding</h1>
    <p className={styles.lead}>Choose goals, expectations, memory consent, notifications, and privacy preferences.</p>
    <ProductOnboarding />
  </main>;
}
