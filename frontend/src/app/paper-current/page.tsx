"use client";

import { useEffect, useState } from "react";
import { requestJson, type JsonObject } from "../../lib/dashboardApi";
import { currentPaperRows } from "../../lib/paperRcProjection";

export default function CurrentPaperPage() {
  const [snapshot, setSnapshot] = useState<JsonObject | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let pending: AbortController | null = null;
    const poll = async () => {
      pending = new AbortController();
      const request = pending;
      const timeout = setTimeout(() => request.abort(), 5000);
      try {
        const payload = await requestJson("/api/v2/backtesting/dashboard", undefined, false, false, request.signal);
        const value = payload.paper_research;
        if (!value || typeof value !== "object" || Array.isArray(value) ||
            value.mode !== "CURRENT_MARKET_PAPER" || typeof value.config_hash !== "string") {
          throw new Error("Current PAPER authority unavailable");
        }
        if (active) { setSnapshot(value); setError(""); }
      } catch (e) {
        if (active) { setSnapshot(null); setError(e instanceof Error ? e.message : "Unavailable"); }
      } finally {
        clearTimeout(timeout);
      }
      if (active) timer = setTimeout(poll, 2000);
    };
    void poll();
    return () => { active = false; clearTimeout(timer); pending?.abort(); };
  }, []);
  return <main className="p-6 space-y-4">
    <h1 className="text-2xl font-bold">ARMS AI — Current-market PAPER</h1>
    <p>LOCAL_PAPER uses internal ARMS simulated fills and bookkeeping. No NinjaTrader or prop account is traded.</p>
    <p>This page is read-only. Entries require the local launcher, certified market and news coverage, and risk approval. HOLD is a valid decision.</p>
    {error && <p role="alert">BLOCKED / unavailable: {error}</p>}
    {!snapshot && <p>Awaiting authoritative current PAPER state.</p>}
    {snapshot && <dl className="space-y-2">{currentPaperRows(snapshot).map(([label, value]) =>
      <div key={label}><dt className="font-semibold">{label}</dt><dd className="break-all whitespace-pre-wrap">
        {value === undefined || value === null ? "Not available / not evaluated" :
          typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </dd></div>)}</dl>}
  </main>;
}
