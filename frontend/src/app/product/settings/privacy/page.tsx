import { Card, EmptyState, Status } from "@/components/product/ProductPrimitives";
import { privacyCenterItems } from "@/lib/productPrivacy";
import styles from "../../page.module.css";

export default function ProductPrivacyPage() {
  return <main className={styles.main}>
    <p className={styles.eyebrow}>Privacy controls</p>
    <h1 className={styles.title}>Privacy Center</h1>
    <p className={styles.lead}>Review memory, retention, export, removal, connected-service, and activity seams.</p>
    <Status priority="watch" label="NO DIRECT DELETION" />
    <div className={styles.grid}>
      {privacyCenterItems.map((item) => <Card key={item.id}
        id={"privacy-" + item.id} title={item.title} description={item.description}>
        <EmptyState title={item.status.replaceAll("_", " ")}
          detail="A trusted production provider is not connected." />
      </Card>)}
    </div>
  </main>;
}
