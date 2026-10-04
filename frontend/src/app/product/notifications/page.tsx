import { NotificationCenter } from "@/components/product/NotificationCenter";
import { localNotificationsEnabled } from "@/lib/notificationLocalConfig";
import styles from "../page.module.css";

export default function ProductNotificationsPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Trusted in-app inbox</p>
    <h1 className={styles.title}>Notification Center</h1>
    <p className={styles.lead}>Review, acknowledge, snooze, and dismiss customer-scoped Product notifications.</p>
    <NotificationCenter enabled={localNotificationsEnabled(process.env)} />
  </main>;
}
