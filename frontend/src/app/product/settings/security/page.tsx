import { Card, EmptyState, Status } from "@/components/product/ProductPrimitives";
import { securityCenterItems } from "@/lib/productSecurity";
import styles from "../../page.module.css";

export default function ProductSecurityPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Read-only security overview</p>
    <h1 className={styles.title}>Security Center</h1>
    <p className={styles.lead}>Review session, event, authentication-seam, and sensitive-permission status.</p>
    <Status priority="watch" label="NO AUTH PROVIDER PROVISIONING" />
    <div className={styles.grid}>
      {securityCenterItems.map((item) => <Card key={item.id}
        id={"security-" + item.id} title={item.title} description={item.detail}>
        <EmptyState title={item.status.replaceAll("_", " ")}
          detail="This view does not change credentials or permissions." />
      </Card>)}
    </div>
  </main>;
}
