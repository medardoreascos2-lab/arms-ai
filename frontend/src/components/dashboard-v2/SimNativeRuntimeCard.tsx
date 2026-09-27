"use client";

import { useEffect, useState } from "react";
import { getSimNativeRuntime, type JsonObject } from "@/lib/dashboardApi";

const show = (value: unknown) => typeof value === "string" || typeof value === "number" ? String(value) : "—";
const flag = (value: unknown) => value === true ? "Sí" : value === false ? "No" : "Desconocido";
const capability = (value: unknown) => value === false ? "DISABLED" : value === true ? "ENABLED — revisar" : "Desconocido";

export function SimNativeRuntimeView({ data, elapsedSeconds = 0 }: { data: JsonObject | null; elapsedSeconds?: number }) {
  const age = typeof data?.heartbeat_age_seconds === "number" ? data.heartbeat_age_seconds + Math.max(0, elapsedSeconds) : null;
  const maximumAge = typeof data?.heartbeat_maximum_age_seconds === "number" ? data.heartbeat_maximum_age_seconds : null;
  const fresh = data?.heartbeat_fresh === true && age !== null && maximumAge !== null && age >= 0 && age <= maximumAge;
  const invalid = data?.status === "INVALID" || data?.status === "DISCONNECTED" ||
    data?.config_signature_valid === false || data?.controlled_v3_configured === false || data?.authority_loaded === false ||
    (data?.reconciliation_fence !== undefined && data.reconciliation_fence !== null && data.reconciliation_fence !== false) ||
    (typeof data?.connection_status === "string" && data.connection_status !== "Connected") ||
    data?.native_submit_enabled === true || data?.auto_retry_allowed === true;
  const healthy = data?.status === "HEALTHY" && fresh && !invalid && data?.execution_domain === "SIM_NATIVE" &&
    data?.native_account === "Sim101" && data?.provider === "Simulator" && data?.instrument === "NQ DEC26" &&
    data?.controlled_v3_configured === true && data?.authority_loaded === true && data?.config_signature_valid === true &&
    data?.reconciliation_fence === false && data?.native_submit_enabled === false && data?.auto_retry_allowed === false &&
    data?.connection_status === "Connected" && data?.position_state === "FLAT" && data?.active_order_count === 0 &&
    ["command_path_ready", "activation_path_ready", "state_path_ready", "reconciliation_path_ready"].every(key => data?.[key] === true);
  const tone = invalid ? "border-rose-500/50 bg-rose-950/20" : healthy ? "border-emerald-500/40 bg-emerald-950/20" : "border-amber-500/40 bg-amber-950/20";
  const status = !data || data.status === "UNAVAILABLE" ? "UNAVAILABLE" : invalid ? "REVISAR" : !fresh && age !== null ? "STALE" : show(data.status);
  const rows = [
    ["Instrumento", show(data?.instrument)], ["Proveedor", show(data?.provider)],
    ["Conexión", show(data?.connection_status)], ["Heartbeat", fresh ? "Fresh" : age !== null ? "Stale / no validado" : "Sin observación"],
    ["Edad del heartbeat", age === null ? "—" : `${age.toFixed(1)} s`],
    ["Posición", show(data?.position_state)], ["Órdenes activas", show(data?.active_order_count)],
    ["V3 configured", flag(data?.controlled_v3_configured)], ["Authority loaded", flag(data?.authority_loaded)],
    ["Config signature", flag(data?.config_signature_valid)], ["Reconciliation fence", flag(data?.reconciliation_fence)],
    ["Restauración", show(data?.restore_status)], ["Native submit", capability(data?.native_submit_enabled)],
    ["Auto retry", capability(data?.auto_retry_allowed)],
    ["Sesión de mercado", data?.physical_test_readiness === "MARKET_SESSION_CLOSED" ? "Mercado cerrado · MARKET_SESSION_CLOSED" : show(data?.physical_test_readiness)],
    ["Rutas command / activation", `${flag(data?.command_path_ready)} / ${flag(data?.activation_path_ready)}`],
    ["Rutas state / reconciliation", `${flag(data?.state_path_ready)} / ${flag(data?.reconciliation_path_ready)}`],
    ["Observado UTC", show(data?.observed_at)],
  ];
  return <section aria-label="NinjaTrader SIM_NATIVE Runtime" className={`mt-6 rounded-2xl border p-6 ${tone}`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold">NinjaTrader SIM_NATIVE Runtime</h2>
      <span role="status" className="text-sm font-semibold">{status}</span>
    </div>
    <p className="mt-2 text-sm text-slate-300">SIM_NATIVE / Sim101 · Solo lectura · Cuenta y registro financiero separados de PAPER.</p>
    {!data && <p className="mt-3 text-amber-200">Observación no disponible. No se confirma un runtime activo.</p>}
    <dl className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map(([label, value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1 break-words text-sm">{value}</dd></div>)}
    </dl>
    <p className="mt-4 text-xs text-slate-400">Estado reportado por NinjaTrader; esta observación no autoriza ejecución.</p>
  </section>;
}

export default function SimNativeRuntimeCard() {
  const [observation, setObservation] = useState<{ data: JsonObject; receivedAt: number } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    async function refresh() {
      controller = new AbortController();
      const deadline = setTimeout(() => controller?.abort(), 5000);
      const requestedAt = Date.now();
      try {
        const data = await getSimNativeRuntime(controller.signal);
        if (!stopped) { setObservation({ data, receivedAt: requestedAt }); setElapsed((Date.now() - requestedAt) / 1000); }
      } catch {
        if (!stopped) setObservation(null);
      } finally {
        clearTimeout(deadline);
        if (!stopped) timer = setTimeout(refresh, 5000);
      }
    }
    void refresh();
    return () => { stopped = true; clearTimeout(timer); controller?.abort(); };
  }, []);
  useEffect(() => {
    if (!observation) return;
    const timer = setInterval(() => setElapsed((Date.now() - observation.receivedAt) / 1000), 1000);
    return () => clearInterval(timer);
  }, [observation]);
  return <SimNativeRuntimeView data={observation?.data ?? null} elapsedSeconds={elapsed} />;
}
