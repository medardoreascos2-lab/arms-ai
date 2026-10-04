import Link from "next/link";
import { Card, EmptyState, SourceBadge } from "@/components/product/ProductPrimitives";
import { initialHomeSections } from "@/lib/homeDashboard";
import styles from "./page.module.css";

export default function ProductHomePage() {
  return (
    <main className={styles.main}>
      <p className={styles.eyebrow}>Product preview</p>
      <h1 className={styles.title}>Your Home</h1>
      <p className={styles.lead}>
        A clear place for daily context, risk, and next steps. Sections awaiting a
        verified source show their status instead of invented information.
      </p>
      <div className={styles.grid}>
        {initialHomeSections.map((section) => (
          <Card key={section.id} id={`home-${section.id}`} title={section.title} description={section.purpose}>
            {section.content.state === "unavailable" && (
              <EmptyState title="Unavailable" detail={section.content.reason} />
            )}
            {section.content.state === "ready" && (
              <div className={styles.summary}>
                <p>{section.content.summary}</p>
                <SourceBadge source={section.content.source} asOf={section.content.asOf} />
              </div>
            )}
            {section.content.state === "navigation" && (
              <ul className={styles.actions}>
                {section.content.actions.map((action) => (
                  <li key={action.href}>
                    <Link className={styles.actionLink} href={action.href}>
                      {action.label}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>
    </main>
  );
}
