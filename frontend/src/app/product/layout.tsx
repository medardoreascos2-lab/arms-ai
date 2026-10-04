import { ProductNavigation } from "@/components/product/ProductNavigation";
import styles from "./product.module.css";

export default function ProductLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className={styles.shell}>
      <div className={styles.container}>
        <ProductNavigation />
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}