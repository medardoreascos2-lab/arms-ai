import { ProductNavigation } from "@/components/product/ProductNavigation";

export default function ProductLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <ProductNavigation />
        {children}
      </div>
    </div>
  );
}
