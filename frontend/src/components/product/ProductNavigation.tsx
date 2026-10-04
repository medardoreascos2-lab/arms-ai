import Link from "next/link";
import { linkedNavigation, primaryNavigation } from "@/lib/productNavigation";

export function ProductNavigation() {
  return (
    <nav aria-label="Product" className="rounded-2xl border border-slate-700 bg-slate-900 p-4 text-slate-100">
      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">ARMS + MEDAR</p>
      <ul className="flex flex-wrap gap-2">
        {linkedNavigation().map((entry) => (
          <li key={entry.id}>
            <Link href={entry.href} title={entry.description} className="inline-flex rounded-lg border border-slate-600 px-3 py-2 text-sm hover:border-cyan-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300">
              {entry.label}
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-slate-400">
        Planned: {primaryNavigation.filter((entry) => entry.availability === "planned").map((entry) => entry.label).join(" · ")}
      </p>
    </nav>
  );
}
