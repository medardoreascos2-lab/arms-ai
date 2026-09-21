"use client";

import { useEffect, useState } from "react";
import { requestJson } from "../../lib/dashboardApi";
import { analysisTimeRows } from "../../lib/marketAnalysisTimeProjection";

export default function MarketAnalysisPage() {
  const [snapshot, setSnapshot] = useState<unknown>(null);
  const [unavailable, setUnavailable] = useState(true);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let lease: ReturnType<typeof setTimeout>;
    let pending: AbortController | null = null;
    const clear = () => { if (active) { setSnapshot(null); setUnavailable(true); } };
    const poll = async () => {
      clear();
      pending = new AbortController();
      const request = pending;
      const timeout = setTimeout(() => request.abort(), 5000);
      try {
        const payload = await requestJson("/api/v2/market-analysis/time-profile", undefined, false, false, request.signal);
        if (active && !document.hidden) {
          setSnapshot(payload); setUnavailable(false);
          lease = setTimeout(clear, 2000);
        }
      } catch { clear(); }
      finally { clearTimeout(timeout); }
      if (active) timer = setTimeout(poll, 2000);
    };
    document.addEventListener("visibilitychange", clear);
    void poll();
    return () => {
      active = false; clearTimeout(timer); clearTimeout(lease); pending?.abort();
      document.removeEventListener("visibilitychange", clear);
    };
  }, []);
  return <main className="p-6 space-y-4">
    <h1 className="text-2xl font-bold">ARMS AI — ANALYSIS ONLY</h1>
    <p className="font-semibold">SOURCE_RELATIVE_ANALYSIS · ABSOLUTE_RECENCY_UNKNOWN</p>
    <p>LIVE describes observed local exporter activity. Absolute market recency, current session and news authority remain unproven.</p>
    <p>LOCAL_PAPER is the mode label only. PAPER entries and SIM execution are disabled; LIVE authority is NO. This page has no execution controls.</p>
    <p>Observations reflect the last response and expire locally after two seconds. Source-relative patterns are not trade recommendations.</p>
    <p>CERTIFIED_BOOTSTRAP_ONLY means initialized historical analysis, not a new LIVE observation. Complete bucket labels are open times. Trend requires 50 completed bars on each timeframe. A gap or conflicting overlap blocks the handoff.</p>
    {unavailable && <p role="status">BLOCKED — analysis service unavailable or awaiting a fresh response.</p>}
    <dl className="space-y-2">{analysisTimeRows(snapshot).map(([label, value]) =>
      <div key={label}><dt className="font-semibold">{label}</dt><dd className="break-all whitespace-pre-wrap">
        {typeof value === "string" ? value : JSON.stringify(value)}
      </dd></div>)}</dl>
  </main>;
}
