import type { ProductMedarResponse } from "@/lib/medarProduct";
import { memoryCategories, memoryItems } from "@/lib/medarMemory";
import styles from "./MedarConversation.module.css";

export function MedarMemoryContext({ response }: { response: ProductMedarResponse }) {
  const items = memoryItems(response);
  if (response.answer === null) return null;
  return (
    <details className={styles.memoryPanel}>
      <summary>Memory context</summary>
      <p className={styles.note}>This view cannot change or delete durable memory.</p>
      {memoryCategories.map(([category, title]) => {
        const categoryItems = items.filter((item) => item.category === category);
        return (
          <section key={category} aria-label={title}>
            <h3>{title}</h3>
            {categoryItems.length === 0 ? (
              <p>Unavailable in this response.</p>
            ) : (
              <ul>{categoryItems.map((item) => (
                <li key={item.evidence_id}>
                  <strong>{item.summary}</strong>
                  <span>Provenance: {item.provenance}</span>
                  <span>Sensitivity: {item.sensitivity.toLowerCase()}</span>
                </li>
              ))}</ul>
            )}
          </section>
        );
      })}
      {response.memory_evidence.length > 0 && items.length === 0 && (
        <p className={styles.note}>Memory references lacked verified category, provenance, or sensitivity metadata.</p>
      )}
    </details>
  );
}
