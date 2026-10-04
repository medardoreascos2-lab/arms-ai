import Link from "next/link";
import { linkedNavigation, primaryNavigation } from "@/lib/productNavigation";
import styles from "./ProductNavigation.module.css";

export function ProductNavigation() {
  return (
    <nav aria-label="Product" className={styles.nav}>
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
    </nav>
  );
}
