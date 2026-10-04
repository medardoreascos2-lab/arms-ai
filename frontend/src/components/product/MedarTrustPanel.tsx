import type { ProductMedarResponse } from "@/lib/medarProduct";
import { trustSections } from "@/lib/medarTrust";
import styles from "./MedarConversation.module.css";

export function MedarTrustPanel({ response }: { response: ProductMedarResponse }) {
  const sections = trustSections(response);
  if (sections.length === 0) return null;
  return (
    <details className={styles.trustPanel}>
      <summary>Reasoning and evidence</summary>
      <div className={styles.trustGrid}>
        {sections.map((section) => (
          <section key={section.label} aria-label={section.label}>
            <h3>{section.label}</h3>
            <ul>{section.details.map((detail, index) => <li key={index}>{detail}</li>)}</ul>
          </section>
        ))}
      </div>
    </details>
  );
}
