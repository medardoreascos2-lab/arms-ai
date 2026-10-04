import { ProductNavigation } from "@/components/product/ProductNavigation";
import styles from "./product.module.css";

export default function ProductLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#product-content">Skip to Product content</a>
      <div className={styles.container}>
        <ProductNavigation />
        <div id="product-content" className={styles.content}>{children}</div>
      </div>
    </div>
  );
}