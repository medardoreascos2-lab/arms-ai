import { financialDisclosureCopy, financialDisclosureKinds } from "@/lib/productTrust";
import styles from "./ProductTrustNotices.module.css";

export function FinancialDisclosureStrip() {
  return (
    <section className={styles.notice} aria-labelledby="financial-disclosure-heading">
      <h2 id="financial-disclosure-heading" className={styles.heading}>Financial mode disclosures</h2>
      <dl className={styles.disclosures}>
        {financialDisclosureKinds.map((kind) => (
          <div key={kind}>
            <dt>{kind.replaceAll("_", " ")}</dt>
            <dd>{financialDisclosureCopy[kind]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}