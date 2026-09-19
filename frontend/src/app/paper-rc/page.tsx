"use client";

import { useEffect, useRef, useState } from "react";
import { configurePaperCredential, requestJson, type JsonObject } from "../../lib/dashboardApi";
import { paperRcRows } from "../../lib/paperRcProjection";

export default function PaperRcPage() {
  const [snapshot, setSnapshot] = useState<JsonObject | null>(null);
  const [error, setError] = useState("");
  const [credential, setCredential] = useState("");
  const [busy, setBusy] = useState(false);
  const commandInFlight = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (commandInFlight.current) {
        if (active) timer = setTimeout(poll, 2000);
        return;
      }
      const version = generation.current;
      try {
        const payload = await requestJson("/api/v2/backtesting/dashboard");
        const value = payload.paper_research;
        if (!value || typeof value !== "object" || Array.isArray(value) ||
            !["PAPER_RESEARCH", "PRODUCTION_POLICY", "HISTORICAL_RESEARCH"].includes(String(value.mode)) ||
            typeof value.config_hash !== "string") {
          throw new Error("PAPER RC authority unavailable");
        }
        if (active && version === generation.current) { setSnapshot(value); setError(""); }
      } catch (e) {
        if (active && version === generation.current) { setSnapshot(null); setError(e instanceof Error ? e.message : "Unavailable"); }
      }
      if (active) timer = setTimeout(poll, 2000);
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, []);

  async function control(command: string) {
    if (commandInFlight.current) return;
    commandInFlight.current = true;
    generation.current++;
    setBusy(true);
    setSnapshot(null);
    try {
      configurePaperCredential(credential);
      const value = await requestJson(`/api/v2/paper/${command}`, {}, true);
      setSnapshot(value);
      setError("");
    } catch (e) {
      setSnapshot(null);
      setError(e instanceof Error ? e.message : "Command rejected");
    } finally {
      generation.current++;
      commandInFlight.current = false;
      setBusy(false);
    }
  }

  return <main className="p-6 space-y-4">
    <h1 className="text-2xl font-bold">ARMS AI — PAPER RC</h1>
    <p>Certified historical replay • Research only • No live trading certification</p>
    <p>Restart requires reconciliation. Persisted evidence is not an operationally restored account.</p>
    <label>Administrative PAPER credential <input type="password" autoComplete="off"
      value={credential} onChange={(e) => setCredential(e.target.value)} className="border p-1" /></label>
    <div className="flex gap-3 flex-wrap">
      {["enable", "disable", "emergency_block", "step", "shutdown"].map(command =>
        <button key={command} disabled={busy} onClick={() => void control(command)}
          className="border p-2 disabled:opacity-50">{command.replaceAll("_", " ")}</button>)}
    </div>
    {error && <p role="alert">BLOCKED / unavailable: {error}</p>}
    {!snapshot && <p>Awaiting authoritative PAPER state. Execution readiness is unknown.</p>}
    {snapshot && <dl className="space-y-2">{paperRcRows(snapshot).map(([label, value]) =>
      <div key={label}><dt className="font-semibold">{label}</dt><dd className="break-all whitespace-pre-wrap">
        {value === undefined || value === null ? "Not available / not evaluated" :
          typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </dd></div>)}</dl>}
  </main>;
}
