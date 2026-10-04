import Link from "next/link";
import { linkedNavigation, primaryNavigation } from "@/lib/productNavigation";
import styles from "./ProductNavigation.module.css";

function NavigationContents() {
  return (
    <>
      <p className={styles.brand}>ARMS + MEDAR</p>
      <ul className={styles.links}>
        {linkedNavigation().map((entry) => (
          <li key={entry.id}>
            <Link href={entry.href} title={entry.description} className={styles.link}>
              {entry.label}
            </Link>
          </li>
        ))}
      </ul>
      <p className={styles.planned}>
        Planned: {primaryNavigation.filter((entry) => entry.availability === "planned").map((entry) => entry.label).join(" · ")}
      </p>
    </>
  );
}

export function ProductNavigation() {
  return (
    <>
      <details className={styles.mobileNav}>
        <summary className={styles.mobileSummary}>Product navigation</summary>
        <nav aria-label="Product mobile" className={styles.mobilePanel}>
          <NavigationContents />
        </nav>
      </details>
      <nav aria-label="Product" className={`${styles.nav} ${styles.desktopNav}`}>
        <NavigationContents />
      </nav>
    </>
  );
}