"use client";

import { useEffect, useState } from "react";
import { getSimNativeFinancial, type JsonObject } from "@/lib/dashboardApi";

const show = (value: unknown) => typeof value === "string" || typeof value === "number" ? String(value) : "—";

export function SimNativeFinancialView({ data }: { data: JsonObject | null }) {
  const available = data?.execution_domain === "SIM_NATIVE" && data?.native_account === "Sim101" &&
    data?.provider === "Simulator" && data?.instrument === "NQ DEC26" &&
    ["NO_OPERATION", "AWAITING_EXECUTION", "OPEN", "CLOSED"].includes(String(data?.status));
  const value = available ? data : null;
  const rows = [
    ["Open positions", value?.open_position_count], ["Closed trades", value?.closed_position_count],
    ["Journal", value?.journal_count], ["Direction", value?.direction], ["Quantity", value?.quantity],
    ["Entry", value?.entry_price], ["SL", value?.stop_loss], ["TP", value?.take_profit],
    ["Exit", value?.exit_price], ["Exit reason", value?.exit_reason], ["Realized PnL", value?.realized_pnl],
    ["Unrealized PnL (checkpoint)", value?.unrealized_pnl], ["Native order role", value?.order_role],
    ["Processed events", value?.processed_event_count], ["Pending events", value?.pending_dashboard_events],
    ["Last financial event", value?.last_financial_event_id],
  ];
  return <section aria-label="SIM_NATIVE Financial / Trade Lifecycle" className="mt-6 rounded-2xl border border-slate-700 bg-slate-900/50 p-6">
    <h2 className="text-lg font-semibold">SIM_NATIVE Financial / Trade Lifecycle</h2>
    <p className="mt-2 text-sm text-slate-300">Sim101 · Simulator · NQ DEC26 · Solo lectura. Registro financiero separado de PAPER.</p>
    <p role="status" className={`mt-3 font-semibold ${available ? "text-slate-100" : "text-amber-300"}`}>
      {value?.status === "NO_OPERATION" ? "NO OPERATION" : available ? show(value?.status) : "UNAVAILABLE"}
    </p>
    <dl className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map(([label, field]) => <div key={String(label)}><dt className="text-xs text-slate-400">{String(label)}</dt>
        <dd className="mt-1 break-words text-sm">{show(field)}</dd></div>)}
    </dl>
    <p className="mt-4 text-xs text-slate-400">Hechos financieros persistidos; no habilita admisiones ni ejecución. PnL no realizado del checkpoint, sin valoración de mercado en vivo.</p>
  </section>;
}

export default function SimNativeFinancialCard() {
  const [data, setData] = useState<JsonObject | null>(null);
  useEffect(() => {
    let stopped = false;
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;
    let staleTimer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    async function refresh() {
      controller = new AbortController();
      const requestStarted = Date.now();
      const deadline = setTimeout(() => controller?.abort(), 5000);
      try {
        const next = await getSimNativeFinancial(controller.signal);
        if (stopped) return;
        clearTimeout(staleTimer);
        // Use the service's evidence cadence, never invent a financial freshness authority.
        const budget = typeof next.observation_maximum_age_seconds === "number" ? next.observation_maximum_age_seconds * 1000 : 0;
        const age = typeof next.observation_age_seconds === "number" ? next.observation_age_seconds * 1000 : budget;
        const remaining = budget - age - (Date.now() - requestStarted);
        setData(remaining > 0 ? next : null);
        if (remaining > 0) staleTimer = setTimeout(() => setData(null), remaining);
        refreshTimer = setTimeout(refresh, Math.max(250, budget / 2 || 2500));
      } catch {
        if (!stopped) { setData(null); refreshTimer = setTimeout(refresh, 2500); }
      } finally { clearTimeout(deadline); }
    }
    void refresh();
    return () => { stopped = true; controller?.abort(); clearTimeout(refreshTimer); clearTimeout(staleTimer); };
  }, []);
  return <SimNativeFinancialView data={data} />;
}
