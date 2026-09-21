type ObjectValue = Record<string, unknown>;
const object = (v: unknown): ObjectValue | null =>
  v !== null && typeof v === "object" && !Array.isArray(v) ? v as ObjectValue : null;
const choose = (v: unknown, values: string[], fallback = "UNKNOWN") =>
  typeof v === "string" && values.includes(v) ? v : fallback;

const fields: Record<string, string[]> = {
  "1m": ["close", "source_open"], "15m": ["close", "source_open"], "1h": ["close", "source_open"],
  trend: ["direction", "fast_ema", "slow_ema", "slope"], structure: ["classification"],
  liquidity: ["equal_highs", "equal_lows", "sweep", "direction"],
  fvg: ["fvg", "direction", "gap_low", "gap_high", "gap_size"],
};

export function analysisTimeRows(input: unknown): [string, unknown][] {
  const p = object(input);
  const valid = p?.schema === "arms.market-analysis-time-profile.v1" &&
    p.profile === "MARKET_ANALYSIS_TIME_PROFILE" && p.execution_mode === "LOCAL_PAPER" &&
    p.paper_entry_authority === "DISABLED" && p.sim_execution_authority === "DISABLED" &&
    p.live_authority === false && p.ninjatrader_account_access === false &&
    p.broker_order_calls === 0 && p.paper_trades_opened === 0 &&
    p.absolute_time_authority === "UNKNOWN" && p.absolute_market_recency === "UNKNOWN" &&
    p.source_time_recency === "UNKNOWN" && p.session_authority === "UNKNOWN" &&
    p.session_status === "UNKNOWN" && p.news_authority === "UNCERTIFIED" &&
    p.decision_status === "NOT_PROJECTED" && p.data_freshness === "NOT_ASSERTED";
  const s = valid ? p : null;
  const age = object(s?.processing_age);
  const adapterAllows = s?.adapter_status === undefined || (s.adapter_status === "LIVE_TAIL" &&
    s.stream_mode === "LIVE_TAIL" && s.exporter_session_status === "BOUND" &&
    s.timing_pair_status === "EXACT_PREFIX" && s.order_submit_reachable === false);
  const active = adapterAllows && s?.market_stream === "LIVE" && s.fault === null &&
    s.transport_liveness === "OBSERVED_RECEIPTS" && s.canonical_continuity === "CONTIGUOUS_OBSERVED" &&
    s.source_time_status === "LABELS_AND_RELATIVE_PROGRESS_ONLY" && age?.status === "QPC_OBSERVED" &&
    typeof age.seconds === "number" && Number.isFinite(age.seconds) && age.seconds >= 0;
  const rows: [string, unknown][] = [
    ["ADAPTER_STATUS", choose(s?.adapter_status, ["WAITING", "BOOTSTRAP", "LIVE_TAIL", "DISCONNECTED", "REVOKED"], "NOT_ATTACHED")],
    ["STREAM_MODE", choose(s?.stream_mode, ["WAITING", "BOOTSTRAP", "LIVE_TAIL", "DISCONNECTED", "REVOKED"], "NOT_ATTACHED")],
    ["EXPORTER_SESSION_STATUS", choose(s?.exporter_session_status, ["BOUND", "WAITING", "DISCONNECTED", "REVOKED"])],
    ["CANONICAL_SEQUENCE", typeof s?.canonical_sequence === "number" && Number.isSafeInteger(s.canonical_sequence) ? s.canonical_sequence : "UNKNOWN"],
    ["TIMING_PAIR_STATUS", choose(s?.timing_pair_status, ["WAITING", "EXACT_PREFIX", "UNAVAILABLE"])],
    ["PROCESSING_AGE_STATUS", active ? "QPC_OBSERVED" : "UNKNOWN"],
    ["TRANSPORT_STATUS", active ? "TRANSPORT_LIVE" : "NOT_LIVE"],
    ["MARKET_STREAM", active ? "LIVE" : "NOT_LIVE"],
    ["STREAM_MEANING", "Local exporter observations; absolute market recency is unproven"],
    ["TRANSPORT_LIVENESS", choose(s?.transport_liveness, ["OBSERVED_RECEIPTS", "UNKNOWN_OR_LOST"])],
    ["PROCESSING_AGE", active ? `${age!.seconds} nominal QPC seconds (not a drift-qualified bound)` : "UNKNOWN"],
    ["CANONICAL_CONTINUITY", active ? "CONTIGUOUS_OBSERVED" : "UNPROVEN_OR_REVOKED"],
    ["SOURCE_TIME_STATUS", active ? "LABELS_AND_RELATIVE_PROGRESS_ONLY" : "UNKNOWN"],
    ["SOURCE_TIME_RECENCY", "UNKNOWN"], ["ABSOLUTE_MARKET_RECENCY", "UNKNOWN"],
    ["ABSOLUTE_TIME_AUTHORITY", "UNKNOWN"], ["SESSION_AUTHORITY", "UNKNOWN"], ["SESSION_STATUS", "UNKNOWN"],
    ["CALENDAR_BINDING", choose(s?.calendar_binding, ["REVIEWED_SNAPSHOT_ONLY", "UNKNOWN"])],
    ["NEWS_AUTHORITY", "UNCERTIFIED"],
    ["ANALYSIS_STATUS", active ? choose(s?.analysis_status, ["SOURCE_RELATIVE_ONLY"], "BLOCKED") : "BLOCKED"],
    ["DECISION_STATUS", "NOT_PROJECTED"], ["EXECUTION_MODE", "LOCAL_PAPER"],
    ["PAPER_ENTRY_AUTHORITY", "DISABLED"], ["SIM_EXECUTION_AUTHORITY", "DISABLED"], ["LIVE_AUTHORITY", "NO"],
  ];
  const components = object(s?.components);
  for (const [name, keys] of Object.entries(fields)) {
    const c = object(components?.[name]);
    const v = object(c?.value);
    const projected: ObjectValue = {};
    if (active && c?.status === "SOURCE_RELATIVE_ONLY" && v) {
      for (const key of keys) {
        const value = v[key];
        if (typeof value === "number" && Number.isFinite(value) || typeof value === "boolean" ||
          typeof value === "string" && (value.length <= 40 && (
            /^(BULLISH|BEARISH|SIDEWAYS|ALCISTA|BAJISTA|LATERAL|NINGUNA|NONE|NO|SÍ)$/.test(value) ||
            key === "source_open" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$/.test(value)))) projected[key] = value;
      }
    }
    rows.push([name.toUpperCase(), Object.keys(projected).length ? {status: "SOURCE_RELATIVE_ONLY", ...projected} : "BLOCKED / INSUFFICIENT DATA"]);
  }
  for (const name of ["REGIME", "CONFLUENCE", "CONFIDENCE"]) rows.push([name, "NOT_PROJECTED"]);
  return rows;
}
