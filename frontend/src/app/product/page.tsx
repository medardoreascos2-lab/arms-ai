import Link from "next/link";
import { initialHomeSections } from "@/lib/homeDashboard";

export default function ProductHomePage() {
  return (
    <main className="py-8">
      <p className="text-sm font-medium text-cyan-300">Product preview</p>
      <h1 className="mt-2 text-3xl font-semibold">Your Home</h1>
      <p className="mt-3 max-w-2xl text-slate-300">
        A clear place for daily context, risk, and next steps. Sections awaiting a
        verified source show their status instead of invented information.
      </p>
      <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {initialHomeSections.map((section) => (
          <section key={section.id} aria-labelledby={`home-${section.id}`} className="rounded-2xl border border-slate-700 bg-slate-900 p-5">
            <h2 id={`home-${section.id}`} className="text-lg font-semibold">{section.title}</h2>
            <p className="mt-1 text-sm text-slate-400">{section.purpose}</p>
            {section.content.state === "unavailable" && (
              <p className="mt-5 rounded-lg border border-amber-700/50 bg-amber-950/30 p-3 text-sm text-amber-100" role="status">
                Unavailable · {section.content.reason}
              </p>
            )}
            {section.content.state === "ready" && (
              <div className="mt-5 text-sm">
                <p>{section.content.summary}</p>
                <p className="mt-2 text-xs text-slate-400">Source: {section.content.source} · As of: {section.content.asOf}</p>
              </div>
            )}
            {section.content.state === "navigation" && (
              <ul className="mt-4 space-y-2">
                {section.content.actions.map((action) => (
                  <li key={action.href}>
                    <Link className="text-sm text-cyan-300 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300" href={action.href}>
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
