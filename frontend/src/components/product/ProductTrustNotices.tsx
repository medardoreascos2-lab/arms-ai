import { financialDisclosureCopy, financialDisclosureKinds } from "@/lib/productTrust";
import { ConfidenceBadge } from "./ProductPrimitives";
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
export function AiLimitationsNotice({
  confidence,
  uncertainty,
  modelLimitation,
  memoryProvenance,
  humanReviewRecommended,
}: {
  confidence: number | null;
  uncertainty: string | null;
  modelLimitation: string;
  memoryProvenance: string | null;
  humanReviewRecommended: boolean;
}) {
  return (
    <section className={styles.notice} aria-labelledby="ai-limitations-heading">
      <h3 id="ai-limitations-heading" className={styles.heading}>AI limitations</h3>
      <div className={styles.aiGrid}>
        <div><strong>Confidence</strong><ConfidenceBadge value={confidence} /></div>
        <div><strong>Uncertainty</strong><p>{uncertainty || "UNKNOWN"}</p></div>
        <div><strong>Model limitation</strong><p>{modelLimitation}</p></div>
        <div><strong>Memory provenance</strong><p>{memoryProvenance || "No memory provenance was supplied."}</p></div>
        <div><strong>Human review</strong><p>{humanReviewRecommended ? "Recommended before decisions or actions." : "Use independent judgment."}</p></div>
      </div>
    </section>
  );
}