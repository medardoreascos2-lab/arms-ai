import Link from "next/link";
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
          <section key={section.id} aria-labelledby={`home-${section.id}`} className={styles.section}>
            <h2 id={`home-${section.id}`} className={styles.sectionTitle}>{section.title}</h2>
            <p className={styles.purpose}>{section.purpose}</p>
            {section.content.state === "unavailable" && (
              <p className={styles.unavailable}>
                Unavailable · {section.content.reason}
              </p>
            )}
            {section.content.state === "ready" && (
              <div className={styles.summary}>
                <p>{section.content.summary}</p>
                <p className={styles.provenance}>Source: {section.content.source} · As of: {section.content.asOf}</p>
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
          </section>
        ))}
      </div>
    </main>
  );
}
