import Link from "next/link";
import { Card, EmptyState } from "@/components/product/ProductPrimitives";
import styles from "../page.module.css";

export default function ProductSettingsPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Customer controls</p>
    <h1 className={styles.title}>Settings</h1>
    <div className={styles.grid}>
      <Card id="settings-profile" title="Profile" description="Display, language, theme, accessibility, and response preferences">
        <EmptyState title="Local foundation ready" detail="Production profile integration is pending." />
      </Card>
      <Card id="settings-privacy" title="Privacy" description="Memory, retention, services, export, and removal">
        <Link href="/product/settings/privacy">Open Privacy Center</Link>
      </Card>
      <Card id="settings-security" title="Security" description="Sessions, events, and permissions">
        <EmptyState title="Planned" detail="Security Center is the next milestone." />
      </Card>
    </div>
  </main>;
}
